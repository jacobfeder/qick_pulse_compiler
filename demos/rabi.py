from numbers import Number

from qpc.board import qick_spin_4x2
from qpc.compiler import QPC
from qpc.loop import QickLoop, QickSweep
from qpc.pulse import Delay, RFPulse, TrigPulse
from qpc.type import QickTime, QickFreq, QickReg, QickSweptReg, QickScope, QickCode

from config import trig_channels
from config import dac_channels

class Rabi(QickCode):
    def __init__(
        self,
        loops: int,
        mw_start: Number,
        mw_stop: Number,
        mw_step: Number,
        amp: int,
        freq: Number,
        init: QickCode,
        readout: QickCode,
        *args,
        mw_pre_padding: Number = 100e-9,
        mw_post_padding: Number = 100e-9,
        **kwargs
    ):
        """Rabi sequence.

        Args:
            loops: Number of experiment repeats.
            mw_start: Microwave pulse initial length (s).
            mw_stop: Microwave pulse final length (s).
            mw_step: Microwave pulse length step size (s).
            amp: RF amplitude in DAC units.
            freq: Drive frequency (Hz).
            init: Initialization sequence.
            readout: Readout sequence.
            args: Additional arguments passed to super constructor.
            mw_pre_padding: Delay between falling edge of init sequence and
                rising edge of microwaves.
            mw_post_padding: Delay between falling edge of microwaves and
                rising edge of readout sequence.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        if 'name' not in kwargs:
            kwargs['name'] = 'rabi'

        super().__init__(*args, **kwargs)

        with QickScope(code=self):
            mw_reg = QickSweptReg(
                start=QickTime(mw_start),
                stop=QickTime(mw_stop),
                step=QickTime(mw_step)
            )

            mw_pulse = RFPulse(
                ch=dac_channels['sample'],
                length=mw_reg,
                freq=freq,
                amp=amp,
                name='mw',
            )

            w_mw = \
                init + \
                Delay(length=mw_pre_padding, name='mw_pre_padding') + \
                mw_pulse + \
                Delay(length=mw_post_padding, name='mw_post_padding') + \
                readout

            no_mw = \
                init + \
                Delay(length=mw_pre_padding, name='mw_pre_padding') + \
                Delay(length=mw_reg, name='no mw') + \
                Delay(length=mw_post_padding, name='mw_post_padding') + \
                readout

            mw_sweep = QickSweep(
                code=w_mw + no_mw,
                reg=mw_reg,
                inc_ref=True,
                name='microwave sweep'
            )

            experiment_loop = QickLoop(
                code=mw_sweep,
                loops=loops,
                inc_ref=False,
                name='loop',
            )
            self.add(experiment_loop)

if __name__ == '__main__':
    with QPC(iomap=qick_spin_4x2) as qpc:
        code = Rabi(
            loops=1,
            mw_start=10e-9,
            mw_stop=100e-9,
            mw_step=4e-9,
            amp=10_000,
            freq=200e6,
            init=TrigPulse(
                ch=trig_channels['laser_1'],
                length=0.9e-6,
                name='init'
            ),
            readout=TrigPulse(
                ch=trig_channels['laser_2'],
                length=0.9e-6,
                name='readout'
            ),
            soc=qpc.soc,
        )

        qpc.run(code)

        input('Press enter to exit\n')
