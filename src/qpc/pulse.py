# from typing import Union
# from typing import Optional
# from numbers import Number

# import numpy as np

# from bs3.instrument.rfsoc.qickprog import QickCode
# from bs3.instrument.rfsoc.qickprog import QickIO
# from bs3.instrument.rfsoc.qickprog import QickIODevice
# from bs3.instrument.rfsoc.qickprog import QickReg
# from bs3.instrument.rfsoc.qickprog import QickTime










    # def trig(
    #         self,
    #         ch: Union[QickIODevice, QickIO, int],
    #         state: bool,
    #         time: Union[Number, QickTime, QickReg, QickExpression],
    #     ):
    #     """Set a trigger port high or low.

    #     Args:
    #         ch: QickIODevice, QickIO, or port to trigger.
    #         state: Whether to set the trigger state True or False.
    #         time: Time at which to set the state.

    #     """
    #     port, offset = self.deembed_io(ch)

    #     asm = f'// Setting trigger port {port} to {state}\n'
    #     asm += self.assign_reg(reg=QickReg(), value=time)

    #     if state:
    #         asm += f'TRIG set p{port}\n'
    #     else:
    #         asm += f'TRIG clr p{port}\n'

    #     self.asm += asm

    # def sig_gen_conf(self, outsel = 'product', mode = 'oneshot', stdysel='zero', phrst = 0) -> int:
    #     outsel_reg = {'product': 0, 'dds': 1, 'input': 2, 'zero': 3}[outsel]
    #     mode_reg = {'oneshot': 0, 'periodic': 1}[mode]
    #     stdysel_reg = {'last': 0, 'zero': 1}[stdysel]

    #     mc = phrst*0b10000 + stdysel_reg*0b01000 + mode_reg*0b00100 + outsel_reg
    #     return mc

    # def rf_square_pulse(
    #         self,
    #         ch: Union[QickIODevice, QickIO, int],
    #         time: Optional[Union[QickTime, Number, QickReg]],
    #         length: Optional[Union[Number, QickReg]],
    #         freq: Optional[Union[QickFreq, Number, QickReg]] = None,
    #         amp: Optional[int] = None,
    #     ):
    #     """Generate a square RF pulse.

    #     Args:
    #         ch: QickIODevice, QickIO, or port to output an RF pulse.
    #         time: Time at which to set the state. Pass a time (s) or a register
    #             containing the time in cycles. Set to None to use the value
    #             currently in out_usr_time.
    #         length: Length of the RF pulse. Pass a time (s) or a register
    #             containing the time in cycles. Set to None to use the value
    #             currently stored in w_length.
    #         freq: RF frequency of the pulse. Pass a frequency (Hz) or a register
    #             containing the frequency in cycles. Set to None to use the value
    #             currently stored in w_freq.
    #         amp: RF amplitude. Pass an integer (-32,768 to 32,767) or a register
    #             containing the amplitude. Set to None to use the value currently
    #             stored in w_gain.

    #     """
    #     port, offset = self.deembed_io(ch)

    #     asm = f'// Pulsing RF port {port}\n'

    #     if time is not None:
    #         # if time is not associated with any code block, associate it now
    #         self.associate_code(time)

    #         if isinstance(time, QickReg):
    #             asm += f'REG_WR out_usr_time op -op({time} + #{offset})\n'
    #         elif isinstance(time, QickTime) or isinstance(time, Number):
    #             asm += f'REG_WR out_usr_time imm #{time + offset}\n'                
    #         else:
    #             raise ValueError(f'time must be a QickTime, number, or QickReg.')

    #     if length is not None:
    #         # if length is not associated with any code block, associate it now
    #         self.associate_code(length)

    #         if isinstance(length, QickReg):
    #             asm += f"""REG_WR w_length op -op({length})\n"""
    #         elif isinstance(length, Number):
    #             asm += f"""REG_WR w_length imm #{QickTime(time=length, relative=False, code=self)}\n"""
    #         else:
    #             raise ValueError(f'length must be a number or QickReg.')

    #     if freq is not None:
    #         # if freq is not associated with any code block, associate it now
    #         self.associate_code(freq)

    #         if isinstance(freq, QickReg):
    #             asm += f"""REG_WR w_freq op -op({freq})\n"""
    #         elif isinstance(freq, QickFreq):
    #             asm += f"""REG_WR w_freq imm #{freq}\n"""
    #         elif isinstance(freq, Number):
    #             asm += f"""REG_WR w_freq imm #{QickFreq(freq=freq, code=self)}\n"""
    #         else:
    #             raise ValueError(f'freq must be a QickFreq, number, or QickReg.')

    #     if amp is not None:
    #         # if amp is not associated with any code block, associate it now
    #         self.associate_code(amp)

    #         if isinstance(amp, QickReg):
    #             asm += f"""REG_WR w_gain op -op({amp})\n"""
    #         elif isinstance(amp, Number):
    #             asm += f"""REG_WR w_gain imm #{amp}\n"""
    #         else:
    #             raise ValueError(f'amp must be a number or QickReg.')

    #     asm += f"REG_WR w_conf imm #{self.sig_gen_conf(outsel='dds', mode='oneshot', stdysel='zero', phrst=0)}\n"
    #     asm += f'WPORT_WR p{port} r_wave\n'

    #     self.asm += asm






# class Delay(QickCode):
#     def __init__(self, length: Number, *args, **kwargs):
#         """A delay.

#         Args:
#             length: Length of the delay.

#         """
#         super().__init__(*args, length=length, **kwargs)

# class TrigConst(QickCode):
#     def __init__(
#         self,
#         ch: Union[QickIODevice, QickIO, int],
#         *args,
#         invert: bool = False,
#         **kwargs
#     ):
#         """Set a digital trigger port high or low.

#         Args:
#             ch: Channel to turn on/off.
#             invert: If true, turn the channel off.

#         """
#         super().__init__(*args, length=0, **kwargs)
#         if invert:
#             self.trig(ch=ch, state=False, time=0)
#         else:
#             self.trig(ch=ch, state=True, time=0)

# class TrigPulse(QickCode):
#     def __init__(
#         self,
#         ch: Union[QickIODevice, QickIO, int],
#         pulse_length: Union[Number, QickReg],
#         *args,
#         pulse_time: Union[Number, QickReg] = 0,
#         block_length: Optional[Number] = None,
#         invert: bool = False,
#         **kwargs
#     ):
#         """A digital pulse on a trigger port.

#         Args:
#             ch: Channel to pulse.
#             pulse_length: Length of the trigger pulse.
#             pulse_time: Start time of the trigger pulse within this code block.
#             block_length: Length of this code block. If None, use pulse_length.
#             invert: If true, turn the channel off, then on.

#         """
#         if block_length is not None:
#             super().__init__(*args, length=block_length, **kwargs)
#         else:
#             if isinstance(pulse_length, QickReg):
#                 raise ValueError('pulse_length cannot be a register if '
#                     'block_length is not defined.')
#             super().__init__(*args, length=pulse_length, **kwargs)

#         # end time for pulse
#         endtime_reg = QickReg(code=self)
#         if isinstance(pulse_time, QickReg) and isinstance(pulse_length, QickReg):
#             self.asm += f'REG_WR {endtime_reg} op -op({pulse_time} + {pulse_length})\n'
#         elif isinstance(pulse_time, Number) and isinstance(pulse_length, QickReg):
#             self.asm += f'REG_WR {endtime_reg} op -op(#{QickTime(code=self, time=pulse_time)} + {pulse_length})\n'
#         elif isinstance(pulse_time, QickReg) and isinstance(pulse_length, Number):
#             self.asm += f'REG_WR {endtime_reg} op -op({pulse_time} + #{QickTime(code=self, time=pulse_length)})\n'
#         else:
#             self.asm += f'REG_WR {endtime_reg} imm #{QickTime(code=self, time=pulse_time + pulse_length)}\n'

#         if invert:
#             self.trig(ch=ch, state=False, time=pulse_time)
#             self.trig(ch=ch, state=True, time=endtime_reg)
#         else:
#             self.trig(ch=ch, state=True, time=pulse_time)
#             self.trig(ch=ch, state=False, time=endtime_reg)

# class RFSquarePulse(QickCode):
#     def __init__(
#         self,
#         ch: Union[QickIODevice, QickIO, int],
#         freq: Optional[Union[Number, QickReg]],
#         amp: Optional[Union[int, QickReg]],
#         pulse_length: Union[Number, QickReg],
#         *args,
#         pulse_time: Union[Number, QickReg] = 0,
#         block_length: Optional[Number] = None,
#         **kwargs,
#     ):
#         """An RF square pulse.

#         Args:
#             ch: QickIODevice, QickIO, or port to output an RF pulse.
#             freq: RF frequency of the pulse. Pass a frequency (Hz) or a register
#                 containing the frequency in cycles. Set to None to use the value
#                 currently stored in w_freq.
#             amp: RF amplitude. Pass an integer (-32,768 to 32,767) or a register
#                 containing the amplitude. Set to None to use the value currently
#                 stored in w_gain.
#             pulse_length: Length of the RF pulse. Pass a time (s) or a register
#                 containing the time in cycles. Set to None to use the value
#                 currently stored in w_length.
#             pulse_time: Start time of the trigger pulse within this code block.
#             block_length: Length of this code block. If None, use pulse_length.

#         """
#         if block_length is not None:
#             super().__init__(*args, length=block_length, **kwargs)
#         else:
#             super().__init__(*args, length=pulse_length, **kwargs)

#         self.rf_square_pulse(ch=ch, time=pulse_time, length=pulse_length, freq=freq, amp=amp)


# # # prototype code for mixing the RF with a user-defined envelope

# # class RFEnvelope(QickCode):
# #     def __init__(
# #         self,
# #         ch: Union[QickIODevice, QickIO, int],
# #         data: np.array,
# #         *args,
# #         **kwargs
# #     ):
# #         """An RF square pulse.

# #         Args:
# #             ch: QickIODevice, QickIO, or port to output an RF pulse.
# #             data:

# #         """
# #         data_2d = np.zeros((length(data), 2), dtype=np.int16)
# #         data_2d[:, 0] = np.round(data)
# #         self.soc.load_pulse_data(
# #             ch=self.dac_port_mapping[dac_ch],
# #             data=make2d(wave),
# #             addr=0
# #         )

# #         self.rf_square_pulse(ch=ch, time=0, length=length, freq=freq, amp=amp)

# # def sawtooth(length=16, maxv=30000, repeat=1):
# #     """
# #     Create a numpy array containing a sawtooth function

# #     :param length: Length of array
# #     :type length: int
# #     :param maxv: Maximum amplitude of triangle function
# #     :type maxv: float
# #     :param n_maxv: Maximum amplitude of triangle function
# #     :type maxv: float
    
# #     :return: Numpy array containing a triangle function
# #     :rtype: array
# #     """

# #     ramp = np.linspace(0, maxv, length)
# #     y = []
# #     for ind in range(repeat):
# #         y = np.append(y, ramp)
# #     return y

# # def make2d(data):
# #     data_2d = np.zeros((length(data), 2), dtype=np.int16)
# #     data_2d[:, 0] = np.round(data)

# # class TestEnvelope(QickProgV2):
# #     def __init__(self, *args, **kwargs):
# #         self.dac_ch = 'DAC_A'

# #         self.wave = sawtooth(length=self.soc.us2cycles(1), maxv = 30000, repeat=10)
# #         self.soc.load_pulse_data(
# #             ch=self.dac_port_mapping[dac_ch],
# #             data=make2d(wave),
# #             addr=0
# #         )

# #     def prog(self):

# #         amp_reg = 32_767

# #         prog = f"""\
# #         // give the tproc some time before we start queuing waves
# #         TIME inc_ref #{self.soc.us2cycles(1)}
# #         // set up pulse parameters
# #         REG_WR w_gain imm #{amp_reg}
# #         REG_WR w_length imm #{length(self.wave)}
# #         REG_WR w_env imm #0
# #         REG_WR w_conf imm #{self.sig_gen_conf(outsel='input', mode='oneshot')}

# #         REG_WR out_usr_time imm #{0}
# #         WPORT_WR p{self.dac_port_mapping[self.dac_ch]} r_wave
# #         """
# #         return prog
