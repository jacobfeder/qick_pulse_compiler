from io import TriggerPort
from io import DataPort
from io import DACPort
from io import ADCPort
from io import TTPort
from io import QickIOMap

qick_spin_4by2 = QickIOMap(
    trigger_ports_mapping = {
        'PMOD0_0': TriggerPort(port=0),
        'PMOD0_1': TriggerPort(port=1),
        'PMOD0_2': TriggerPort(port=2),
        'PMOD0_3': TriggerPort(port=3),
        'PMOD0_4': TriggerPort(port=4),
        'PMOD0_5': TriggerPort(port=5),
        'PMOD0_6': TriggerPort(port=6),
        'PMOD0_7': TriggerPort(port=7),
        'PMOD1_0': TriggerPort(port=10),
        'PMOD1_1': TriggerPort(port=11),
        'PMOD1_2': TriggerPort(port=12),
        'PMOD1_3': TriggerPort(port=13),
        'PMOD1_4': TriggerPort(port=14),
        'PMOD1_5': TriggerPort(port=15),
        'PMOD1_6': TriggerPort(port=16),
        'PMOD1_7': TriggerPort(port=17),
    },
    data_ports_mapping = {
        'NA0': DataPort(port=0, bit=0)
        'NA1': DataPort(port=1, bit=0)
        'NA2': DataPort(port=2, bit=0)
        'NA3': DataPort(port=3, bit=0)
    },
    dac_ports_mapping = {
        'DAC_A': DACPort(port=0),
        'DAC_B': DACPort(port=1),
    },
    adc_ports_mapping = {

    },
    tt_ports_mapping = {

    },
)
