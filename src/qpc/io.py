"""Port mapping and offset handling for the inputs / outputs of different
QICK boards / firmwares."""

from collections import namedtuple
from typing import Dict, List, Union
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
            channel_type: One of 'trig', 'data', 'dac', 'adc', 'tt'.
            channel: IO channel name (e.g. 'PMOD0_0', 'DAC_A')
            offset: Offset that this IO adds (s).

        """
        channel_types = ['trig', 'data', 'dac', 'adc', 'tt']
        if channel_type in channel_types:
            self.channel_type = channel_type
        else:
            raise ValueError(f'channel_type must be one of {channel_types} '
                f'but got {channel_type}.')
        self.channel = channel
        self.offset = offset

    def key(self) -> str:
        return f'*{self.channel}*'

class QickIODevice(QickIO):
    """Represents a device connected to an RFSoC input / output."""
    def __init__(self, io: QickIO, offset: Number):
        """
        Args:
            io: RFSoC IO connected to the device.
            offset: Offset that this device adds (s).

        """
        super().__init__(
            channel_type=io.channel_type,
            channel=io.channel,
            offset=io.offset + offset)

TriggerPort = namedtuple('TriggerPort', ['port'])
DataPort = namedtuple('DataPort', ['port', 'bit'])
DACPort = namedtuple('DACPort', ['port'])
ADCPort = namedtuple('ADCPort', ['port'])
TTPort = namedtuple('TTPort', ['port'])

class QickIOMap:
    def __init__(self,
        trigger_ports_mapping: Dict[str, TriggerPort],
        data_ports_mapping: Dict[str, DataPort],
        dac_ports_mapping: Dict[str, DACPort],
        adc_ports_mapping: Dict[str, ADCPort],
        tt_ports_mapping: Dict[str, TTPort],
    ):
        """Contains a mapping between the QICK firmware I/O ports and
        user-friendly port names.

        Args:
            trigger_ports_mapping: Mapping between trigger port names and numbers.
            data_ports_mapping: Mapping between data port names and numbers.
            dac_ports_mapping: Mapping between DAC port names and numbers.
            adc_ports_mapping: Mapping between ADC port names and numbers.
            tt_ports_mapping: Mapping between time tagger port names and numbers.
        """
        self.mappings = {
            'trig': trigger_ports_mapping,
            'data': data_ports_mapping,
            'dac': dac_ports_mapping,
            'adc': adc_ports_mapping,
            'tt': tt_ports_mapping,
        }

    def _ports(self, port_mapping) -> List:
        ports = []
        for p in port_mapping.values():
            if p.port not in ports:
                ports.append(p.port)
        return ports

    def trigger_ports(self) -> List:
        """Return a list of all unique trigger ports."""
        return self._ports(self.mappings['trig'])

    def data_ports(self) -> List:
        """Return a list of all unique data ports."""
        return self._ports(self.mappings['data'])

    def dac_ports(self) -> List:
        """Return a list of all unique dac ports."""
        return self._ports(self.mappings['dac'])

    def adc_ports(self) -> List:
        """Return a list of all unique adc ports."""
        return self._ports(self.mappings['adc'])

    def tt_ports(self) -> List:
        """Return a list of all unique time tagger ports."""
        return self._ports(self.mappings['tt'])
