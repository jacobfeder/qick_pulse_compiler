from numbers import Number

from qpc.board import qick_spin_4x2
from qpc.compiler import QPC
from qpc.loop import QickLoop, QickSweep
from qpc.pulse import Delay, RFSquarePulse, TrigPulse
from qpc.type import QickTime, QickFreq, QickReg, QickSweptReg, QickScope, QickCode

from config import trig_channels
from config import dac_channels

class PulsedODMR(QickCode):
    def __init__(
        self,
        loops: int,
        amp: int,
        freq_start: Number,
        freq_stop: Number,
        freq_step: Number,
        init: QickCode,
        readout: QickCode,
        *args,
        mw_len: Number = 1e-6,
        mw_pre_padding: Number = 100e-9,
        mw_post_padding: Number = 100e-9,
        **kwargs
    ):
        """Pulsed ODMR sequence.

        Args:
            loops: Number of experiment repeats.
            amp: RF amplitude in DAC units.
            freq_start: Start frequency (Hz).
            freq_stop: Stop frequency (Hz).
            freq_step: Frequency step size (Hz).
            init: Initialization sequence.
            readout: Readout sequence.
            args: Additional arguments passed to super constructor.
            mw_len: Length of microwave pulse (s).
            mw_pre_padding: Delay between falling edge of init sequence and
                rising edge of microwaves.
            mw_post_padding: Delay between falling edge of microwaves and
                rising edge of readout sequence.
            kwargs: Additional keyword arguments passed to super constructor.
        """
        if 'name' not in kwargs:
            kwargs['name'] = 'pulsed ODMR'

        super().__init__(*args, **kwargs)

        with QickScope(code=self):
            freq_reg = QickSweptReg(
                start=QickFreq(freq_start),
                stop=QickFreq(freq_stop),
                step=QickFreq(freq_step)
            )

            mw_on = \
                init + \
                Delay(length=mw_pre_padding, name='mw_pre_padding') + \
                RFSquarePulse(ch=dac_channels['sample'], length=mw_len, freq=freq_reg, amp=amp) + \
                Delay(length=mw_post_padding, name='mw_post_padding') + \
                readout

            mw_off = \
                init + \
                Delay(length=mw_pre_padding, name='mw_pre_padding') + \
                Delay(length=mw_len, name='mw_delay') + \
                Delay(length=mw_post_padding, name='mw_post_padding') + \
                readout

            experiment = mw_on + mw_off

            freq_sweep = QickSweep(
                code=experiment,
                reg=freq_reg,
                inc_ref=True,
                name='sweep',
            )

            experiment_loop = QickLoop(
                code=freq_sweep,
                loops=loops,
                inc_ref=False,
                name='loop',
            )

        self.add(experiment_loop)

if __name__ == '__main__':
    with QPC(iomap=qick_spin_4x2, fake_soc=True) as qpc:
        code = PulsedODMR(
            loops=10,
            amp=1_000,
            freq_start=50e6,
            freq_stop=151e6,
            freq_step=50e6,
            init=TrigPulse(
                ch=trig_channels['laser_1'],
                length=1e-6,
                name='init'
            ),
            readout=TrigPulse(
                ch=trig_channels['laser_2'],
                length=1e-6,
                name='readout'
            ),
            soccfg=qpc.soccfg,
        )

        qpc.run(code)

        input('Press enter to exit\n')
