"""Take a QickCode object defining a pulse sequence and compile it into
assembly code for the tproc v2. Also handle readout.

First, create an SSH tunnel to the RFSoC
ssh -C -L 8000:localhost:8000 xilinx@<ip>

Author: Jacob Feder
Date: 2024-08-16
"""

from __future__ import annotations
import logging
from math import ceil, log10
from numbers import Number
from pathlib import Path
from typing import Optional, Iterable, Dict, Any, Union

import Pyro4
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.PICKLE_PROTOCOL_VERSION=4
import qick
from qick import QickConfig
from qick.qick_asm import AbsQickProgram
try:
    from qick import QickSoc
except Exception:
    # script is not running on the RFSoC
    local_soc = False
else:
    # script is running on the RFSoC
    local_soc = True
from qick.tprocv2_assembler import Assembler

from qpc.type import QickType, QickConstType, QickInt, QickLabel, QickTime
from qpc.type import QickFreq, QickReg, QickExpression, QickAssignment
from qpc.type import QickScope, QickCode
from qpc.io import QickIO, QickIODevice

_logger = logging.getLogger(__name__)

# maximum immediate value in the tproc
MAX_IMM = 2**23 - 1

# maximum register number
MAX_REG = 15

# dummy classes to simulate the soc object
class FakeTProc:
    def __getattr__(self, attr):
        return lambda *args: None

class FakeSoC:
    def __init__(self, *args, **kwargs):
        self.tproc = FakeTProc()

    def us2cycles(self, x):
        # assume clock = 1 GHz
        return round(1000 * x)

    def freq2reg(self, x):
        return round(x)

class QPC(AbsQickProgram):
    """Runs a QICK program for tprocv2."""
    def __init__(self,
        iomap: QickIOMap,
        ns_addr: str = 'localhost',
        ns_port: int = 8000,
        soc_proxy: str = 'rfsoc',
        print_prog: bool = True,
        fake_soc: bool = False,
        **soc_kwargs
        ):
        """
        Args:
            iomap: Mapping between input/output names and their firmware ports.
            ns_addr: Pyro nameserver address for the RFSoC.
            ns_port: Pyro nameserver port for the RFSoC.
            soc_proxy: Pyro SoC object name.
            fake_soc: If True, simulate the SoC connection for testing purposes.
            soc_kwargs: SoC object keyword args.

        """
        self.iomap = iomap
        self.ns_addr = ns_addr
        self.ns_port = ns_port
        self.soc_proxy = soc_proxy
        self.print_prog = print_prog
        self.fake_soc = fake_soc
        self.soc_kwargs = soc_kwargs

        if self.fake_soc:
            self.soc = FakeSoC()
            self.soccfg = None
        else:
            if local_soc:
                if 'bitfile' not in self.soc_kwargs:
                    raise ValueError('If run locally on the RFSoC, '
                        'bitfile must be defined.')
                self.soc = QickSoc(**self.soc_kwargs)
            else:
                # connect to the pyro name server
                self.name_server = Pyro4.locateNS(host=ns_addr, port=ns_port)
                # load the soc proxy object
                self.soc = Pyro4.Proxy(self.name_server.lookup(soc_proxy))

            self.soccfg = QickConfig(self.soc.get_cfg())
            super().__init__(self.soccfg)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()

    def _compile_assignment(
            self,
            asn: QickAssignment,
        ) -> str:
        """Create the assembly code that evaluates a QickAssignment."""

        if isinstance(asn.rhs, int) or isinstance(asn.rhs, QickConstType):
            asm = f'REG_WR {asn.reg} imm #{asn.rhs}\n'
        elif isinstance(asn.rhs, QickReg):
            asm = f'REG_WR {asn.reg} op -op({asn.rhs})\n'
        elif isinstance(asn.rhs, QickExpression):
            asm = f'{asn.rhs.pre_asm_key()}REG_WR {asn.reg} op -op({asn.rhs.exp_asm_key()})\n'
        else:
            raise TypeError(f'Tried to assign reg a value with an invalid type.')

        return asm

    def _compile_exp(
            self,
            exp: QickExpression,
            regno: int
        ) -> Tuple[str, str]:
        """Create the assembly code that evaluates a QickExpression.

        Args:
            exp: Expression to compile.
            regno: Number of lowest unused register.

        """
        # series of REG_WR instructions that go before this expression
        # to prepare the operands
        pre_asm = ''
        # assembly code of this expression, e.g. 'r1 + 5' or 'r1 + r2'
        exp_asm = ''

        # TODO check that regno does not exceed # of registers

        if exp.operator == '*':
            raise RuntimeError('* not yet implemented in the compiler.')

        if isinstance(exp.left, QickConstType) or isinstance(exp.left, int):
            # left not allowed to be an immediate by the assembler
            # so we need to swap left / right
            if exp.operator == '-':
                raise RuntimeError('Expression with constant minus variable is '
                    'not allowed by the assembler.')
            left = exp.right
            right = exp.left
        else:
            left = exp.left
            right = exp.right

        if isinstance(left, QickExpression):
            left_pre_asm, left_exp_asm = self._compile_exp(exp=left, regno=regno + 1)
            pre_asm += left_pre_asm
            pre_asm += f'REG_WR r{regno} op -op({left_exp_asm})\n'
            exp_asm += f'r{regno} '
            regno += 1
        elif isinstance(left, QickReg):
            exp_asm += f'{left} '
        else:
            exp_asm += f'#{left} '

        exp_asm += exp.operator

        if isinstance(right, QickExpression):
            right_pre_asm, right_exp_asm = self._compile_exp(exp=right, regno=regno + 1)
            pre_asm += right_pre_asm
            pre_asm += f'REG_WR r{regno} op -op({right_exp_asm})\n'
            exp_asm += f' r{regno}'
        elif isinstance(right, QickReg):
            exp_asm += f' {right}'
        else:
            exp_asm += f' #{right}'

        return pre_asm, exp_asm

    def _compile(self, code: QickCode, regno: int, labelno: int):
        """Compile the assembly code. All special *key* in the assembly code
        will be replaced by their firmware-specific values.

        Args:
            code: Code to compile.
            regno: Number of lowest unused register.
            labelno: Lowest unused labelid in order to ensure all labels
                are unique. 

        """
        asm = code.asm

        if code.iomap is None:
            code.iomap = self.iomap
        if code.soc is None:
            code.soc = self.soc

        # add name header
        if code.name is not None:
            asm = f'// ---------------\n// {code.name}\n// ---------------\n' + asm

        # compile QickAssignment (register assignments)
        with QickScope(code=code):
            for key, qick_obj in code.kvp.copy().items():
                if isinstance(qick_obj, QickAssignment):
                    assignment_asm = self._compile_assignment(asn=qick_obj)
                    asm = asm.replace(key, assignment_asm)

        # calculate how many registers will be allocated
        nregs = 0
        for qick_obj in code.kvp.values():
            if isinstance(qick_obj, QickReg) and qick_obj.reg is None:
                nregs += 1

        # recursively compile the rest of the QickCode objects
        for key, qick_obj in code.kvp.copy().items():
            if isinstance(qick_obj, QickCode):
                sub_asm, labelno = self._compile(code=qick_obj, regno=regno + nregs, labelno=labelno)
                asm = asm.replace(key, sub_asm)

        # compile the QickExpression
        with QickScope(code=code):
            # make a copy since we'll be adding new elements
            for key, qick_obj in code.kvp.copy().items():
                if isinstance(qick_obj, QickExpression):
                    pre_asm, exp_asm = self._compile_exp(exp=qick_obj, regno=regno + nregs)
                    asm = asm.replace(key + 'pre_asm', pre_asm)
                    asm = asm.replace(key + 'exp_asm', exp_asm)

        # compile the rest of the non-code objects
        for key, qick_obj in code.kvp.items():
            if isinstance(qick_obj, QickTime) or isinstance(qick_obj, QickFreq):
                asm = asm.replace(key, str(qick_obj.clocks()))
            elif isinstance(qick_obj, QickInt):
                asm = asm.replace(key,str(qick_obj.val))
            elif isinstance(qick_obj, QickLabel):
                asm = asm.replace(key, f'{qick_obj.prefix}_{labelno}')
                labelno += 1
            elif isinstance(qick_obj, QickReg):
                if qick_obj.reg is None:
                    asm = asm.replace(key, f'r{regno}')
                    regno += 1
                else:
                    asm = asm.replace(key, qick_obj.reg)

        # substitute port names for numbers
        for port_type in self.iomap.mappings:
            for port_name, port in self.iomap.mappings[port_type].items():
                # port name is a string, e.g. "PMOD0_0"
                # port is one of the namedtuple types from io.py
                asm = asm.replace(f'*{port_name}*', str(port.port))

        # add name footer
        if code.name is not None:
            asm += f'// ---------------\n// end {code.name}\n// ---------------\n'

        return asm, labelno

    def compile(self, code: QickCode, start_reg: int = 0):
        """Compile a QickCode object into assembly code compatible with tprocv2.

        Args:
            code: The code block to compile.
            start_reg: Lowest register number that will be used by the compiler.
                All registers below this will be ignored and can be utilized by
                the user for global variables.

        """
        wrapper_code = QickCode(name='program')
        with QickScope(code=wrapper_code):
            # make a copy so we don't modify the original code during compilation
            code = code.qick_copy()

            # add a NOP to the beginning of the program
            wrapper_code.asm += 'NOP\n'
            # add a short inc_ref to the beginning of the program
            wrapper_code.asm += f'TIME inc_ref #{QickTime(100e-6)}\n'

            # wrap the code
            wrapper_code.asm += str(code)

            # add an infinite loop to the end of the program
            wrapper_code.asm += 'JUMP HERE\n'

            # compile!
            asm, _ = self._compile(
                code=wrapper_code,
                regno=start_reg,
                labelno=0
            )

            if '*' in asm:
                raise RuntimeError(f'Internal error: some keys were not matched '
                    f'during compilation. Program:\n{asm}')

            return asm

    def run(
        self,
        code: Optional[QickCode] = None,
        start_reg: Optional[int] = 0
    ):
        """Run the currently loaded assembly program, or load and run a new one.

        Args:
            code: If None, the program that was last loaded with load() will be run.
                Otherwise this code will be compiled, loaded, and then run.
            start_reg: See compile().

        """
        if code is not None:
            asm = self.compile(code=code, start_reg=start_reg)
            self.load(asm=asm)

        # start the program
        self.soc.tproc.start()
        _logger.debug('running rfsoc prog...')

    def load(self, asm: str):
        """Load the program and configure the tproc.

        Args:
            asm: Assembly code to load.

        """
        if self.print_prog:
            ndigits = ceil(log10(asm.count('\n')))
            for i, line in enumerate(asm.splitlines()):
                # add line numbers
                print(f'{i+1:0{str(ndigits)}}: {line}')

        # assemble program
        pmem, asm_bin = Assembler.str_asm2bin(asm)

        # stop any previously running program
        self.soc.tproc.reset()

        # load the new program into memory
        self.soc.tproc.Load_PMEM(asm_bin)

    def off_prog(self) -> QickCode:
        """A program that outputs 0's on all ports."""
        off_code = QickCode(name='off program', soc=self.soc)
        with QickScope(off_code):
            # disable all trig ports
            for p in self.iomap.trigger_ports():
                off_code.trig(ch=p, state=False, time=0)

            # write 0 waveform into all WPORTs
            for p in self.iomap.dac_ports():
                off_code.rf_pulse(ch=p, length=1e-6, freq=100e6, amp=0, time=0)

            # disable all DPORTs
            off_code.asm += '// write 0 into all DPORTs\n'
            off_code.asm += 'REG_WR r0 imm #0\n'
            for port in self.iomap.data_ports():
                off_code.asm += f'DPORT_WR p{port} reg r0\n'

        return off_code

    def stop(self):
        """Upload a program that outputs 0's on all ports."""
        self.run(self.off_prog())
        self.soc.tproc.start()
