from numbers import Number

from qpc.compiler import QPC
from qpc.board import qick_spin_4x2
from qpc.io import QickIO, QickIODevice
from qpc.loop import QickLoop, QickSweep
from qpc.pulse import Delay, TrigConst, TrigPulse, RFPulse
from qpc.type import QickCode, QickScope, QickReg, QickSweptReg, QickTime

pmod0_0 = QickIO(channel_type='trig', channel='PMOD0_0', offset=0)
pmod0_1 = QickIO(channel_type='trig', channel='PMOD0_1', offset=0)
dac_0 = QickIO(channel_type='dac', channel='DAC_A', offset=0)
dac_1 = QickIO(channel_type='dac', channel='DAC_B', offset=0)

device1 = QickIODevice(io=pmod0_0, offset=1e-6)

def test1():
    code = QickCode(name='code')
    with QickScope(code):
        time1 = QickTime(1e-6)
        time2 = QickTime(2e-6)

        reg0 = QickReg()
        reg0.assign(time1)

        reg1 = QickReg()
        reg1.assign(reg0 + time2)

    return code

def test2():
    code = QickCode(name='code')
    with QickScope(code):
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
    code = QickCode(name='c1')
    with QickScope(code):
        time10 = QickTime(10e-6)
        time11 = QickTime(11e-6)
        code.trig(ch=0, state=True, time=time10)
        code.trig(ch=0, state=False, time=time11)

    return code

def test4():
    code1 = QickCode(name='c1')
    with QickScope(code1):
        time10 = QickTime(10e-6)
        time11 = QickTime(11e-6)
        code1.trig(ch=0, state=True, time=time10)
        code1.trig(ch=0, state=False, time=time11)

    code2 = QickCode(name='c2')
    with QickScope(code2):
        time12 = QickTime(12e-6)
        time13 = QickTime(13e-6)
        code2.trig(ch=1, state=True, time=time12)
        code2.trig(ch=1, state=False, time=time13)

    return code1 + code2

def test5():
    return TrigPulse(ch=0, length=2e-6)

def test6():
    t1 = TrigPulse(ch=0, length=1e-6, name='t1')
    t2 = TrigPulse(ch=1, length=2e-6, name='t2')
    return t1 + t2

def test7():
    t1 = TrigPulse(ch=0, length=1e-6, name='t1')
    t2 = TrigPulse(ch=1, length=2e-6, name='t2')
    return t1 | t2

def test8():
    rf1 = RFPulse(ch=0, length=1e-6, freq=100e6, amp=10_000)
    return rf1

def test9():
    rf1 = RFPulse(ch=0, length=1e-6, freq=100e6, amp=10_000, name='rf1')
    rf2 = RFPulse(ch=1, length=2e-6, freq=None, amp=None, name='rf2')
    return rf1 + rf2

def test10():
    t1 = TrigPulse(ch=0, length=3e-6, name='t1')
    return QickLoop(code=t1, loops=5, inc_ref=True)

def test11():
    t1 = TrigPulse(ch=0, length=3e-6, name='t1')
    t2 = TrigPulse(ch=0, length=5e-6, name='t2')
    return QickLoop(code=t1 + t2, loops=5, inc_ref=True, name='loop')

def test12():
    code = QickCode(name='code')
    with QickScope(code):
        len_reg = QickReg()
        len_reg.assign(QickTime(3e-6))
        t1 = TrigPulse(ch=0, length=len_reg, name='t1')
        code.add(t1)
    return code

def test13():
    code = QickCode(name='code')
    with QickScope(code):
        len_reg = QickReg()
        len_reg.assign(QickTime(3e-6))
        t1 = TrigPulse(ch=0, length=len_reg, name='t1')
        t2 = TrigPulse(ch=1, length=5e-6, name='t2')
        code.add(t1)
        code.add(t2)
    return code

def test14():
    code = QickCode(name='code')
    with QickScope(code):
        len_reg = QickReg()
        len_reg.assign(QickTime(3e-6))
        t1 = TrigPulse(ch=0, length=len_reg, name='t1')
        t2 = TrigPulse(ch=1, length=5e-6, name='t2')
        t3 = TrigPulse(ch=0, length=1e-6, name='t3')
        code.add(t1)
        code.add(t2)
        code.add(t3)
    return code

def test15():
    code = QickCode(name='code')
    with QickScope(code):
        len_reg = QickReg()
        len_reg.assign(QickTime(3e-6))
        t1 = TrigPulse(ch=0, length=len_reg, name='t1')
        t2 = TrigPulse(ch=1, length=5e-6, name='t2')
        code.add(t2)
        code.add(t1)
        code.add(t2)
    return code

def test16():
    code = QickCode(name='code')
    with QickScope(code):
        len_reg = QickReg()
        len_reg.assign(QickTime(3e-6))
        t1 = TrigPulse(ch=0, length=len_reg, name='t1')
        t2 = TrigPulse(ch=1, length=5e-6, name='t2')
        code.add(t1)
        code.add(t2)
    return QickLoop(code=code, loops=5, inc_ref=True, name='loop')

def test17():
    return TrigPulse(ch=pmod0_0, length=3e-6, name='t1')

def test18():
    return TrigPulse(ch=device1, length=3e-6, name='t1')

def test19():
    code = QickCode(name='code')
    with QickScope(code):
        swept_reg = QickSweptReg(
            start=QickTime(2e-6),
            stop=QickTime(5e-6),
            step=QickTime(1e-6)
        )
        t1 = TrigPulse(ch=0, length=swept_reg, name='t1')
        code.add(QickSweep(code=t1, reg=swept_reg, inc_ref=True, name='sweep'))
    return code

def test20():
    code = QickCode(name='code')
    with QickScope(code):
        swept_reg = QickSweptReg(
            start=QickTime(2e-6),
            stop=QickTime(5e-6),
            step=QickTime(1e-6)
        )
        t1 = TrigPulse(ch=0, length=swept_reg, name='t1')
        t2 = TrigPulse(ch=1, length=QickTime(10e-6), name='t2')
        code.add(QickSweep(code=t1 + t2, reg=swept_reg, inc_ref=True, name='sweep'))
    return code

def test21():
    code = QickCode(name='code')
    with QickScope(code):
        r0 = QickReg(val=QickTime(0e-9))
        r1 = QickReg(val=QickTime(1e-9))
        r2 = QickReg()
        exp = \
            (r0 + QickTime(4e-9)) + \
            (r0 + QickTime(5e-9)) + \
            (r0 + r1) + \
            (r0 + QickTime(1e-9))
        r2.assign(exp)
    return code

if __name__ == '__main__':
    with QPC(iomap=qick_spin_4x2, fake_soc=False) as qpc:
        qpc.run(test8())
        input('Press enter to exit\n')
