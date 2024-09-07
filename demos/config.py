from qpc.io import QickIO, QickIODevice

# RFSoC digital outputs
pmod0_0 = QickIO(channel_type='trig', channel='PMOD0_0', offset=0)
pmod0_1 = QickIO(channel_type='trig', channel='PMOD0_1', offset=0)
pmod0_2 = QickIO(channel_type='trig', channel='PMOD0_2', offset=0)
pmod0_3 = QickIO(channel_type='trig', channel='PMOD0_3', offset=0)
pmod0_4 = QickIO(channel_type='trig', channel='PMOD0_4', offset=0)
pmod0_5 = QickIO(channel_type='trig', channel='PMOD0_5', offset=0)
pmod0_6 = QickIO(channel_type='trig', channel='PMOD0_6', offset=0)
pmod0_7 = QickIO(channel_type='trig', channel='PMOD0_7', offset=0)

pmod1_0 = QickIO(channel_type='trig', channel='PMOD1_0', offset=0)
pmod1_1 = QickIO(channel_type='trig', channel='PMOD1_1', offset=0)
pmod1_2 = QickIO(channel_type='trig', channel='PMOD1_2', offset=0)
pmod1_3 = QickIO(channel_type='trig', channel='PMOD1_3', offset=0)

# RFSoC digital output "trigger" channels
trig_channels = {
    'laser_1':  QickIODevice(io=pmod0_4, offset=0),
    'laser_2':  QickIODevice(io=pmod0_5, offset=0),
    'laser_3':  QickIODevice(io=pmod0_6, offset=0),
}

dac_a = QickIO(channel_type='dac', channel='DAC_A', offset=-75e-9)

# channel mapping for RFSoC RF/DAC outputs
dac_channels = {
    'sample': QickIODevice(io=dac_a, offset=0),
}

adc_d = QickIO(channel_type='adc', channel='ADC_D', offset=0)

# channel mapping for RFSoC ADC inputs
adc_channels = {
    'pmt': QickIODevice(io=adc_d, offset=50e-9),
}