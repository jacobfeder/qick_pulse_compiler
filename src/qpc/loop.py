# from typing import Optional
# from typing import Union
# from typing import List
# from numbers import Number

# from bs3.config import trig_channels
# from bs3.instrument.rfsoc.qickprog import QickCode
# from bs3.instrument.rfsoc.qickprog import QickReg
# from bs3.instrument.rfsoc.qickprog import QickLabel
# from bs3.instrument.rfsoc.qickprog import QickTime
# from bs3.instrument.rfsoc.qickprog import QickFreq
# from bs3.instrument.rfsoc.qickprog import QickSweepArange
# from bs3.instrument.rfsoc.qickprog import MAX_IMM

# class QickSweep(QickCode):
#     """While loop that sweeps the value stored in a register."""
#     def __init__(
#         self,
#         loop_code: QickCode,
#         reg: QickReg,
#         sweep_args: QickSweepArange,
#         inc_ref: bool = True,
#         **kwargs
#     ):
#         """

#         Args:
#             loop_code: Code to repeat in a loop.
#             reg: Register to sweep over.
#             sweep_args: Range over which to sweep the register.
#             inc_ref: If true, inc_ref the length of loop_code after each loop.
#             kwargs: Keyword arguments to pass to the QickCode constructor.

#         """
#         # set a bogus length since it would be difficult to predict the actual length
#         super().__init__(length=0, **kwargs)

#         self.sweep_args = sweep_args

#         self.sweep_start_label = QickLabel(code=self, prefix='SWEEP')
#         self.sweep_end_label = QickLabel(code=self, prefix='SWEEP_END')
#         # tau
#         self.loop_reg = reg

#         # tau = 0
#         if isinstance(self.sweep_args.start, QickTime) or isinstance(self.sweep_args.start, QickFreq):
#             self.asm += f'REG_WR {self.loop_reg} imm #{self.sweep_args.start_key()}\n'
#         elif isinstance(self.sweep_args.start, int):
#             self.asm += f'REG_WR {self.loop_reg} imm #{self.sweep_args.start}\n'
#         elif isinstance(self.sweep_args.start, QickReg):
#             self.asm += f'REG_WR {self.loop_reg} op -op({self.sweep_args.start})\n'
#         else:
#             raise ValueError(f'start must be a QickTime, int, or QickReg')

#         # while tau < stop
#         self.asm += f'{self.sweep_start_label}:\n'

#         if isinstance(self.sweep_args.stop, QickTime) or isinstance(self.sweep_args.stop, QickFreq):
#             scratch_reg = QickReg(code=self, scratch=True)
#             self.asm += f'REG_WR {scratch_reg} imm #{self.sweep_args.stop_key()}\n'
#             self.asm += f'TEST -op({self.loop_reg} - {scratch_reg})\n'
#         elif isinstance(self.sweep_args.stop, int):
#             scratch_reg = QickReg(code=self, scratch=True)
#             self.asm += f'REG_WR {scratch_reg} imm #{self.sweep_args.stop}\n'
#             self.asm += f'TEST -op({self.loop_reg} - {scratch_reg})\n'
#         elif isinstance(self.sweep_args.stop, QickReg):
#             self.asm += f'TEST -op({self.loop_reg} - {self.sweep_args.stop})\n'
#         else:
#             raise ValueError(f'stop must be a QickTime, int, or QickReg')

#         self.asm += f'JUMP {self.sweep_end_label} -if(NS)\n'

#         # loop code
#         self.asm += loop_code.asm + '// ---------------\n'

#         if inc_ref:
#             # increment reference time
#             self.asm += f'TIME inc_ref #{QickTime(code=self, time=loop_code.length, relative=False)}\n'

#         # tau += step
#         if isinstance(self.sweep_args.step, QickTime) or isinstance(self.sweep_args.step, QickFreq):
#             scratch_reg = QickReg(code=self, scratch=True)
#             self.asm += f'REG_WR {scratch_reg} imm #{self.sweep_args.step_key()}\n'
#             self.asm += f'REG_WR {self.loop_reg} op -op({self.loop_reg} + {scratch_reg})\n'
#         elif isinstance(self.sweep_args.step, int):
#             scratch_reg = QickReg(code=self, scratch=True)
#             self.asm += f'REG_WR {scratch_reg} imm #{self.sweep_args.step}\n'
#             self.asm += f'REG_WR {self.loop_reg} op -op({self.loop_reg} + {scratch_reg})\n'
#         elif isinstance(self.sweep_args.step, QickReg):
#             self.asm += f'REG_WR {self.loop_reg} op -op({self.loop_reg} + {self.sweep_args.step})\n'
#         else:
#             raise ValueError(f'step must be a QickTime, int, or QickReg')

#         # jump to beginning of while
#         self.asm += f'JUMP {self.sweep_start_label}\n'
#         self.asm += f'{self.sweep_end_label}:\n'

#         self.merge_kvp(loop_code.kvp)

# class QickLoop(QickCode):
#     """Repeat a code block."""
#     def __init__(
#         self,
#         loop_code: QickCode,
#         loops: Optional[int],
#         inc_ref: bool = True,
#         **kwargs
#     ):
#         """

#         Args:
#             loop_code: Code to repeat in a loop.
#             loops: Number of loops. Set to None for an infinite loop.
#             name: Program name.
#             inc_ref: If true, inc_ref the length of loop_code after each loop.
#             kwargs: Keyword arguments to pass to the QickCode constructor.

#         """
#         if inc_ref:
#             super().__init__(length=0, **kwargs)
#         else:
#             super().__init__(length=loop_code.length * loops, **kwargs)

#         loop_reg = QickReg(code=self)
#         scratch_reg = QickReg(code=self, scratch=True)
#         exp_label = QickLabel(code=self, prefix='LOOP')
#         exp_end_label = QickLabel(code=self, prefix='LOOP_END')

#         if loops is not None:
#             self.asm += f'REG_WR {loop_reg} imm #0\n'

#         self.asm += f'{exp_label}:\n'

#         if loops is not None:
#             self.asm += f'REG_WR {scratch_reg} imm #{loops}\n'
#             self.asm += f'TEST -op({loop_reg} - {scratch_reg})\n'
#             self.asm += f'JUMP {exp_end_label} -if(NS)\n'

#         self.asm += loop_code.asm + '// ---------------\n'

#         if inc_ref:
#             self.asm += f'TIME inc_ref #{QickTime(code=self, time=loop_code.length, relative=False)}\n'

#         if loops is not None:
#             self.asm += f'REG_WR {loop_reg} op -op({loop_reg} + #1)\n'

#         self.asm += f'JUMP {exp_label}\n'

#         if loops is not None:
#             self.asm += f'{exp_end_label}:\n'

#         self.merge_kvp(loop_code.kvp)
