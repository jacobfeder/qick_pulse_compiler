from typing import Union
from typing import Optional
from numbers import Number

from qpc.io import QickIO, QickIODevice
from qpc.type import QickType, QickVarType, QickFreq, QickTime, QickReg
from qpc.type import QickCode

class Delay(QickCode):
    def __init__(self, length: QickType, *args, **kwargs):
        """A delay.

        Args:
            length: Length of the delay.

        """
        super().__init__(*args, length=length, **kwargs)

class TrigConst(QickCode):
    def __init__(
        self,
        ch: Union[QickIODevice, QickIO, int],
        *args,
        invert: bool = False,
        **kwargs
    ):
        """Set a digital trigger port high or low.

        Args:
            ch: Channel to turn on/off.
            invert: If true, turn the channel off.

        """
        if 'name' not in kwargs:
            kwargs['name'] = 'trig const'
        super().__init__(*args, **kwargs)
        if invert:
            self.trig(ch=ch, state=False, time=0)
        else:
            self.trig(ch=ch, state=True, time=0)

class TrigPulse(QickCode):
    def __init__(
        self,
        ch: Union[QickIODevice, QickIO, int],
        length: Union[Number, QickTime, QickVarType],
        *args,
        invert: bool = False,
        **kwargs
    ):
        """A digital pulse on a trigger port.

        Args:
            ch: Channel to pulse.
            length: Length of the trigger pulse.
            invert: If true, turn the channel off, then on.

        """
        if 'name' not in kwargs:
            kwargs['name'] = 'trig pulse'
        super().__init__(*args, length=length, **kwargs)

        if invert:
            self.trig(ch=ch, state=False, time=0)
            self.trig(ch=ch, state=True, time=length)
        else:
            self.trig(ch=ch, state=True, time=0)
            self.trig(ch=ch, state=False, time=length)

class RFSquarePulse(QickCode):
    def __init__(
        self,
        ch: Union[QickIODevice, QickIO, int],
        length: Optional[Union[Number, QickTime, QickVarType]],
        freq: Optional[Union[Number, QickFreq, QickVarType]],
        amp: Optional[int],
        time: Optional[Union[Number, QickTime, QickVarType]] = 0,
        *args,
        **kwargs,
    ):
        """An RF square pulse.

        Args:
            ch: QickIODevice, QickIO, or port to output an RF pulse.
            length: Length of the RF pulse. Pass a time (s), QickLength,
                QickReg, QickExpression. Set to None to use the value
                currently in w_length.
            freq: RF frequency of the pulse. Pass a frequency (s), QickFreq,
                QickReg, QickExpression. Set to None to use the value
                currently in w_freq.
            amp: RF amplitude. Pass an integer (-32,768 to 32,767).
                Set to None to use the value currently stored in w_gain.
            time: Time at which to play the pulse. Pass a time (s), QickTime,
                QickReg, QickExpression. Set to None to use the value
                currently in out_usr_time.

        """
        if 'name' not in kwargs:
            kwargs['name'] = 'rf pulse'
        super().__init__(*args, length=length, **kwargs)

        self.rf_square_pulse(
            ch=ch,
            length=length,
            freq=freq,
            amp=amp,
            time=time,
        )

# # prototype code for mixing the RF with a user-defined envelope

# class RFEnvelope(QickCode):
#     def __init__(
#         self,
#         ch: Union[QickIODevice, QickIO, int],
#         data: np.array,
#         *args,
#         **kwargs
#     ):
#         """An RF square pulse.

#         Args:
#             ch: QickIODevice, QickIO, or port to output an RF pulse.
#             data:

#         """
#         data_2d = np.zeros((length(data), 2), dtype=np.int16)
#         data_2d[:, 0] = np.round(data)
#         self.soc.load_pulse_data(
#             ch=self.dac_port_mapping[dac_ch],
#             data=make2d(wave),
#             addr=0
#         )

#         self.rf_square_pulse(ch=ch, time=0, length=length, freq=freq, amp=amp)

# def sawtooth(length=16, maxv=30000, repeat=1):
#     """
#     Create a numpy array containing a sawtooth function

#     :param length: Length of array
#     :type length: int
#     :param maxv: Maximum amplitude of triangle function
#     :type maxv: float
#     :param n_maxv: Maximum amplitude of triangle function
#     :type maxv: float
    
#     :return: Numpy array containing a triangle function
#     :rtype: array
#     """

#     ramp = np.linspace(0, maxv, length)
#     y = []
#     for ind in range(repeat):
#         y = np.append(y, ramp)
#     return y

# def make2d(data):
#     data_2d = np.zeros((length(data), 2), dtype=np.int16)
#     data_2d[:, 0] = np.round(data)

# class TestEnvelope(QickProgV2):
#     def __init__(self, *args, **kwargs):
#         self.dac_ch = 'DAC_A'

#         self.wave = sawtooth(length=self.soc.us2cycles(1), maxv = 30000, repeat=10)
#         self.soc.load_pulse_data(
#             ch=self.dac_port_mapping[dac_ch],
#             data=make2d(wave),
#             addr=0
#         )

#     def prog(self):

#         amp_reg = 32_767

#         prog = f"""\
#         // give the tproc some time before we start queuing waves
#         TIME inc_ref #{self.soc.us2cycles(1)}
#         // set up pulse parameters
#         REG_WR w_gain imm #{amp_reg}
#         REG_WR w_length imm #{length(self.wave)}
#         REG_WR w_env imm #0
#         REG_WR w_conf imm #{self.sig_gen_conf(outsel='input', mode='oneshot')}

#         REG_WR out_usr_time imm #{0}
#         WPORT_WR p{self.dac_port_mapping[self.dac_ch]} r_wave
#         """
#         return prog
