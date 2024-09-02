from numbers import Number

from qpc.board import qick_spin_4x2
from qpc.compiler import QPC
from qpc.loop import QickLoop, QickSweep
from qpc.pulse import Delay, RFSquarePulse, TrigPulse
from qpc.type import QickTime, QickFreq, QickReg, QickSweptReg, QickScope, QickCode

from config import trig_channels
from config import dac_channels

class T1(QickCode):
    def __init__(
        self,
        loops: int,
        tau_start: Number,
        tau_stop: Number,
        tau_step: Number,
        pi_time: Number,
        amp: int,
        freq: Number,
        init: QickCode,
        readout: QickCode,
        *args,
        mw_pre_padding: Number = 100e-9,
        mw_post_padding: Number = 100e-9,
        **kwargs
    ):
        """T1 sequence.

        Args:
            loops: Number of experiment repeats.
            tau_start: Start tau (s).
            tau_stop: Stop tau (s).
            tau_step: Tau step size (s).
            pi_time: Pi pulse duration.
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
            kwargs['name'] = 'T1'

        super().__init__(*args, **kwargs)

        with QickScope(code=self):
            tau_reg = QickSweptReg(
                start=QickTime(tau_start),
                stop=QickTime(tau_stop),
                step=QickTime(tau_step)
            )

            pi_pulse = RFSquarePulse(
                ch=dac_channels['sample'],
                length=pi_time,
                freq=freq,
                amp=amp,
                name='pi',
            )

            pi = \
                init + \
                Delay(length=mw_pre_padding, name='mw_pre_padding') + \
                Delay(length=tau_reg, name='tau 1') + \
                pi_pulse + \
                Delay(length=mw_post_padding, name='mw_post_padding') + \
                readout

            no_pi = \
                init + \
                Delay(length=mw_pre_padding, name='mw_pre_padding') + \
                Delay(length=tau_reg, name='tau_1') + \
                Delay(length=pi_time, name='pi_delay') + \
                Delay(length=mw_post_padding, name='mw_post_padding') + \
                readout

            tau_sweep = QickSweep(
                code=pi + no_pi,
                reg=tau_reg,
                inc_ref=True,
                name='tau sweep'
            )

            experiment_loop = QickLoop(
                code=tau_sweep,
                loops=loops,
                inc_ref=False,
                name='loop',
            )
            self.add(experiment_loop)

if __name__ == '__main__':
    with QPC(iomap=qick_spin_4x2, fake_soc=True) as qpc:
        code = T1(
            loops=10,
            tau_start=1e-6,
            tau_stop=100e-6,
            tau_step=10e-6,
            pi_time=20e-9,
            amp=1_000,
            freq=200e6,
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
