from numbers import Number

from nspyre import nspyre_init_logger

from qpc.compiler import QPC
from qpc.loop import QickLoop
from qpc.pulse import Delay, TrigConst, TrigPulse, RFSquarePulse
from qpc.types import QickCode, QickContext, QickReg, QickTime

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
        reg5.assign((reg1 + reg4) + (reg2 + time2))

    return code

def test3():
    code1 = QickCode(name='c1')
    with QickContext(code1):
        time0 = QickTime(10e-6)
        time1 = QickTime(11e-6)
        code1.trig(ch=0, state=True, time=time0)
        code1.trig(ch=0, state=False, time=time1)

    code2 = QickCode(name='c2')
    with QickContext(code2):
        time2 = QickTime(12e-6)
        time3 = QickTime(13e-6)
        code2.trig(ch=1, state=True, time=time2)
        code2.trig(ch=1, state=False, time=time3)

    return code1 + code2

def test4():
    return TrigPulse(ch=1, length=2e-6)

def test5():
    t1 = TrigPulse(ch=0, length=1e-6, name='t1')
    t2 = TrigPulse(ch=1, length=2e-6, name='t2')
    return (t1 + t2)

def test6():
    t1 = TrigPulse(ch=0, length=1e-6, name='t1')
    t2 = TrigPulse(ch=1, length=2e-6, name='t2')
    return t1 | t2

def test7():
    rf1 = RFSquarePulse(ch=0, length=1e-6, freq=100e6, amp=1_000)
    return rf1

def test8():
    rf1 = RFSquarePulse(ch=0, length=1e-6, freq=100e6, amp=1_000, name='rf1')
    rf2 = RFSquarePulse(ch=0, length=2e-6, freq=None, amp=None, time=5e-6, name='rf2')

    return rf1 + rf2

def test9():
    t1 = TrigPulse(ch=0, length=3e-6, name='t1')
    return QickLoop(code=t1, loops=5, inc_ref=True)

def test10():
    t1 = TrigPulse(ch=0, length=3e-6, name='t1')
    t2 = TrigPulse(ch=0, length=5e-6, name='t2')
    return QickLoop(code=t1 + t2, loops=5, inc_ref=True, name='loop')

if __name__ == '__main__':
    import logging

    nspyre_init_logger(log_level=logging.INFO)

    with QPC(fake_soc=True) as qpc:
        qpc.run(test10())
        input('Press enter to exit\n')
