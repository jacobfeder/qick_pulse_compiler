"""Take a QickCode object defining a pulse sequence and compile it into
assembly code for the tproc v2. Also handle readout.

First, create an SSH tunnel to the RFSoC
ssh -C -L 8000:localhost:8000 xilinx@<ip>

Author: Jacob Feder
Date: 2024-08-16
"""

from __future__ import annotations
from numbers import Number
import logging
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

from qpc.types import QickLabel, QickTime, QickFreq, QickReg, QickExpression, QickCode
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

    # simulate us2cycles, freq2reg, etc.
    def __getattr__(self, attr):
        return lambda x: int(x)

class QickPulseCompiler:
    """Runs a QICK program for tprocv2."""
    def __init__(self,
        iomap: Optional[QickIOMap] = None,
        ns_addr: str = 'localhost',
        ns_port: int = 8000,
        soc_proxy: str = 'rfsoc',
        print_prog: bool = True,
        fake_soc: bool = False,
        **soc_kwargs
        ):
        """
        Args:
            iomap: TODO.
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

    def port(io: [QickIODevice, QickIO]) -> Union[int, Tuple]:
        """Return the port info associated with the given object.

        Args:
            io: QickIODevice or QickIO to return the port number of.

        """
        if isinstance(io, QickIODevice):
            channel_type = io.io.channel_type
            channel = io.io.channel
        elif isinstance(io, QickIO):
            channel_type = io.channel_type
            channel = io.channel
        else:
            raise ValueError('io must be a QickIODevice or QickIO but got '
                f'[{io}]')

        try:
            port_info = self.iomap.mappings[channel_type][channel]
        except KeyError as err:
            raise ValueError(f'iomap does not contain port [{channel}].') from err

        if port_info not in self.iomap.ports[device.io.channel_type]:
            raise ValueError(f'The port [{port_info}] associated with the'
                'given device is not a valid port for the board.')

        return port_info

    def render_exp(self, exp, regno) -> Tuple[str, str]:
        """Create assembly code that evaluates a QickExpression."""

        if regno == MAX_REG:
            raise RuntimeError('Ran out of registers during compilation.')

        # series of REG_WR instructions that go before this expression
        # to prepare the operands
        pre_asm = ''
        # assembly code of this expression, e.g. 'r1 + 5' or 'r1 + r2'
        exp_asm = ''

        if isinstance(exp.left, QickExpression):
            left_pre, left_exp = self.render_asm(exp, regno + 1)
            pre_asm += left_pre
            pre_asm += f'REG_WR r{regno} op -op({left_exp})\n'
            regno += 1
        elif isinstance(exp.left, QickReg):
            exp_asm += f'{exp.left} '
        else:
            exp_asm += f'#{exp.left} '

        exp_asm += exp.operator

        if isinstance(exp.right, QickExpression):
            right_pre, right_exp = self.render_asm(exp, regno + 1)
            pre_asm += right_pre
            pre_asm += f'REG_WR r{regno} op -op({right_exp})\n'
            regno += 1
        elif isinstance(exp.right, QickReg):
            exp_asm += f' {exp.right}'
        else:
            exp_asm += f' #{exp.right}'

        return pre_asm, exp_asm

    def _compile(self, code: QickCode, regno: int, labelno: int):
        """TODO"""
        asm = code.asm

        for key, qick_obj in code.kvp.items():
            if isinstance(qick_obj, QickIO):
                asm = asm.replace(key, str(self.iomap.mappings[qick_obj.channel_type][qick_obj.channel]))
            elif isinstance(qick_obj, QickIODevice):
                asm = asm.replace(key, str(self.iomap.mappings[qick_obj.io.channel_type][qick_obj.io.channel]))
            elif isinstance(qick_obj, QickTime):
                asm = asm.replace(key, str(self.soc.us2cycles(qick_obj.val * 1e6)))
            elif isinstance(qick_obj, QickLabel):
                asm = asm.replace(key, f'{qick_obj.prefix}_{labelno}')
                labelno += 1
            elif isinstance(qick_obj, QickFreq):
                asm = asm.replace(key, str(self.soc.freq2reg(qick_obj.val / 1e6)))
            elif isinstance(qick_obj, QickReg):
                if qick_obj.reg is None:
                    asm = asm.replace(key, f'r{regno}')
                    regno += 1
                else:
                    asm = asm.replace(key, qick_obj.reg)
            elif isinstance(qick_obj, QickExpression):
                pre_asm, exp_asm = self.render_exp(exp=qick_obj, regno=regno)
                asm = asm.replace(key + 'pre_asm', pre_asm)
                asm = asm.replace(key + 'exp_asm', exp_asm)
            else:
                raise RuntimeError(f'[{qick_obj}] not supported.')

        return asm, labelno

    def compile(self, code: QickCode):
        """TODO.

        Args:
            code: The code block to compile.

        """
        asm, _ = self._compile(code=code, regno=0, labelno=0)
        return asm

    def run(self, code: QickCode):
        # start the program
        self.soc.tproc.start()
        _logger.debug('running rfsoc prog...')

    def load(self, code: QickCode):
        """Load the program and configure the tproc.

        Args:
            code: The code block to load.

        """
        # get the user program and remove indentation
        asm = ''
        for line in self.compile(code).split('\n'):
            asm += line.lstrip() + '\n'

        # add a NOP to the beginning of the program
        setup_asm = 'NOP\n'
        # add a 1 ms inc_ref to the beginning of the program
        setup_asm += f'TIME inc_ref #{int(self.soc.us2cycles(1e3))}\n'
        # add an infinite loop to the end of the program
        teardown_asm = 'JUMP HERE\n'
        # add setup and teardown asm
        asm = setup_asm + asm + teardown_asm

        if self.print_prog:
            print('#################')
            print('#### Program ####')
            print('#################')
            for i, line in enumerate(asm.splitlines()):
                # add line numbers
                print(f'{i+1:03}: {line}')
            print('#################\n')

        # assemble program
        pmem, asm_bin = Assembler.str_asm2bin(asm)

        # stop any previously running program
        self.soc.tproc.reset()

        # load the new program into memory
        self.soc.tproc.Load_PMEM(asm_bin)

    def off_prog(self) -> QickCode:
        """A program that outputs 0's on all ports."""
        # TODO
        prog = QickCode(length=0)

        # write 0 waveform into all WPORTs
        for p in self.iomap.dac_ports():
            prog.rf_square_pulse(ch=p, time=0, length=1e-6, freq=100e6, amp=0)

        # disable all DPORTs
        prog.asm += '// write 0 into all DPORTs\n'
        prog.asm += 'REG_WR r0 imm #0\n'
        for port in self.iomap.data_ports():
            prog.asm += f'DPORT_WR p{port} reg r0\n'

        # disable all trig ports
        for port in self.iomap.trigger_ports():
            prog.trig(ch=port, state=False, time=0)

        return prog

    def stop(self):
        """Upload a program that outputs 0's on all ports."""
        # TODO
        # self.load(self.off_prog())
        self.soc.tproc.start()
