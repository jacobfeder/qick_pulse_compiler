"""A high-level interface for generating pulse sequences for 
the QICK tprocv2.

First, create an SSH tunnel to the RFSoC
ssh -C -L 8000:localhost:8000 xilinx@<ip>

Author: Jacob Feder
Date: 2024-08-16
"""
from __future__ import annotations
from numbers import Number
import logging
from pathlib import Path
from typing import Optional, Iterable, Dict, Any, Union

import Pyro4
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.PICKLE_PROTOCOL_VERSION=4
import qick
from qick import QickConfig
from qick.qick_asm import AbsQickProgram

try:
    from qick import QickSoc
except Exception:
    # script is not running on the RFSoC
    local_soc = False
else:
    # script is running on the RFSoC
    local_soc = True

from qick.tprocv2_assembler import Assembler

from bs3.instrument.rfsoc.boards import qick_boards

_logger = logging.getLogger(__name__)

# maximum immediate value in the tproc
MAX_IMM = 2**23 - 1

class QICKV2(AbsQickProgram):
    """Runs a QICK program for tprocv2."""
    def __init__(self,
        code: QickCode,
        board: QickBoard,
        ns_addr: str = 'localhost',
        ns_port: int = 8000,
        soc_proxy: str = 'rfsoc',
        print_prog: bool = True,
        ADC_debug: bool = False,
        readout: bool = False,
        readouts_per_loop: int = 1,
        **soc_kwargs
        ):
        """
        Args:
            code: Assembly code to run.
            board: RFSoC board that this code will be run on.
            ns_addr: Pyro nameserver address for the RFSoC.
            ns_port: Pyro nameserver port for the RFSoC.
            soc_proxy: Pyro SoC object name.
            print_prog: Whether to print out the program assembly before running.
            ADC_debug: Whether to output ADC debug pulses.
            readout: Whether to read out the ADCs.
            readouts_per_loop: Number of ADC readouts per experiment
            soc_kwargs: SoC object keyword args.

        """
        self.code = code
        self.ns_addr = ns_addr
        self.ns_port = ns_port
        self.soc_proxy = soc_proxy
        self.print_prog = print_prog
        self.ADC_debug = ADC_debug
        # whether we should readout data from the ADC FIFOs
        self.readout = readout
        # number of samples generated per loop of program
        self.readouts_per_loop = readouts_per_loop
        self.soc_kwargs = soc_kwargs

        # data received from rfsoc
        self.data = []
        # number of samples self.data
        self.data_len = 0

        self.board = board
        if local_soc:
            if 'bitfile' not in soc_kwargs:
                soc_kwargs['bitfile'] = str(Path(qick.__file__).parent / 'qick_4x2.bit')
            self.soc = QickSoc(**soc_kwargs)
        else:
            # connect to the pyro name server
            self.name_server = Pyro4.locateNS(host=ns_addr, port=ns_port)
            # load the soc proxy object
            self.soc = Pyro4.Proxy(self.name_server.lookup(soc_proxy))

        self.soccfg = QickConfig(self.soc.get_cfg())
        self.print_prog = print_prog

        super().__init__(self.soccfg)

        if board == qick_boards[self.soccfg['board']]:
            self.board = board
        else:
            raise ValueError(f'Board [{self.soccfg["board"]}] configuration not available.')

    def __enter__(self):
        self.run()
        return self

    def __exit__(self, *args):
        self.stop()

    def preprocess(self, code: QickCode):
        """Replace keys in the code block string with their string values.

        Args:
            code: The code block to preprocess.

        """
        reg = 0
        label = 0

        for key, val in code.kvp.items():
            if key != f'*{id(val)}*':
                raise RuntimeError('Internal preprocessor error - key and '
                    'value do not match')
            if isinstance(val, QickIO):
                code.asm = code.asm.replace(key, str(self.board.ports_mapping[val.channel_type][val.channel]))
            elif isinstance(val, QickIODevice):
                code.asm = code.asm.replace(key, str(self.board.ports_mapping[val.io.channel_type][val.io.channel]))
            elif isinstance(val, QickReg):
                scratch_reg = self.board.regs - 1
                if val.scratch:
                    code.asm = code.asm.replace(key, f'r{scratch_reg}')
                else:
                    if reg > self.board.regs - 2:
                        raise ValueError('Ran out of registers.')
                    else:
                        code.asm = code.asm.replace(key, f'r{reg}')
                        reg += 1
            elif isinstance(val, QickTime):
                code.asm = code.asm.replace(key, str(self.soc.us2cycles(val.time * 1e6)))
            elif isinstance(val, QickLabel):
                code.asm = code.asm.replace(key, f'{val.prefix}{label}')
                label += 1
            elif isinstance(val, QickFreq):
                code.asm = code.asm.replace(key, str(self.soc.freq2reg(val.freq / 1e6)))
            elif isinstance(val, QickSweepArange):
                if val.sweep_ch is not None:
                    if isinstance(val.sweep_ch, QickIODevice):
                        sweep_ch = self.board.ports_mapping[val.sweep_ch.io.channel_type][val.sweep_ch.io.channel]
                    elif isinstance(val.sweep_ch, QickIO):
                        sweep_ch = self.board.ports_mapping[val.sweep_ch.channel_type][val.sweep_ch.channel]
                    elif isinstance(val.sweep_ch, int):
                        sweep_ch = val.sweep_ch
                    else:
                        raise RuntimeError(f'[{val.sweep_ch}] must be a '
                            'QickIODevice, QickIO, or int.')
                else:
                    sweep_ch = None

                def convert_cycles(val_natural_units: Number, val_type: str, **kwargs):
                    """Convert the val in natural units into clock cycle units.

                    Args:
                        val_natural_units: Value to convert in natural units (Hz / s).
                        conversion_factor: Conversion factor between natural units and clock cycle units
                        val_type: 'time' or 'freq'.
                        kwargs: Additional kwargs to pass to conversion function.

                    """

                    # an exception will be raised if any start/stop/step error
                    # is greater than max_error after rounding to the nearest
                    # clock cycle
                    max_error = 0.05

                    # convert to clock cycles
                    if val_type == 'time':
                        conversion_factor = 1e6
                        val_cyc = self.soc.us2cycles(val_natural_units * conversion_factor, **kwargs)
                        one_cyc = self.soc.cycles2us(1, **kwargs)
                    elif val_type == 'freq':
                        conversion_factor = 1e-6
                        val_cyc = self.soc.freq2reg(val_natural_units * conversion_factor, **kwargs)
                        one_cyc = self.soc.reg2freq(1, **kwargs)
                    else:
                        raise ValueError('val_type must be "time" or "freq".')

                    # check that the error isn't > max_error
                    actual_val_natural_units = val_cyc * one_cyc / conversion_factor
                    if abs(actual_val_natural_units - val_natural_units) / val_natural_units > max_error:
                        raise ValueError(f'After rounding QickSweepArange '
                            f'[{val_natural_units:.3e}] to the nearest clock '
                            f'cycle [{actual_val_natural_units:.3e}], error is '
                            f'> {max_error*100:.1f}%.')

                    return val_cyc

                if isinstance(val.start, QickFreq):
                    start_cyc = convert_cycles(val_natural_units=val.start.freq, val_type='freq', gen_ch=sweep_ch)
                elif isinstance(val.start, QickTime):
                    start_cyc = convert_cycles(val_natural_units=val.start.time, val_type='time')
                elif isinstance(val.start, int):
                    start_cyc = val.start
                elif isinstance(val.start, QickReg):
                    start_cyc = None
                else:
                    raise RuntimeError('QickSweepArange sweep_type is '
                        '"freq" but "start" is not QickFreq, int, or '
                        'QickReg.')

                if isinstance(val.stop, QickFreq):
                    stop_cyc = convert_cycles(val_natural_units=val.stop.freq, val_type='freq', gen_ch=sweep_ch)
                elif isinstance(val.stop, QickTime):
                    stop_cyc = convert_cycles(val_natural_units=val.stop.time, val_type='time')
                elif isinstance(val.stop, int):
                    stop_cyc = val.stop
                elif isinstance(val.stop, QickReg):
                    stop_cyc = None
                else:
                    raise RuntimeError('QickSweepArange sweep_type is '
                        '"freq" but "stop" is not QickFreq, int, or '
                        'QickReg.')

                if isinstance(val.step, QickFreq):
                    step_cyc = convert_cycles(val_natural_units=val.step.freq, val_type='freq', gen_ch=sweep_ch)
                elif isinstance(val.step, QickTime):
                    step_cyc = convert_cycles(val_natural_units=val.step.time, val_type='time')
                elif isinstance(val.step, int):
                    step_cyc = val.step
                elif isinstance(val.step, QickReg):
                    step_cyc = None
                else:
                    raise RuntimeError('QickSweepArange sweep_type is '
                        '"freq" but "step" is not QickFreq, int, or '
                        'QickReg.')

                code.asm = code.asm.replace(key + 'start', str(start_cyc))
                code.asm = code.asm.replace(key + 'stop', str(stop_cyc))
                code.asm = code.asm.replace(key + 'step', str(step_cyc))
            elif isinstance(val, str):
                code.asm = code.asm.replace(key, val)
            else:
                raise ValueError(f'Value [{val}] for key [{key}] is not of a known type.')

    def run(self):
        self.load(self.code)
        if self.readout:
            self.begin_readout()
        else:
            # start the program
            self.soc.tproc.start()
        _logger.debug('running rfsoc prog...')

    def port(io: [QickIODevice, QickIO]) -> Union[int, Tuple]:
        """Return the port info associated with the given object.

        Args:
            io: QickIODevice or QickIO to return the port number of.

        """
        if isinstance(io, QickIODevice):
            channel_type = io.io.channel_type
            channel = io.io.channel
        elif isinstance(io, QickIO):
            channel_type = io.channel_type
            channel = io.channel
        else:
            raise ValueError('io must be a QickIODevice or QickIO but got '
                f'[{io}]')

        try:
            port_info = self.board.ports_mapping[channel_type][channel]
        except KeyError as err:
            raise ValueError(f'Qick board does not contain port [{channel}].') \
            from err

        if port_info not in self.board.ports[device.io.channel_type]:
            raise ValueError(f'The port [{port_info}] associated with the'
                'given device is not a valid port for the board.')

        return port_info

    def load(self, code: QickCode):
        """Load the program and configure the tproc.

        Args:
            code: The code block to load.

        """

        # preprocess the code to substitute keys for board-specific values
        self.preprocess(code)

        # get the user program and remove indentation
        asm = ''
        for line in code.asm.split('\n'):
            asm += line.lstrip() + '\n'

        # add a NOP to the beginning of the program
        setup_asm = 'NOP\n'
        # add a 1 ms inc_ref to the beginning of the program
        setup_asm += f'TIME inc_ref #{self.soc.us2cycles(1e3)}\n'
        # add an infinite loop to the end of the program
        teardown_asm = 'JUMP HERE\n'
        # add setup and teardown asm
        asm = setup_asm + asm + teardown_asm

        if self.print_prog:
            print('#################')
            print('#### Program ####')
            print('#################')
            for i, line in enumerate(asm.splitlines()):
                # add line numbers
                print(f'{i+1:03}: {line}')
            print('#################\n')

        # assemble program
        pmem, asm_bin = Assembler.str_asm2bin(asm)

        # stop any previously running program
        self.soc.tproc.reset()

        # configure the ADC readouts
        self.config_readouts(self.soc)
        self.config_bufs(self.soc, enable_avg=True, enable_buf=True)

        # load the new program into memory
        self.soc.tproc.Load_PMEM(asm_bin)

    def begin_readout(self, stride: int = 1):
        """Spawn the readout thread."""
        self.soc.start_readout(
            np.inf,
            ch_list=list(self.ro_chs),
            reads_per_rep=self.readouts_per_loop,
            stride=stride
        )

    def end_readout(self):
        """Stop the readout thread."""
        self.soc.streamer.stop_readout()

    def off_prog(self) -> QickCode:
        """A program that outputs 0's on all ports."""
        prog = QickCode(length=0)

        # write 0 waveform into all WPORTs
        for p in self.board.ports['DAC']:
            prog.rf_square_pulse(ch=p, time=0, length=1e-6, freq=100e6, amp=0)

        # disable all DPORTs
        prog.asm += '// write 0 into all DPORTs\n'
        prog.asm += 'REG_WR r0 imm #0\n'
        for port in self.board.data_ports():
            prog.asm += f'DPORT_WR p{port} reg r0\n'

        # disable all trig ports
        for port in self.board.ports['TRIG']:
            prog.trig(ch=port, state=False, time=0)

        return prog

    def stop(self):
        """Upload a program that outputs 0's on all ports."""
        if self.readout:
            self.end_readout()
        self.load(self.off_prog())
        self.soc.tproc.start()

    # TODO
    # the ADC readout code below was tested using an earlier version of
    # tproc v2, but is yet to adapted to more recent versions.

    # def _poll(self, totaltime, timeout):
    #     """Helper for read()."""
    #     # TODO ideally we could just read directly instead of using a certain duration
    #     packets = self.soc.poll_data(totaltime=totaltime, timeout=timeout)
    #     for packet in packets:
    #         packet_len, rest_of_packet = packet
    #         data, stats = rest_of_packet
    #         # the total number of samples in self.data
    #         self.data_len += packet_len
    #         # self.data is a list where each element is a 2D numpy array
    #         self.data.append(data)

    # def read(self, channel, min_readouts, max_readouts=np.inf, chunk_size=1):
    #     """Read from the ADC average buffer. This is only designed for
    #     reading a single ADC channel. TODO: implement multi-channel reading.

    #     Args:
    #         channel: Readout channel number.
    #         min_readouts: Minimum number of readouts to return. Will be rounded
    #             up to the nearest chunk_size.
    #         max_readouts: Maximum number of readouts to return.
    #         chunk_size: Return a number of readouts that is an integer multiple
    #             of this quantity.

    #     Returns:
    #         A list of numpy arrays containing the data. The list axes 
    #         correspond to the ADC channel number. For the numpy array,
    #         axis_0 = readout number, axis_1 = I/Q channels.
    #     """
    #     # round min_readouts up to the nearest chunk_size
    #     min_readouts = math.ceil(min_readouts / chunk_size) * chunk_size
    #     if min_readouts > max_readouts:
    #         raise ValueError(f'min_readouts {min_readouts} adjusted for chunk size is greater than {max_readouts}.')

    #     # collect readout data until we reach min_readouts
    #     while self.data_len < min_readouts:
    #         self._poll(totaltime = 0.01, timeout = 0.01)
    #     # read a bit longer if there is more data than min_readouts
    #     self._poll(totaltime = 0.01, timeout = 0.01)

    #     # cap the actual number of readouts to max_readouts
    #     if self.data_len > max_readouts:
    #         num_readouts = max_readouts
    #     else:
    #         num_readouts = self.data_len
    #     # round down to the nearest chunk_size
    #     num_readouts = num_readouts - (num_readouts % chunk_size)

    #     # numpy data buffer to return to the user
    #     d_buf = np.zeros((num_readouts, 2))
    #     # keep track of the number of readouts currently in d_buf
    #     copied_readouts = 0
    #     # copy from self.data into the data buffer
    #     while copied_readouts < num_readouts:
    #         # remove the oldest data packet
    #         packet = self.data.pop(0)[0]
    #         # number of data entries in data packet
    #         packet_len = packet.shape[0]
    #         # readouts remaining to be copied
    #         readouts_remaining = num_readouts - copied_readouts
    #         if readouts_remaining >= packet_len:
    #             # the whole packet can be copied into the buffer
    #             d_buf[copied_readouts:copied_readouts + packet_len, :] = packet
    #             copied_readouts += packet_len
    #             self.data_len -= packet_len
    #         else:
    #             # copy the remaining readouts required into the buffer
    #             d_buf[copied_readouts:, :] = packet[:readouts_remaining, :]
    #             copied_readouts += readouts_remaining
    #             self.data_len -= readouts_remaining
    #             # put the rest of the packet back into self.data
    #             self.data.insert(0, [packet[readouts_remaining:, :]])

    #     # find the ADC readout lengths
    #     rol = self.ro_chs[self.adc_port_mapping[channel]]['length']

    #     _logger.debug(f'read [{num_readouts}] from rfsoc')
    #     # divide the sum buffer data by the number of samples per readout so
    #     # that the average ADC value is returned
    #     d_buf = d_buf / rol
    #     return d_buf
