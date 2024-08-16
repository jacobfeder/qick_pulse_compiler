"""Port mapping and offset handling for the inputs / outputs of different
QICK boards / firmwares."""

from typing import Iterable, Dict, List
from numbers import Number

class QickIO:
    """Represents an RFSoC input / output."""
    def __init__(
        self,
        channel_type: str,
        channel: Union[str, tuple],
        offset: Number
    ):
        """
        Args:
            channel_type: One of 'TRIG', 'DATA', 'DAC', 'ADC', 'TT'.
            channel: IO channel name (e.g. 'PMOD0_0', 'DAC_A')
            offset: Offset that this IO adds (s).

        """
        channel_types = ['TRIG', 'DATA', 'DAC', 'ADC', 'TT']
        if channel_type in channel_types:
            self.channel_type = channel_type
        else:
            raise ValueError(f'channel_type must be one of {channel_types} '
                f'but got {channel_type}.')
        self.channel = channel
        self.offset = offset

class QickIODevice:
    """Represents a device connected to an RFSoC input / output."""
    def __init__(self, io: QickIO, offset: Number):
        """
        Args:
            io: RFSoC IO connected to the device.
            offset: Offset that this device adds (s).

        """
        self.io = io
        self.offset = offset

    def total_offset(self) -> float:
        """Return the total offset of the device including the IO port."""
        return self.offset + self.io.offset

TriggerPort = namedtuple('TriggerPort', ['port', 'clk'])
DataPort = namedtuple('DataPort', ['port', 'bit', 'clk'])
DACPort = namedtuple('DACPort', ['port', 'clk'])
ADCPort = namedtuple('ADCPort', ['port', 'clk'])
TTPort = namedtuple('TTPort', ['port', 'clk'])

class QickBoard:
    def __init__(self,
        trigger_ports_mapping: Dict[str, int],
        data_ports_mapping: Dict,
        dac_ports_mapping: Dict,
        adc_ports_mapping: Dict,
        tt_ports_mapping: Dict,
        regs: int,
        tproc_clk: Number,
    ):
        """Contains the settings specific to a QICK firmware.

        Args:
            trigger_ports_mapping: Mapping between trigger port names and numbers.
            data_ports_mapping: Mapping between data port names and numbers.
            dac_ports_mapping: Mapping between DAC port names and numbers.
            adc_ports_mapping: Mapping between ADC port names and numbers.
            tt_ports_mapping: Mapping between time tagger port names and numbers.
            regs: Number of registers.
        """
        self.port_mapping = {
            'TRIG': trigger_ports_mapping,
            'DATA': data_ports_mapping,
            'DAC': dac_ports_mapping,
            'ADC': adc_ports_mapping,
            'TT': tt_ports_mapping,
        }
        self.regs = regs
        self.tproc_clk = tproc_clk

    def data_ports(self) -> List:
        """Return a list of all unique data ports."""
        dps = []
        for port, bit in self.ports['DATA']:
            if port not in dps:
                dps.append(port)
        return dps

data_ports = []
# 4 data ports
for port in range(3):
    # TODO
    # 10? bits per data port
    for bit in range(10):
        data_ports.append()

# TODO need to check all these
qick_spin_4by2_tproc_clk = 2e-9
qick_spin_4by2 = QickBoard(
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
    data_ports = data_ports,
    data_ports_mapping = {
        # name : (data port number, bit within data port)
        'NA0': DataPort(port=0, bit=0, clk=qick_spin_4by2_tproc_clk)
        'NA1': DataPort(port=1, bit=0, clk=qick_spin_4by2_tproc_clk)
        'NA2': DataPort(port=2, bit=0, clk=qick_spin_4by2_tproc_clk)
        'NA3': DataPort(port=3, bit=0, clk=qick_spin_4by2_tproc_clk)
    },
    dac_ports = [0, 1],
    dac_ports_mapping = {
        'DAC_A': 0,
        'DAC_B': 1,
    },
    adc_ports = [],
    adc_ports_mapping = {

    },
    tt_ports = [],
    tt_ports_mapping = {

    },
    regs = 16
)

qick_boards = {
    'RFSoC4x2': qick_spin_4by2,
}