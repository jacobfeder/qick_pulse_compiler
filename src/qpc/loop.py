from typing import Optional
from typing import Union
from typing import List
from numbers import Number

from qpc.type import QickScope, QickLabel, QickVarType, QickInt, QickReg, QickSweptReg
from qpc.type import QickCode

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
        if 'name' not in kwargs:
            kwargs['name'] = 'loop'

        if inc_ref:
            super().__init__(*args, length=0, **kwargs)
        elif isinstance(code.length, QickVarType):
            super().__init__(*args, length=0, **kwargs)
        elif loops is None:
            super().__init__(*args, length=0, **kwargs)            
        else:
            super().__init__(*args, length=code.length * loops, **kwargs)

        self.loops = loops
        self.inc_ref = inc_ref

        with QickScope(code=self):
            # make a copy so we don't modify the original code
            code = code.qick_copy()

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
                self.loop_reg.assign(QickInt(0))
                self.nloops_reg.assign(QickInt(loops))

            self.asm += f'{self.loop_start_label}:\n'

            if self.loops is not None:
                self.asm += f'TEST -op({self.loop_reg} - {self.nloops_reg})\n'
                self.asm += f'JUMP {self.loop_end_label} -if(NS)\n'

            self.asm += str(code)

            if self.loops is not None:
                self.loop_reg.assign(self.loop_reg + QickInt(1))

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
        if 'name' not in kwargs:
            kwargs['name'] = 'sweep'

        if inc_ref is False and self.soccfg is not None and isinstance(code.length, QickTime):
            # TODO calculate the length based on number of loop iterations
            super().__init__(*args, length=0, **kwargs)
        else:
            # we can't easily calculate the length so just set it to 0
            super().__init__(*args, length=0, **kwargs)

        self.inc_ref = inc_ref

        with QickScope(code=self):
            # make a copy so we don't modify the original code
            code = code.qick_copy()

            if self.inc_ref:
                code.inc_ref()

            self.sweep_start_label = QickLabel(prefix='SWEEP')
            self.sweep_end_label = QickLabel(prefix='SWEEP_END')
            self.sweep_reg = reg

            # the current value of the sweep
            self.asm += '// sweep reg start\n'
            self.asm += self.sweep_reg._assign(self.sweep_reg.start)
            # the max value of the sweep
            self.asm += '// sweep stop\n'
            self.sweep_stop_reg = QickReg()
            self.asm += self.sweep_stop_reg._assign(self.sweep_reg.stop)
            # the step size of the sweep
            self.asm += '// sweep step\n'
            self.sweep_step_reg = QickReg()
            self.asm += self.sweep_step_reg._assign(self.sweep_reg.step)

            # exit the loop of sweep_reg > sweep_stop_reg
            self.asm += f'{self.sweep_start_label}:\n'
            self.asm += f'TEST -op({self.sweep_reg} - {self.sweep_stop_reg})\n'
            self.asm += f'JUMP {self.sweep_end_label} -if(NS)\n'

            # insert the code
            self.asm += str(code)

            # increment sweep_reg by sweep_reg.step
            self.asm += self.sweep_reg._assign(self.sweep_reg + self.sweep_step_reg)
            self.asm += f'JUMP {self.sweep_start_label}\n'
            self.asm += f'{self.sweep_end_label}:\n'
