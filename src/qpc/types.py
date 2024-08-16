


class QickObject:
    """A QICK object to be used with the QickCode preprocessor."""
    def __init__(
            self,
            code: Optional[QickCode] = None,
            board: Optional[QickBoard] = None,
        ):
        """
        Args:
            code: Code block that this object is associated with.
            board: RFSoC board that this object will be run on.

        """
        self.code = code
        self.board = board

    def __str__(self) -> str:
        if self.code is None:
            raise RuntimeError(f'QickObject [{self}] was never associated with '
                'a QickCode block.')
        else:
            return self.code.key(self)

class QickReg(QickObject):
    """Represents a register in the tproc."""
    def __init__(self, scratch: bool = False, **kwargs):
        """
        Args:
            scratch: If True, this is a temporary / scratch register.
            kwargs: Keyword arguments to pass to QickObject constructor.

        """
        super().__init__(**kwargs)
        self.scratch = scratch

# TODO
# class QickExpression(QickObject):
#     """Represents a mathematical expression containing registers and numbers."""
#     def __init__(self):
#         """
#         Args:
#             code: Code block that this expression is associated with.

#         """
#         self.code = code
#         self.left_operand = None
#         self.right_operand = None
#         self.operator = None

class QickTime(QickObject):
    """Represents a time in seconds, which will be converted into tproc
    clock units."""
    def __init__(self, time: Number, relative: bool = True, **kwargs):
        """
        Args:
            time: Time (s).
            relative: If True, this represents a time relative to the start of
                its associated code block.
            kwargs: Keyword arguments to pass to QickObject constructor.

        """
        super().__init__(**kwargs)

        if not isinstance(time, Number):
            raise ValueError('time must be a number.')
        self.time = time
        self.relative = relative

    def __add__(self, other) -> QickTime:
        if isinstance(other, QickTime):
            if self.code != other.code:
                raise RuntimeError('Tried to add two times associated with'
                    'different code blocks.')
            if self.relative != other.relative:
                raise RuntimeError('Tried to add a relative time with an '
                    'absolute time.')
            return QickTime(time=self.time + other.time, code=self.code)
        elif isinstance(other, Number):
            return QickTime(time=self.time + other, code=self.code)
        else:
            return NotImplemented

    def __radd__(self, other) -> QickTime:
        return self.__add__(other)

class QickFreq(QickObject):
    """Represents a frequency in Hz."""
    def __init__(self, freq: Number, **kwargs):
        """
        Args:
            freq: Frequency (Hz).
            kwargs: Keyword arguments to pass to QickObject constructor.

        """
        super().__init__(**kwargs)
        self.freq = freq

class QickSweepArange(QickObject):
    """Represents the arguments to a swept variable."""
    def __init__(
            self,
            start: Union[QickTime, QickFreq, int, QickReg],
            stop: Union[QickTime, QickFreq, int, QickReg],
            step: Union[QickTime, QickFreq, int, QickReg],
            sweep_type: str,
            sweep_ch: Optional[Union[QickIODevice, QickIO, int]] = None,
            **kwargs
        ):
        """Represents the arguments to a variable that should be swept over
        a range inside a loop.

        Args:
            start: Start value of swept variable.
            stop: Stop value of swept variable.
            step: Step size of swept variable.
            sweep_type: Should be 'freq' or 'time'.
            sweep_ch: If sweep_type is 'freq', this is the associated
                RF channel.
            kwargs: Keyword arguments to pass to QickObject constructor.

        """
        super().__init__(**kwargs)
        self.start = start
        self.stop = stop
        self.step = step
        self.sweep_type = sweep_type
        if sweep_type == 'freq' and sweep_ch is None:
            raise ValueError(f'sweep_type is "freq" but no sweep_ch is '
                'specified.')
        self.sweep_ch = sweep_ch

    def __str__(self):
        raise ValueError('QickSweepArange cannot be converted into a string'
            'key. Use start_key(), stop_key(), and step_key().')

    def start_key(self) -> str:
        return self.code.key(obj=self, subid='start')

    def stop_key(self) -> str:
        return self.code.key(obj=self, subid='stop')

    def step_key(self) -> str:
        return self.code.key(obj=self, subid='step')

class QickLabel(QickObject):
    """Represents an assembly code label."""
    def __init__(self, prefix: str, **kwargs):
        """
        Args:
            prefix: Label prefix.
            kwargs: Keyword arguments to pass to QickObject constructor.

        """
        super().__init__(**kwargs)
        self.prefix = prefix

class QickCode:
    """Represents a segment of QICK code. There are two components. The first
    is a string containing assembly code. The second is a key-value pair ("kvp")
    dictionary containing string keys and object values. In the assembly code,
    there are special string keys surrounded by *, e.g. *12345*. These are keys
    to the kvp dictionary and will be replaced by the preprocessor before the
    code is uploaded to the board.

    """
    def __init__(
            self,
            length: Number,
            offset: Number = 0,
            name: Optional[str] = None,
            board: Optional[QickBoard] = None,
        ):
        """
        Args:
            length: The length of this code block (s).
            offset: Offset to add to all pulses in this code block (s).
            name: Optional name that will be added as a comment at the top of
                the code segment.
            board: RFSoC board that this code will be run on.

        """
        # assembly code string
        self.asm = ''
        self.name = name
        if self.name is not None:
            self.asm += f'// ---------------\n// {self.name}\n// ---------------\n'
        # key-value pairs for the preprocessor
        self.kvp = {}

        self.length = length
        self.offset = offset
        self.board = board

    def key(self, obj: Any, subid: Optional[str] = None) -> str:
        """Get the key associated with the given object, or create a new one
        if it does not exist.

        Args:
            obj: The object to be handled by the preprocessor.
            subid: A string representing some additional identifier within obj.

        Returns:
            A unique string representing this object.

        """
        dict_key = f'*{id(obj)}*'
        if dict_key not in self.kvp:
            self.kvp[dict_key] = obj

        if subid is None:
            return dict_key
        else:
            return dict_key + subid

    def associate_code(self, obj):
        """Check if the given object has an associated code block. If it
        doesn't, associate it with this code block.

        Args:
            obj: The object to process.

        """
        if isinstance(obj, QickObject):
            if obj.code is None:
                obj.code = self

    def deembed_io(self, io: Optional[Union[QickIODevice, QickIO, int]]) -> Tuple:
        """Consolidate all of the offsets relevant to the provided IO.

        Args:
            io: QickIODevice, QickIO, or port to calculate the offsets of.

        Returns:
            A tuple containing (port, offset). The port is the firmware port
            number and the offset is a QickTime.

        """
        offset = self.offset
        if isinstance(io, QickIODevice):
            port = self.key(io)
            offset += io.total_offset()
        elif isinstance(io, QickIO):
            port = self.key(io)
            offset += io.offset
        else:
            port = io
        offset = QickTime(time=offset, relative=False, code=self)

        return port, offset

    def trig(
            self,
            ch: Union[QickIODevice, QickIO, int],
            state: bool,
            time: Optional[Union[QickTime, Number, QickReg]],
        ):
        """Set a trigger port high or low.

        Args:
            ch: QickIODevice, QickIO, or port to trigger.
            state: Whether to set the trigger state True or False.
            time: Time at which to set the state. Pass a time (s) or a register
                containing the time in cycles. Set to None to use the value
                currently in out_usr_time.

        """
        port, offset = self.deembed_io(ch)

        asm = f'// Setting trigger port {port} to {state}\n'
        if time is not None:
            # if time is not associated with any code block, associate it now
            self.associate_code(time)

            if isinstance(time, QickReg):
                asm += f'REG_WR out_usr_time op -op({time} + #{offset})\n'
            elif isinstance(time, QickTime) or isinstance(time, Number):
                asm += f'REG_WR out_usr_time imm #{time + offset}\n'                
            else:
                raise ValueError(f'time must be a QickTime, number, or QickReg.')

        if state:
            asm += f'TRIG set p{port}\n'
        else:
            asm += f'TRIG clr p{port}\n'

        self.asm += asm

    def rf_square_pulse(
            self,
            ch: Union[QickIODevice, QickIO, int],
            time: Optional[Union[QickTime, Number, QickReg]],
            length: Optional[Union[Number, QickReg]],
            freq: Optional[Union[QickFreq, Number, QickReg]] = None,
            amp: Optional[int] = None,
        ):
        """Generate a square RF pulse.

        Args:
            ch: QickIODevice, QickIO, or port to output an RF pulse.
            time: Time at which to set the state. Pass a time (s) or a register
                containing the time in cycles. Set to None to use the value
                currently in out_usr_time.
            length: Length of the RF pulse. Pass a time (s) or a register
                containing the time in cycles. Set to None to use the value
                currently stored in w_length.
            freq: RF frequency of the pulse. Pass a frequency (Hz) or a register
                containing the frequency in cycles. Set to None to use the value
                currently stored in w_freq.
            amp: RF amplitude. Pass an integer (-32,768 to 32,767) or a register
                containing the amplitude. Set to None to use the value currently
                stored in w_gain.

        """
        port, offset = self.deembed_io(ch)

        asm = f'// Pulsing RF port {port}\n'

        if time is not None:
            # if time is not associated with any code block, associate it now
            self.associate_code(time)

            if isinstance(time, QickReg):
                asm += f'REG_WR out_usr_time op -op({time} + #{offset})\n'
            elif isinstance(time, QickTime) or isinstance(time, Number):
                asm += f'REG_WR out_usr_time imm #{time + offset}\n'                
            else:
                raise ValueError(f'time must be a QickTime, number, or QickReg.')

        if length is not None:
            # if length is not associated with any code block, associate it now
            self.associate_code(length)

            if isinstance(length, QickReg):
                asm += f"""REG_WR w_length op -op({length})\n"""
            elif isinstance(length, Number):
                asm += f"""REG_WR w_length imm #{QickTime(time=length, relative=False, code=self)}\n"""
            else:
                raise ValueError(f'length must be a number or QickReg.')

        if freq is not None:
            # if freq is not associated with any code block, associate it now
            self.associate_code(freq)

            if isinstance(freq, QickReg):
                asm += f"""REG_WR w_freq op -op({freq})\n"""
            elif isinstance(freq, QickFreq):
                asm += f"""REG_WR w_freq imm #{freq}\n"""
            elif isinstance(freq, Number):
                asm += f"""REG_WR w_freq imm #{QickFreq(freq=freq, code=self)}\n"""
            else:
                raise ValueError(f'freq must be a QickFreq, number, or QickReg.')

        if amp is not None:
            # if amp is not associated with any code block, associate it now
            self.associate_code(amp)

            if isinstance(amp, QickReg):
                asm += f"""REG_WR w_gain op -op({amp})\n"""
            elif isinstance(amp, Number):
                asm += f"""REG_WR w_gain imm #{amp}\n"""
            else:
                raise ValueError(f'amp must be a number or QickReg.')

        asm += f"REG_WR w_conf imm #{self.sig_gen_conf(outsel='dds', mode='oneshot', stdysel='zero', phrst=0)}\n"
        asm += f'WPORT_WR p{port} r_wave\n'

        self.asm += asm

    def sig_gen_conf(self, outsel = 'product', mode = 'oneshot', stdysel='zero', phrst = 0) -> int:
        outsel_reg = {'product': 0, 'dds': 1, 'input': 2, 'zero': 3}[outsel]
        mode_reg = {'oneshot': 0, 'periodic': 1}[mode]
        stdysel_reg = {'last': 0, 'zero': 1}[stdysel]

        mc = phrst*0b10000 + stdysel_reg*0b01000 + mode_reg*0b00100 + outsel_reg
        return mc

    def merge_kvp(self, kvp: Dict):
        """Merge the given key-value pairs into this code block's key-value
        pairs.

        Args:
            kvp: Key-value pair dictionary.

        """
        for k, v in kvp.items():
            if k in self.kvp and v != self.kvp[k]:
                raise RuntimeError('Internal error merging key-value '
                    'pairs. Key already exists with different value.')
            else:
                self.kvp[k] = v

    def _check_board(self, code):
        """Check that the given code block has the same QICK board.

        Args:
            code: The code block to check.

        """
        if self.board != code.board:
            raise RuntimeError('Adding the code blocks below is not '
                'possible because they are associated with different QICK '
                f'boards. [{self}] with board [{self.board}] + [{code}] '
                f'with board [{code.board}].')

    def add(self, code: QickCode):
        """Consolidate another code block to run sequentially after this block.

        Args:
            code: Code to run after this code.

        """
        self._check_board(code)

        # merge code's kvp dict into this kvp dict
        # offset all times in code by the length of this block
        new_asm = code.asm
        for k, v in code.kvp.items():
            if k in self.kvp and v != self.kvp[k]:
                raise RuntimeError('Internal error merging key-value '
                    'pairs. Key already exists with different value.')
            else:
                if isinstance(v, QickTime):
                    if v.relative:
                        # create a new QickTime that is offset by the length of
                        # this code
                        v = QickTime(time=v.time + self.length, code=self)
                        # replace the keys in the asm with the new
                        # offset QickTime
                        new_asm = new_asm.replace(k, str(v))
                        # save the new key into the kvp
                        k = str(v)
                self.kvp[k] = v

        # add the length of code to this block since they run sequentially
        self.length += code.length
        self.asm += new_asm

        if self.name is None and code.name is not None:
            self.name = code.name
        elif self.name is not None and code.name is not None:
            self.name = f'({self.name} + {code.name})'

    def parallel(self, code: QickCode):
        """Consolidate another code block to run in parallel with this block.

        Args:
            code: Code to run in parallel with this code.

        """
        self._check_board(code)

        self.merge_kvp(code.kvp)
        # the new length is the larger of this and code since they run in
        # parallel
        self.length = max(self.length, code.length)
        self.asm += code.asm

        if self.name is None and code.name is not None:
            self.name = code.name
        elif self.name is not None and code.name is not None:
            self.name = f'({self.name} | {code.name})'

    def __add__(self, code: QickCode):
        if not isinstance(code, QickCode):
            return NotImplemented

        new_block = QickCode(length=0)
        new_block.add(self)
        new_block.add(code)

        return new_block

    def __or__(self, code: QickCode):
        if not isinstance(code, QickCode):
            return NotImplemented

        new_block = QickCode(length=0)
        new_block.parallel(self)
        new_block.parallel(code)

        return new_block