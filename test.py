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

def test1():
    code = QickCode()
    with QickContext(code):
        time1 = QickTime(1e-6)
        time2 = QickTime(2e-6)

        reg0 = QickReg()
        reg0.assign(time1)

        reg1 = QickReg()
        reg1.assign(reg0 + time2)

    return code

def test2():
    code = QickCode()
    with QickContext(code):
        time0 = QickTime(0e-6)
        time1 = QickTime(1e-6)
        time2 = QickTime(2e-6)
        time3 = QickTime(3e-6)

        reg0 = QickReg()
        reg0.assign(time0)
        reg1 = QickReg()
        reg1.assign(time1)
        reg2 = QickReg()
        reg2.assign(time2)
        reg3 = QickReg()
        reg3.assign(time3)

        reg4 = QickReg()
        reg4.assign((reg0 + reg3) + (reg1 + reg2))

        reg5 = QickReg()
        reg5.assign(reg4 + reg4)

    return code

if __name__ == '__main__':
    import logging

    nspyre_init_logger(log_level=logging.INFO)

    with QickPulseCompiler(fake_soc=True) as qpc:
        qpc.load(test2())
        input('Press enter to exit\n')
