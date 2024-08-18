from numbers import Number

from nspyre import nspyre_init_logger

from qpc.types import QickCode, QickContext, QickReg, QickTime
from qpc.compiler import QickPulseCompiler

# class Test(QickCode):
#     def __init__(
#         self,
#     ):
#         super().__init__(length=0)

#         with QickContext(self):
#             pl = QickTime(1e-6)
#             reg1 = QickReg()
#             exp = 

#         # self.add(experiment_loop)

if __name__ == '__main__':
    import logging

    nspyre_init_logger(log_level=logging.INFO)

    code = QickCode()
    with QickContext(code):
        time1 = QickTime(1e-6)
        time2 = QickTime(2e-6)

        reg1 = QickReg()
        reg1.assign(time1)

        reg2 = QickReg()
        reg2.assign(reg1 + time2)

    with QickPulseCompiler(fake_soc=True) as qpc:
        qpc.load(code)
        input('Press enter to exit\n')
