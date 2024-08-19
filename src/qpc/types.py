"""TODO"""
from __future__ import annotations
from abc import ABC, abstractmethod
from inspect import isclass
from numbers import Number
from typing import Optional, Union, Type

from qick import QickConfig

# keep track of current context of the QICK code being created
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
        if len(qpc_context):
            self.context = qpc_context[-1]
        else:
            raise RuntimeError('Attempted to create QickObject outside of '
                'a QickContext.')

    def __str__(self) -> str:
        if self.context.code is None:
            raise RuntimeError(f'QickObject [{self}] was never associated with '
                'a QickCode block.')
        else:
            return self.context.code.key(self)

class QickLabel:
    """Represents an assembly code label."""
    def __init__(self, prefix: str):
        """
        Args:
            prefix: Label prefix.

        """
        self.prefix = prefix

class QickType(QickObject, ABC):
    """Fundamental types used in the QICK firmware."""

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
        if isclass(other) and issubclass(other, QickType):
            return other
        elif isinstance(other, QickType):
            return other.qick_type()
        else:
            raise TypeError(f'other [{other}] must be an instance of QickType '
                'or a subclass of QickType.')

    def compatible_type(self, other: Union[QickType, Type]) -> bool:
        """Return true if self and other have compatible QICK type.

        Args:
            other: a QickType object or class.

        """
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
        if self.compatible_type(other):
            return self.qick_type_class(other)(val=self.val)
        else:
            raise TypeError(f'Tried to cast [{self}] to type of [{other}] '
                'but their types are incompatible.')

    def __add__(self, other) -> QickConstType:
        if isinstance(other, QickConstType):
            if not self.compatible_type(other):
                raise TypeError(f'Tried to add [{self}] to [{other}] '
                    'but their types are incompatible.')
            if self.context != other.context:
                raise RuntimeError(f'Tried to add [{self}] and [{other}] '
                    'but they are associated with different contexts.')
            return self.qick_type()(val=self.val + other.val)
        elif isinstance(other, Number):
            return self.qick_type()(val=self.val + other)
        else:
            return NotImplemented

    def __radd__(self, other) -> QickConstType:
        return self.__add__(other)

class QickTime(QickConstType):
    """Represents a time."""
    def compatible_type(self, other: Union[QickType, Type]) -> bool:
        return (issubclass(self.qick_type(), QickTime) and \
            issubclass(self.qick_type_class(other), QickTime))

class QickEpoch(QickTime):
    """Represents the time at which a pulse will be played."""
    pass

class QickLength(QickTime):
    """Represents the length of a pulse."""
    def __init__(self, val: Number, ch):
        super().__init__(val=val)
        # TODO need to integrate type checking for correct channel number
        # when adding regs

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
        if not self.compatible_type(other):
            raise TypeError(f'Tried adding [{self}] and [{other}] but their '
                'types are not compatible.')
        if self.context != other.context:
            raise RuntimeError(f'Tried to add [{self}] and [{other}] '
                'but they are associated with different contexts.')

        # swap the orientation if called from __radd__
        if swap:
            return QickExpression(left=other, operator='+', right=self)
        else:
            return QickExpression(left=self, operator='+', right=other)

    def __radd__(self, other) -> QickExpression:
        return self.__add__(other, swap=True)

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
        """Return self if it already has the type of other. Otherwise, QickReg
        cannot be typecast."""
        if self.qick_type() == self.qick_type_class(other):
            return self
        else:
            raise TypeError(f'QickReg cannot be typecast.')

    def assign(self, value: Union[int, QickType]):
        """TODO

        Args:
            value: TODO

        """
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
            pre_asm, exp_asm = value.render_asm()
            asm = pre_asm
            asm += f'REG_WR {self} op -op({exp_asm})\n'
        else:
            raise TypeError(f'Tried to assign reg a value with an invalid type.')

        self.context.code.asm += asm

class QickExpression(QickVarType):
    """Represents a mathematical equation containing QickType."""
    def __init__(
            self,
            left: QickType,
            operator: str,
            right: QickType,
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
            right = right.typecast(left)
        except TypeError:
            try:
                left = left.typecast(right)
            except TypeError:
                raise TypeError(f'Could not create new QickExpression because '
                    f'left [{left}] and right [{right}] could not be typecast.')

        self.left = left
        self.right = right
        self.operator = operator
        self.held_type: QickConstType = left.qick_type()

    def typecast(self, other: Union[QickType, Type]) -> QickExpression:
        """Return self converted into the type of other."""
        try:
            left = self.left.typecast(other)
            right = self.right.typecast(other)
        except TypeError as err:
            raise TypeError(f'QickExpression [{self}] failed to typecast '
                f'into type [{other}].') from err
        return QickExpression(left=left, operator=self.operator, right=right)

    def render_asm(self) -> Tuple[str, str]:
        """Create assembly code that evaluates the expression."""
        # series of REG_WR instructions that go before this expression
        # to prepare the operands
        pre_asm = ''
        # assembly code of this expression, e.g. 'r1 + 5' or 'r1 + r2'
        exp_asm = ''

        if isinstance(self.left, QickExpression):
            left_pre, left_exp = left.render_asm()
            pre_asm += left_pre
            left_reg = QickReg()
            pre_asm += f'REG_WR {left_reg} op -op({left_exp})\n'
        elif isinstance(self.left, QickReg):
            exp_asm += f'{self.left} '
        else:
            exp_asm += f'#{self.left} '

        exp_asm += self.operator

        if isinstance(self.right, QickExpression):
            right_pre, right_exp = right.render_asm()
            pre_asm += right_pre
            right_reg = QickReg()
            pre_asm += f'REG_WR {right_reg} op -op({right_exp})\n'
        elif isinstance(self.right, QickReg):
            exp_asm += f' {self.right}'
        else:
            exp_asm += f' #{self.right}'

        return pre_asm, exp_asm

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
#         raise ValueError('QickSweepArange cannot be converted into a string'
#             'key. Use start_key(), stop_key(), and step_key().')

#     def start_key(self) -> str:
#         return self.context.code.key(obj=self, subid='start')

#     def stop_key(self) -> str:
#         return self.context.code.key(obj=self, subid='stop')

#     def step_key(self) -> str:
#         return self.context.code.key(obj=self, subid='step')

class QickCode:
    """Represents a segment of QICK code. There are two components. The first
    is a string containing assembly code. The second is a key-value pair ("kvp")
    dictionary containing string keys and object values. In the assembly code,
    there are special string keys surrounded by *, e.g. *12345*. These are keys
    to the kvp dictionary and will be replaced by the compiler before the
    code is uploaded to the board.

    """
    def __init__(
            self,
            offset: Optional[QickType] = None,
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
        # length of code block
        self.length = None

        if offset is None:
            with QickContext(self):
                self.offset = QickEpoch(0)
        else:
            self.offset = offset

        self.name = name
        if self.name is not None:
            self.asm += f'// ---------------\n// {self.name}\n// ---------------\n'

    def key(self, obj: Any, subid: Optional[str] = None) -> str:
        """Get the key associated with the given object, or create a new one
        if it does not exist.

        Args:
            obj: The object to be handled by the compiler.
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

    def deembed_io(self, io: Union[QickIODevice, QickIO, int]) -> Tuple:
        """Consolidate all of the offsets relevant to the provided IO.

        Args:
            io: QickIODevice, QickIO, or port to calculate the offsets of.

        Returns:
            A tuple containing (port, offset). The port is the firmware port
            number and the offset is a QickTime.

        """
        with QickContext(code=self):
            if isinstance(io, QickIODevice):
                port = self.key(io)
                port_offset = QickEpoch(io.total_offset())
            elif isinstance(io, QickIO):
                port = self.key(io)
                port_offset = QickEpoch(io.offset)
            else:
                port = io
                port_offset = QickEpoch(0)

        offset = self.offset + port_offset

        return port, offset

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

    # def add(self, code: QickCode):
    #     """Consolidate another code block to run sequentially after this block.

    #     Args:
    #         code: Code to run after this code.

    #     """

    #     # merge code's kvp dict into this kvp dict
    #     # offset all times in code by the length of this block
    #     new_asm = code.asm
    #     for k, v in code.kvp.items():
    #         if k in self.kvp and v != self.kvp[k]:
    #             raise RuntimeError('Internal error merging key-value '
    #                 'pairs. Key already exists with different value.')
    #         else:
    #             if isinstance(v, QickTime):
    #                 if v.relative:
    #                     # create a new QickTime that is offset by the length of
    #                     # this code
    #                     v = QickTime(time=v.time + self.length, code=self)
    #                     # replace the keys in the asm with the new
    #                     # offset QickTime
    #                     new_asm = new_asm.replace(k, str(v))
    #                     # save the new key into the kvp
    #                     k = str(v)
    #             self.kvp[k] = v

    #     # add the length of code to this block since they run sequentially
    #     self.length += code.length
    #     self.asm += new_asm

    #     if self.name is None and code.name is not None:
    #         self.name = code.name
    #     elif self.name is not None and code.name is not None:
    #         self.name = f'({self.name} + {code.name})'

    # def parallel(self, code: QickCode):
    #     """Consolidate another code block to run in parallel with this block.

    #     Args:
    #         code: Code to run in parallel with this code.

    #     """
    #     self._check_board(code)

    #     self.merge_kvp(code.kvp)
    #     # the new length is the larger of this and code since they run in
    #     # parallel
    #     self.length = max(self.length, code.length)
    #     self.asm += code.asm

    #     if self.name is None and code.name is not None:
    #         self.name = code.name
    #     elif self.name is not None and code.name is not None:
    #         self.name = f'({self.name} | {code.name})'

    # def __add__(self, code: QickCode):
    #     if not isinstance(code, QickCode):
    #         return NotImplemented

    #     new_block = QickCode(length=0)
    #     new_block.add(self)
    #     new_block.add(code)

    #     return new_block

    # def __or__(self, code: QickCode):
    #     if not isinstance(code, QickCode):
    #         return NotImplemented

    #     new_block = QickCode(length=0)
    #     new_block.parallel(self)
    #     new_block.parallel(code)

    #     return new_block
