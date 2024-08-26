from copy import deepcopy
from typing import Optional
from typing import Union
from typing import List
from numbers import Number

from qpc.types import QickScope, QickLabel, QickVarType, QickReg, QickSweptReg
from qpc.types import QickCode

class QickLoop(QickCode):
    """Repeat a code block."""
    def __init__(
        self,
        code: QickCode,
        loops: Optional[int],
        inc_ref: bool,
        *args,
        **kwargs
    ):
        """

        Args:
            code: Code to repeat in a loop.
            loops: Number of loops. Set to None for an infinite loop.
            inc_ref: If true, inc_ref the length of loop_code after each loop.
            args: Arguments to pass to the QickCode constructor.
            kwargs: Keyword arguments to pass to the QickCode constructor.

        """
        super().__init__(*args, **kwargs)

        self.loops = loops
        self.inc_ref = inc_ref

        with QickScope(code=self):
            # make a copy so we don't modify the original code
            # code = deepcopy(code)

            if inc_ref:
                super().__init__(*args, length=0, **kwargs)
            elif isinstance(code.length, QickVarType):
                super().__init__(*args, length=0, **kwargs)
            else:
                super().__init__(*args, length=code.length * loops, **kwargs)

            if self.inc_ref:
                code.inc_ref()

            # the current loop iteration
            self.loop_reg = QickReg()
            # the number of loop iterations
            self.nloops_reg = QickReg()

            # loop start and end labels
            self.loop_start_label = QickLabel(prefix='LOOP')
            self.loop_end_label = QickLabel(prefix='LOOP_END')

            if self.loops is not None:
                self.loop_reg.assign(0)
                self.nloops_reg.assign(loops)

            self.asm += f'{self.loop_start_label}:\n'

            if self.loops is not None:
                self.asm += f'TEST -op({self.loop_reg} - {self.nloops_reg})\n'
                self.asm += f'JUMP {self.loop_end_label} -if(NS)\n'

            self.asm += str(code)

            # if self.inc_ref:
            #     with QickScope(code=code):
            #         # the amount to inc_ref by
            #         self.ref_reg = QickReg()
            #         self.ref_reg.assign(code.length)
            #         code.asm += f'TIME inc_ref {self.ref_reg}\n'

            if self.loops is not None:
                self.loop_reg.assign(self.loop_reg + 1)

            self.asm += f'JUMP {self.loop_start_label}\n'

            if self.loops is not None:
                self.asm += f'{self.loop_end_label}:\n'

class QickSweep(QickCode):
    """While loop that sweeps the value stored in a register."""
    def __init__(
        self,
        code: QickCode,
        reg: QickSweptReg,
        inc_ref: bool,
        *args,
        **kwargs
    ):
        """

        Args:
            code: Code to repeat in a loop.
            reg: Register to sweep over.
            inc_ref: If true, inc_ref the length of code after each loop.
            args: Arguments to pass to the QickCode constructor.
            kwargs: Keyword arguments to pass to the QickCode constructor.

        """
        super().__init__(*args, **kwargs)

        with QickScope(code=self):
            # make a copy so we don't modify the original code
            code = code.qick_copy()

            if inc_ref is False and self.soccfg is not None and isinstance(code.length, QickTime):
                # TODO calculate the length based on number of loop iterations
                super().__init__(*args, length=0, **kwargs)
            else:
                # we can't easily calculate the length so just set it to 0
                super().__init__(*args, length=0, **kwargs)

            self.sweep_start_label = QickLabel(prefix='SWEEP')
            self.sweep_end_label = QickLabel(prefix='SWEEP_END')
            self.sweep_reg = reg

            self.asm += '// ---------------\n'
            self.asm += '// Sweep\n'
            self.asm += '// ---------------\n'

            # the current value of the sweep
            self.sweep_reg.assign(self.sweep_reg.start)
            # the max value of the sweep
            self.max_sweep_reg = QickReg()
            self.max_sweep_reg.assign(self.sweep_reg.stop)

            self.asm += f'{sweep_start_label}:\n'
            self.asm += f'TEST -op({self.sweep_reg} - {self.max_sweep_reg})\n'
            self.asm += f'JUMP {self.sweep_end_label} -if(NS)\n'

            self.asm += '// ---------------\n'
            self.asm += str(code)
            self.asm += '// ---------------\n'

            if self.inc_ref:
                # the amount to inc_ref by
                self.ref_reg = QickReg()
                self.ref_reg.assign(code.length)
                self.asm += f'TIME inc_ref {self.ref_reg}\n'

            self.sweep_reg.assign(self.sweep_reg + self.sweep_reg.step)

            self.asm += f'JUMP {self.sweep_start_label}\n'
            self.asm += f'{self.sweep_end_label}:\n'
            self.asm += '// ---------------\n'
