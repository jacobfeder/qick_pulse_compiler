"""Fundamental types to be used in generating pusle programs that can be
compiled using the QickPulseCompiler.

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

# keep track of current context of the qick code being created
qpc_context = []

class QickContext:
    """QPC program context. QPC objects defined within this context will be
    associated with the code given in the constructor."""
    def __init__(
            self,
            code: QickCode,
            soccfg: Optional[QickConfig] = None
        ):
        """
        Args:
            code: QickObjects created within this context will be associated
                with this code block.
            soccfg: Qick firmware config.

        """
        self.code = code
        self.soccfg = soccfg

    def __enter__(self):
        qpc_context.append(self)
        return self

    def __exit__(self, *args):
        qpc_context.pop()

class QickObject:
    """An object to be used with the QPC compiler."""
    def __init__(self):
        self._set_current_context()

    def __str__(self) -> str:
        if self.context.code is None:
            raise RuntimeError(f'QickObject was never associated with a '
                'QickCode block.')
        else:
            return self.context.code.key(self)

    def _set_current_context(self):
        if len(qpc_context):
            self.context = qpc_context[-1]
        else:
            raise RuntimeError('Attempted to contextcast QickObject outside of '
                'a QickContext.')

    def contextcast(self):
        """Set this object's context to the current context."""
        self._set_current_context()

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
    def __init__(self, val: Number):
        """
        Args:
            val: Value in SI units (s, Hz, etc.).

        """
        super().__init__()
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
        if isinstance(other, QickConstType):
            if not self.typecastable(other):
                raise TypeError(f'Cannot add these QickConstType because their '
                    'types are incompatible.')
            return self.qick_type()(val=self.val + other.val)
        elif isinstance(other, Number):
            return self.qick_type()(val=self.val + other)
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

class QickEpoch(QickTime):
    """Represents the time at which a pulse will be played."""
    pass

class QickLength(QickTime):
    """Represents the length of a pulse."""
    def __init__(self, val: Number, ch: int):
        super().__init__(val=val)
        self.ch = ch
        # TODO need to integrate type checking for correct channel number
        # when doing ops on regs

class QickFreq(QickConstType):
    """Represents a frequency."""
    pass

class QickVarType(QickType):
    """Base class for variable types."""
    def __init__(self):
        super().__init__()
        self.held_type: Optional[QickConstType] = None

    def qick_type(self) -> Optional[QickConstType]:
        return self.held_type

    def __add__(self, other, swap: bool = False) -> QickExpression:
        if not self.typecastable(other):
            raise TypeError(f'Cannot add these QickVarType because their '
                'types are not compatible.')

        if isinstance(self, QickEpochExpression) or isinstance(other, QickEpochExpression):
            exp_type = QickEpochExpression
        else:
            exp_type = QickExpression

        # swap the orientation if called from __radd__
        if swap:
            return exp_type(left=other, operator='+', right=self)
        else:
            return exp_type(left=self, operator='+', right=other)

    def __radd__(self, other) -> QickExpression:
        return self.__add__(other, swap=True)

    def __mul__(self, other) -> QickConstType:
        # TODO
        return NotImplemented

    def __rmul__(self, other) -> QickConstType:
        return self.__mul__(other)

class QickReg(QickVarType):
    """Represents a register in the tproc."""
    def __init__(self, reg: Optional[str] = None):
        """
        Args:
            reg: Register to use. If None, a register will be
                automatically assigned.

        """
        super().__init__()
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
        self.context.code.asm += self._assign(value=value)

class QickExpression(QickVarType):
    """Represents a mathematical equation containing QickType."""
    def __init__(
            self,
            left: Union[int, QickType],
            operator: str,
            right: Union[int, QickType],
        ):
        """
        Args:
            left: Left operand.
            operator: Operator: '+', '-', '*'.
            right: Right operand.

        """
        super().__init__()

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

    def contextcast(self):
        """Set this object's context to the current context."""
        super().contextcast()
        if isinstance(self.left, QickExpression):
            self.left.contextcast(new_context)
        if isinstance(self.right, QickExpression):
            self.right.contextcast(new_context)

    def pre_asm_key(self) -> str:
        return self.context.code.key(obj=self, subid='pre_asm')

    def exp_asm_key(self) -> str:
        return self.context.code.key(obj=self, subid='exp_asm')

    def typecast(self, other: Union[QickType, Type]) -> QickExpression:
        """Return self converted into the type of other."""
        try:
            left = self.left.typecast(other)
            right = self.right.typecast(other)
        except TypeError as err:
            raise TypeError(f'QickExpression [{self}] failed to typecast '
                f'into type [{other}].') from err
        return type(self)(left=left, operator=self.operator, right=right)

class QickEpochExpression(QickExpression):
    """Special QickExpression used for QickCode offsets."""
    pass

# class QickSweptReg(QickReg):
#     """Represents the arguments to a swept variable."""
#     def __init__(
#             self,
#             start: Union[QickTime, QickFreq, int, QickReg],
#             stop: Union[QickTime, QickFreq, int, QickReg],
#             step: Union[QickTime, QickFreq, int, QickReg],
#             sweep_type: str,
#             sweep_ch: Optional[Union[QickIODevice, QickIO, int]] = None,
#             **kwargs
#         ):
#         """Represents the arguments to a variable that should be swept over
#         a range inside a loop.

#         Args:
#             start: Start value of swept variable.
#             stop: Stop value of swept variable.
#             step: Step size of swept variable.
#             sweep_type: Should be 'freq' or 'time'.
#             sweep_ch: If sweep_type is 'freq', this is the associated
#                 RF channel.
#             kwargs: Keyword arguments to pass to QickObject constructor.

#         """
#         super().__init__(**kwargs)
#         self.start = start
#         self.stop = stop
#         self.step = step
#         self.sweep_type = sweep_type
#         if sweep_type == 'freq' and sweep_ch is None:
#             raise ValueError(f'sweep_type is "freq" but no sweep_ch is '
#                 'specified.')
#         self.sweep_ch = sweep_ch

#     def __str__(self):
#         raise ValueError('QickSweepArange cannot be converted into a string '
#             'key. Use start_key(), stop_key(), and step_key().')

#     def start_key(self) -> str:
#         return self.context.code.key(obj=self, subid='start')

#     def stop_key(self) -> str:
#         return self.context.code.key(obj=self, subid='stop')

#     def step_key(self) -> str:
#         return self.context.code.key(obj=self, subid='step')

class QickCode:
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
        ):
        """

        Args:
            offset: Offset to add to all pulses in this code block.
            name: Optional name that will be added as a comment at the top of
                the code segment.

        """
        # assembly code string
        self.asm = ''
        # key-value pairs
        self.kvp = {}
        # other QickCode's that have references to this QickCode
        # this is required in order to implement deepcopy()
        self.refs = []

        with QickContext(code=self):
            # length of code block
            if length is None:
                self.length = QickTime(0)
            elif isinstance(length, Number):
                self.length = QickTime(length)
            elif isinstance(length, QickType):
                self.length = length
            else:
                raise ValueError('length has an invalid type')

            # offset for all pulses in the block
            if offset is None:
                self.offset = QickReg(reg='s0')
            elif isinstance(offset, Number):
                self.offset = QickTime(offset)
            elif isinstance(offset, QickType):
                self.offset = offset
            else:
                raise ValueError('offset has an invalid type')

        self.name = name

    def __str__(self) -> str:
        if len(qpc_context):
            context = qpc_context[-1]
            # record the fact that context.code contains a reference to this code
            self.refs.append(context.code)
            return context.code.key(self)
        else:
            raise RuntimeError('Attempted to get key of QickCode outside of '
                'a QickContext.')

    def _key(self, obj: Any) -> str:
        return f'*{id(obj)}*'

    def key(self, obj: Any, subid: Optional[str] = None) -> str:
        """Get the key associated with the given object, or create a new one
        if it does not exist.

        Args:
            obj: The object to be handled by the compiler.
            subid: A string representing some additional identifier within obj.

        Returns:
            A unique string representing this object.

        """
        dict_key = self._key(obj)
        if dict_key not in self.kvp:
            self.kvp[dict_key] = obj

        if subid is None:
            return dict_key
        else:
            return dict_key + subid

    def update_key(self, old_key: str):
        """Update the given key in the assembly code and key-value pair dictionary.

        Args:
            old_key: The key that needs to be updated.

        """
        # object associated with the key
        qick_obj = self.kvp[old_key]
        # get the new key associated with the object
        new_key = self._key(qick_obj)
        # update the key in the dictionary
        del self.kvp[old_key]
        self.kvp[new_key] = qick_obj
        # replace all instances of the old key with the new key in the assembly code
        self.asm = self.asm.replace(old_key, new_key)

    def _update_all_keys(self, old_kvp: Dict):
        """ """
        for old_key, qick_obj in old_kvp.copy().items():
            if old_key in self.kvp:
                self.update_key(old_key)

        for ref in self.refs:
            ref._update_all_keys(old_kvp=old_kvp)

    def __deepcopy__(self, memo):
        # references:
        # https://stackoverflow.com/a/71125311
        # https://stackoverflow.com/a/24621200

        import pdb; pdb.set_trace()

        # store the original references
        old_refs = self.refs

        # prevent infinite recursion in call to deepcopy
        deepcopy_method = self.__deepcopy__
        self.__deepcopy__ = None

        # delete references so they don't get copied in deepcopy()
        del self.__dict__['refs']

        # make the copy
        clone = deepcopy(self, memo)

        # restore the refs
        setattr(self, 'refs', old_refs)
        # give clone a new array containing the old refs
        setattr(clone, 'refs', old_refs.copy())

        # restore __deepcopy__
        self.__deepcopy__ = deepcopy_method
        # bind to clone by types.MethodType
        clone.__deepcopy__ = MethodType(deepcopy_method.__func__, clone)

        clone._update_all_keys(self.kvp)

        return clone

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

    def deembed_io(self, io: Union[QickIODevice, QickIO, int]) -> Tuple:
        """Calculate the final offset relevant to the provided IO.

        Args:
            io: QickIODevice, QickIO, or port to calculate the offsets of.

        Returns:
            A tuple containing (port, offset). The port is the firmware port
            number and the offset is a QickEpochExpression.

        """
        if isinstance(io, QickIODevice):
            port = self.key(io)
            port_offset = QickTime(io.total_offset())
        elif isinstance(io, QickIO):
            port = self.key(io)
            port_offset = QickTime(io.offset)
        else:
            port = io
            port_offset = QickReg(reg='s0')

        offset = QickEpochExpression(
            left=self.offset,
            operator='+',
            right=port_offset
        )

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
        with QickContext(code=self):
            port, offset = self.deembed_io(ch)

            self.asm += f'// Setting trigger port {port} to {state}\n'
            if time is not None:
                if isinstance(time, Number):
                    time = QickTime(time)

                # set the play time of the trig
                out_usr_time = QickReg(reg='out_usr_time')
                out_usr_time.assign(offset + time)

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
        with QickContext(code=self):
            port, offset = self.deembed_io(ch)

            self.asm += f'// Pulsing RF port {port}\n'

            if time is not None:
                if isinstance(time, Number):
                    time = QickTime(time)
                # set the play time of the pulse
                out_usr_time = QickReg(reg='out_usr_time')
                out_usr_time.assign(offset + time)

            if length is not None:
                if isinstance(length, Number):
                    length = QickLength(val=length, ch=port)
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
        # make a copy so we don't modify the original code
        code = deepcopy(code)

        with QickContext(code=code):
            # calculate the amount to offset all pulses in code
            offset_reg = QickReg()
            self.length.contextcast()
            code.asm = offset_reg._assign(self.length) + code.asm

            # find all instance of QickEpochExpression in kvp and offset
            # them by offset_reg
            for key, qick_obj in code.kvp.copy().items():
                if isinstance(qick_obj, QickEpochExpression):
                    code.kvp[key] = QickEpochExpression(
                        left=offset_reg,
                        operator='+',
                        right=qick_obj,
                    )
                    code.update_key(key)

        with QickContext(code=self):
            self.length += code.length
            self.asm += str(code)

        if self.name is None and code.name is not None:
            self.name = code.name
        elif self.name is not None and code.name is not None:
            self.name = f'({self.name} + {code.name})'

    def parallel(self, code: QickCode):
        """Set another code block to run in parallel with this block. The length
        is set by the right operand.

        Args:
            code: Code to run in parallel with this code.

        """
        # make a copy so we don't modify the original code
        code = deepcopy(code)

        with QickContext(code=self):
            self.length = code.length
            self.asm += str(code)

        if self.name is None and code.name is not None:
            self.name = code.name
        elif self.name is not None and code.name is not None:
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
