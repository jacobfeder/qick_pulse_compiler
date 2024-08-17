from numbers import Number

from nspyre import nspyre_init_logger

from qpc.types import QickCode, QickContext, QickReg, QickTime
from qpc.compiler import QickPulseCompiler

class Test(QickCode):
    def __init__(
        self,
    ):
        super().__init__(length=0)

        with QickContext(self):
            pl = QickTime(time=1e-6)
            reg1 = QickReg()

        # self.add(experiment_loop)

if __name__ == '__main__':
    import logging

    nspyre_init_logger(log_level=logging.INFO)

    code = Test()

    with QickPulseCompiler(code, fake_soc=True) as prog:
        input('Press enter to exit\n')
