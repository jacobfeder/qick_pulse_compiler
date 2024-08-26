"""Fundamental types to be used in generating pusle programs that can be
compiled using the Qick Pulse Compiler.

Author: Jacob Feder
Date: 2024-08-16
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from copy import deepcopy
from inspect import isclass
from numbers import Number
from types import MethodType
from typing import Optional, Union, Type

from qick import QickConfig

from qpc.io import QickIO, QickIODevice

# keep track of current scope of the qick code being created
qpc_scope = []

# unique id counter for qpc objects
qpc_id = 0

class QickScope:
    """QPC program scope. QPC objects defined within this scope will be
    associated with the code (and soccfg) given in the constructor."""
    def __init__(
            self,
            code: QickCode,
            soccfg: Optional[QickConfig] = None
        ):
        """
        Args:
            code: QickObjects created within this scope will be associated
                with this code block.
            soccfg: Qick firmware config.

        """
        self.code = code
        self.soccfg = soccfg

    def __enter__(self):
        if len(qpc_scope) and self.soccfg is None:
            # inherit soccfg from parent scope
            self.soccfg = qpc_scope[-1].soccfg
        qpc_scope.append(self)
        return self

    def __exit__(self, *args):
        qpc_scope.pop()

class QickObject:
    """An object to be used with the QPC compiler."""
    def __init__(self, scope_required: bool = True):
        """

        Args:
            scope_required: If True, require this object to have a scope.

        """
        self.scope_required = scope_required
        self._alloc_qpc_id()
        self._connect_scope()

    def _alloc_qpc_id(self) -> int:
        """Allocate a unique id number."""
        global qpc_id
        self.id = qpc_id
        qpc_id += 1

    def _connect_scope(self):
        """Connect object to the local scope"""
        if len(qpc_scope):
            self.scope = qpc_scope[-1]
        else:
            if self.scope_required:
                raise RuntimeError('Cannot create a QickObject outside of a QickScope.')
            else:
                self.scope = None

    def __str__(self) -> str:
        return self.key()

    def _key(self) -> str:
        return f'*{self.id}*'

    def key(self, subid: Optional[str] = None) -> str:
        """Get the key associated with this object, or create a new one
        if it does not exist.

        Args:
            subid: A string representing some additional identifier within obj.

        Returns:
            A unique string representing this object.

        """
        key = self._key()

        if self.scope is not None:
            if key not in self.scope.code.kvp:
                self.scope.code.kvp[key] = self

        if subid is None:
            return key
        else:
            return key + subid

class QickLabel(QickObject):
    """Represents an assembly code label."""
    def __init__(self, prefix: str):
        """
        Args:
            prefix: Label prefix.

        """
        super().__init__()
        self.prefix = prefix

class QickType(QickObject, ABC):
    """Fundamental types used in the qick firmware."""
    def __init__(self, *args, epoch: bool = False, **kwargs):
        """

        Args:
            epoch: If true, this object represents an epoch time for playing
                pulses.

        """
        super().__init__(*args, **kwargs)
        self.epoch = epoch

    def transfer_epoch(self, other) -> bool:
        """Determine the result of performing operations on QickType that have
        the epoch flag set.

        Args:
            other: Other operand.

        """
        # remove the flag from the operands but apply it to the result
        epoch = False
        if self.epoch:
            self.epoch = False
            epoch = True
        if isinstance(other, QickType) and other.epoch:
            other.epoch = False
            epoch = True

        return epoch

    @abstractmethod
    def qick_type(self):
        """Returns the type of this object."""
        pass

    @abstractmethod
    def typecast(self, other: Union[QickType, Type]):
        """Return self converted into the qick type of other."""
        pass

    def qick_type_class(self, other: Union[QickType, Type]) -> Type:
        """Similar to qick_type except it may also accept a class."""
        if (isclass(other) and issubclass(other, QickType)) or other is None:
            return other
        elif isinstance(other, QickType):
            return other.qick_type()
        else:
            raise TypeError(f'other must be an instance of QickType '
                'or a subclass of QickType.')

    def typecastable(self, other: Union[QickType, Type]) -> bool:
        """Return true if self can be typecast into the qick type of other.

        Args:
            other: a QickType object or class.

        """
        if self.qick_type() is None:
            return True
        else:
            return self.qick_type() == self.qick_type_class(other)

class QickConstType(QickType):
    """Base class for types that have a constant value."""
    def __init__(self, val: Number, *args, **kwargs):
        """

        Args:
            val: Value in SI units (s, Hz, etc.).
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, **kwargs)
        if not isinstance(val, Number):
            raise TypeError('val must be a number.')
        self.val = val

    def qick_type(self) -> QickConstType:
        return type(self)

    def typecast(self, other: Union[QickType, Type]) -> QickConstType:
        """Return a copy of self converted into the qick type of other."""
        if self.typecastable(other):
            return self.qick_type_class(other)(val=self.val)
        else:
            raise TypeError(f'Cannot cast to type of other because their types '
                'are incompatible.')

    def __add__(self, other) -> QickConstType:
        epoch = self.transfer_epoch(other)
        if isinstance(other, QickConstType):
            if not self.typecastable(other):
                raise TypeError(f'Cannot add these QickConstType because their '
                    'types are incompatible.')
            return self.qick_type()(val=self.val + other.val, epoch=epoch)
        elif isinstance(other, Number):
            return self.qick_type()(val=self.val + other, epoch=epoch)
        else:
            return NotImplemented

    def __radd__(self, other) -> QickConstType:
        return self.__add__(other)

    def __mul__(self, other) -> QickConstType:
        if isinstance(other, QickConstType):
            if not self.typecastable(other):
                raise TypeError(f'Cannot multiply these QickConstType because '
                    'their types are incompatible.')
            return self.qick_type()(val=self.val * other.val)
        elif isinstance(other, Number):
            return self.qick_type()(val=self.val * other)
        else:
            return NotImplemented

    def __rmul__(self, other) -> QickConstType:
        return self.__mul__(other)

class QickTime(QickConstType):
    """Represents a time."""
    def typecastable(self, other: Union[QickType, Type]) -> bool:
        if self.qick_type_class(other) is None:
            return False
        else:
            return (issubclass(self.qick_type(), QickTime) and \
                issubclass(self.qick_type_class(other), QickTime))

class QickLength(QickTime):
    """Represents the length of a pulse."""
    def __init__(self, val: Number, *args, **kwargs):
        """

        Args:
            val: Length (s).
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, val=val, **kwargs)
        # TODO need to integrate type checking for correct channel number
        # when doing ops on regs

class QickFreq(QickConstType):
    """Represents a frequency."""
    pass

class QickVarType(QickType):
    """Base class for variable types."""
    def __init__(self, *args, **kwargs):
        """

        Args:
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, **kwargs)
        self.held_type: Optional[QickConstType] = None

    def qick_type(self) -> Optional[QickConstType]:
        return self.held_type

    def __add__(self, other, swap: bool = False) -> QickExpression:
        if not self.typecastable(other):
            raise TypeError(f'Cannot add these QickVarType because their '
                'types are not compatible.')
        epoch = self.transfer_epoch(other)
        # swap the orientation if called from __radd__
        if swap:
            return QickExpression(left=other, operator='+', right=self, epoch=epoch)
        else:
            return QickExpression(left=self, operator='+', right=other, epoch=epoch)

    def __radd__(self, other) -> QickExpression:
        return self.__add__(other, swap=True)

    def __mul__(self, other) -> QickConstType:
        # TODO
        return NotImplemented

    def __rmul__(self, other) -> QickConstType:
        return self.__mul__(other)

class QickReg(QickVarType):
    """Represents a register in the tproc."""
    def __init__(self, *args, reg: Optional[str] = None, **kwargs):
        """

        Args:
            reg: Register to use. If None, a register will be
                automatically assigned.
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, **kwargs)
        self.reg = reg

    def typecast(self, other: Union[QickType, Type]) -> QickReg:
        """Convert self into the qick type of other."""
        if self.held_type is None:
            self.held_type = self.qick_type_class(other)
            return self

        if self.qick_type() == self.qick_type_class(other):
            return self
        else:
            raise TypeError(f'QickReg cannot be typecast.')

    def _assign(self, value: Union[int, QickType]):
        if self.held_type is None:
            if isinstance(value, QickType):
                self.held_type = value.qick_type()
            elif isinstance(value, int):
                self.held_type = None
            else:
                raise TypeError(f'value [{value}] must be a QickType or int.')
        else:
            raise ValueError(f'Cannot reassign reg [{self}].')

        if isinstance(value, int) or isinstance(value, QickConstType):
            asm = f'REG_WR {self} imm #{value}\n'
        elif isinstance(value, QickReg):
            asm = f'REG_WR {self} op -op({value})\n'
        elif isinstance(value, QickExpression):
            asm = f'{value.pre_asm_key()}REG_WR {self} op -op({value.exp_asm_key()})\n'
        else:
            raise TypeError(f'Tried to assign reg a value with an invalid type.')

        return asm

    def assign(self, value: Union[int, QickType]):
        """Assign a value to a register.

        Args:
            value: The value to assign.

        """
        self.scope.code.asm += self._assign(value=value)

class QickExpression(QickVarType):
    """Represents a mathematical equation containing QickType."""
    def __init__(
            self,
            left: Union[int, QickType],
            operator: str,
            right: Union[int, QickType],
            *args,
            **kwargs
        ):
        """
        Args:
            left: Left operand.
            operator: Operator: '+', '-', '*'.
            right: Right operand.
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, **kwargs)

        # make sure left and right have the same qick type
        try:
            if isinstance(right, QickType):
                right = right.typecast(left)
        except TypeError:
            try:
                left = left.typecast(right)
            except TypeError:
                raise TypeError(f'Could not create new QickExpression because '
                    f'left and right could not be typecast.')

        self.left = left
        self.right = right
        self.operator = operator
        self.held_type: QickConstType = left.qick_type()

    def __str__(self):
        raise ValueError('QickExpression cannot be converted into a string '
            'key. Use pre_asm_key() and exp_asm_key().')

    def pre_asm_key(self) -> str:
        return self.key(subid='pre_asm')

    def exp_asm_key(self) -> str:
        return self.key(subid='exp_asm')

    def typecast(self, other: Union[QickType, Type]) -> QickExpression:
        """Return self converted into the type of other."""
        try:
            left = self.left.typecast(other)
            right = self.right.typecast(other)
        except TypeError as err:
            raise TypeError(f'QickExpression [{self}] failed to typecast '
                f'into type [{other}].') from err
        return type(self)(left=left, operator=self.operator, right=right)

class QickSweptReg(QickReg):
    """Represents the arguments to a swept variable."""
    def __init__(
            self,
            start: Union[int, QickConstType, QickVarType],
            stop: Union[int, QickConstType, QickVarType],
            step: Union[int, QickConstType, QickVarType],
            *args,
            **kwargs
        ):
        """Represents a variable that will be swept over a range inside a loop.

        Args:
            start: Start value of swept variable.
            stop: Stop value of swept variable.
            step: Step size of swept variable.
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, **kwargs)
        self.start = start
        self.stop = stop
        self.step = step

    def __str__(self):
        raise ValueError('QickSweepArange cannot be converted into a string '
            'key. Use start_key(), stop_key(), and step_key().')

    def start_key(self) -> str:
        return self.key(subid='start')

    def stop_key(self) -> str:
        return self.key(subid='stop')

    def step_key(self) -> str:
        return self.key(subid='step')

class QickCode(QickObject):
    """Represents a segment of qick code. There are two components. The first
    is a string containing assembly code. The second is a key-value pair ("kvp")
    dictionary containing string keys and object values. In the assembly code,
    there are special string keys surrounded by *, e.g. *12345*. These are keys
    to the kvp dictionary and will be replaced by the compiler before the
    code is uploaded to the board.

    """
    def __init__(
            self,
            offset: Optional[Number, QickType] = None,
            length: Optional[Number, QickType] = None,
            name: Optional[str] = None,
            *args,
            **kwargs
        ):
        """

        Args:
            offset: Offset to add to all pulses in this code block.
            length: Length of code block.
            name: Optional name that will be added as a comment at the top of
                the code segment.
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, scope_required=False, **kwargs)
        # assembly code string
        self.asm = ''
        # key-value pairs
        self.kvp = {}

        with QickScope(code=self):
            # length of code block
            if length is None:
                self.length = QickTime(0)
            elif isinstance(length, Number):
                self.length = QickTime(length)
            elif isinstance(length, QickTime) or isinstance(length, QickVarType):
                self.length = length
            else:
                raise ValueError('length has an invalid type')

            # offset for all pulses in the block
            if isinstance(offset, Number):
                self.offset = QickTime(offset)
            elif offset is None or isinstance(offset, QickTime) or isinstance(offset, QickVarType):
                self.offset = offset
            else:
                raise ValueError('offset has an invalid type')

        self.name = name


    def update_key(self, old_key: str, new_obj: QickType):
        """Update the given key in the assembly code and key-value pair dictionary.

        Args:
            old_key: The key that needs to be updated.
            new_obj: The object that will take the place of the object pointed
                to by old_key.

        """
        del self.kvp[old_key]

        new_key = new_obj._key()
        self.kvp[new_key] = new_obj

        # replace all instances of the old key with the new key in the assembly code
        self.asm = self.asm.replace(old_key, new_key)

    def inc_ref(self):
        """Increment the reference by the length of this code block."""
        with QickScope(code=self):
            # the amount to inc_ref by
            ref_reg = QickReg()
            ref_reg.assign(self.length)
            self.asm += f'TIME inc_ref {ref_reg}\n'

    def _qick_copy(self):
        """Recursively iterate through all QickCode and change their ids."""

        for old_key, qick_obj in self.kvp.copy().items():
            if isinstance(qick_obj, QickCode):
                # get a new id
                qick_obj._alloc_qpc_id()
                # update the id in the kvp
                self.update_key(old_key, qick_obj)
                qick_obj._qick_copy()

    def qick_copy(self):
        """Implements deepcopy-like behavior."""

        # create the copy object
        new_code = deepcopy(self)

        # get a new id
        new_code._alloc_qpc_id()
        # put the new code in the current scope
        new_code._connect_scope()
        new_code._qick_copy()

        return new_code

    def deembed_io(self, io: Union[QickIODevice, QickIO, int]) -> Tuple:
        """Calculate the final offset relevant to the provided IO.

        Args:
            io: QickIODevice, QickIO, or port to calculate the offsets of.

        Returns:
            A tuple containing (port, offset). The port is the firmware port
            number and the offset is the total offset of the port.

        """
        if isinstance(io, QickIODevice):
            port_offset = QickTime(io.total_offset())
            port = io.io.key()
        elif isinstance(io, QickIO):
            port_offset = QickTime(io.offset)
            port = io.key()
        elif isinstance(io, int):
            port_offset = None
            port = io
        else:
            raise ValueError('io has invalid type.')

        if port_offset is None and self.offset is None:
            offset = QickTime(0)
        elif self.offset is not None and port_offset is None:
            offset = self.offset
        elif self.offset is None and port_offset is not None:
            offset = port_offset
        else:
            offset = self.offset + port_offset

        return port, offset

    def trig(
            self,
            ch: Union[QickIODevice, QickIO, int],
            state: bool,
            time: Optional[Union[Number, QickTime, QickVarType]],
        ):
        """Set a trigger port high or low.

        Args:
            ch: QickIODevice, QickIO, or port to trigger.
            state: Whether to set the trigger state True or False.
            time: Time at which to set the state. Pass a time (s), QickTime,
                QickReg, QickExpression. Set to None to use the value
                currently in out_usr_time.

        """
        with QickScope(code=self):
            port, offset = self.deembed_io(ch)
            self.asm += f'// Setting trigger port {port} to {state}\n'
            if time is not None:
                if isinstance(time, Number):
                    time = QickTime(time)

                # set the play time of the trig
                out_usr_time = QickReg(reg='out_usr_time')
                final_playtime = offset + time
                if not isinstance(final_playtime, QickExpression):
                    # this guarantees that out_usr_time will be an expression, which
                    # is required in order for QickCode.add() to work
                    final_playtime += QickReg(reg='s0')
                # this will get transferred to the out_usr_time assignment,
                # allowing it to later be replaced in the case of a QickCode.add()
                final_playtime.epoch = True
                out_usr_time.assign(final_playtime)

            # set the trig
            if state:
                self.asm += f'TRIG set p{port}\n'
            else:
                self.asm += f'TRIG clr p{port}\n'

    def sig_gen_conf(self, outsel = 'product', mode = 'oneshot', stdysel='zero', phrst = 0) -> int:
        outsel_reg = {'product': 0, 'dds': 1, 'input': 2, 'zero': 3}[outsel]
        mode_reg = {'oneshot': 0, 'periodic': 1}[mode]
        stdysel_reg = {'last': 0, 'zero': 1}[stdysel]

        mc = phrst * 0b10000 + stdysel_reg * 0b01000 + mode_reg * 0b00100 + outsel_reg
        return mc

    def rf_square_pulse(
            self,
            ch: Union[QickIODevice, QickIO, int],
            length: Optional[Union[Number, QickTime, QickVarType]],
            freq: Optional[Union[Number, QickFreq, QickVarType]],
            amp: Optional[int],
            time: Optional[Union[Number, QickTime, QickVarType]],
        ):
        """Generate a square RF pulse.

        Args:
            ch: QickIODevice, QickIO, or port to output an RF pulse.
            length: Length of the RF pulse. Pass a time (s), QickLength,
                QickReg, QickExpression. Set to None to use the value
                currently in w_length.
            freq: RF frequency of the pulse. Pass a frequency (s), QickFreq,
                QickReg, QickExpression. Set to None to use the value
                currently in w_freq.
            amp: RF amplitude. Pass an integer (-32,768 to 32,767).
                Set to None to use the value currently stored in w_gain.
            time: Time at which to play the pulse. Pass a time (s), QickTime,
                QickReg, QickExpression. Set to None to use the value
                currently in out_usr_time.

        """
        with QickScope(code=self):
            port, offset = self.deembed_io(ch)

            self.asm += f'// Pulsing RF port {port}\n'

            if time is not None:
                if isinstance(time, Number):
                    time = QickTime(time)
                # set the play time of the pulse
                out_usr_time = QickReg(reg='out_usr_time')
                final_playtime = offset + time
                if not isinstance(final_playtime, QickExpression):
                    # this guarantees that out_usr_time will be an expression, which
                    # is required in order for QickCode.add() to work
                    final_playtime += QickReg(reg='s0')
                # this will get transferred to the out_usr_time assignment,
                # allowing it to later be replaced in the case of a QickCode.add()
                final_playtime.epoch = True
                out_usr_time.assign(final_playtime)

            if length is not None:
                if isinstance(length, Number):
                    length = QickLength(val=length)
                # set the play time of the pulse
                w_length = QickReg(reg='w_length')
                w_length.assign(length)

            if freq is not None:
                if isinstance(freq, Number):
                    freq = QickFreq(freq)
                # set the play time of the pulse
                w_freq = QickReg(reg='w_freq')
                w_freq.assign(freq)

            if amp is not None:
                w_gain = QickReg(reg='w_gain')
                w_gain.assign(amp)

            w_conf = QickReg(reg='w_conf')
            w_conf.assign(self.sig_gen_conf(outsel='dds', mode='oneshot', stdysel='zero', phrst=0))

            self.asm += f'WPORT_WR p{port} r_wave\n'

    def add(self, code: QickCode):
        """Set another code block to run sequentially after this block.

        Args:
            code: Code to run after this code.

        """
        with QickScope(code=self):
            # make a copy so we don't modify the original code
            code = code.qick_copy()

            with QickScope(code=code):
                # calculate the amount to offset all pulses in code
                offset_reg = QickReg()
                code.asm = '// Length offset\n' + \
                    offset_reg._assign(self.length) + \
                    code.asm

                # find all epoch objects in kvp and offset them by offset_reg
                for key, qick_obj in code.kvp.copy().items():
                    if qick_obj.epoch:
                        new_epoch = qick_obj + offset_reg
                        code.update_key(key, new_epoch)

            self.length += code.length
            self.asm += str(code)

            self.name = f'({self.name} + {code.name})'

    def parallel(self, code: QickCode):
        """Set another code block to run in parallel with this block. The length
        is set by the right operand.

        Args:
            code: Code to run in parallel with this code.

        """
        with QickScope(code=self):
            # make a copy so we don't modify the original code
            code = code.qick_copy()

            self.length = code.length
            self.asm += str(code)

        self.name = f'({self.name} | {code.name})'

    def __add__(self, code: QickCode):
        if not isinstance(code, QickCode):
            return NotImplemented

        new_block = QickCode()
        new_block.add(self)
        new_block.add(code)

        return new_block

    def __or__(self, code: QickCode):
        if not isinstance(code, QickCode):
            return NotImplemented

        new_block = QickCode()
        new_block.parallel(self)
        new_block.parallel(code)

        return new_block
