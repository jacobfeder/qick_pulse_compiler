"""TODO"""
from __future__ import annotations
from abc import ABC, abstractmethod
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
    def holds_type(self):
        """Returns the type of this class."""
        pass

    def compatible_type(self, other: Type) -> bool:
        """Return True if other is compatible with this type."""
        return (self.holds_type() == other)

    def __add__(self, other: QickType) -> QickType:
        if isinstance(self, QickVarType) or isinstance(other, QickVarType):
            return QickExpression(left=self, right=other, operator='+')
        else:
            return NotImplemented

    def __radd__(self, other) -> QickType:
        return self.__add__(other)

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

    def holds_type(self):
        return type(self)

    def typecast(self, other: Type):
        """Return self converted into other type."""
        if self.compatible_type(other):
            return other(val=self.val)
        else:
            raise TypeError(f'Tried to cast [{self}] to type of [{other}] '
                'but their types are incompatible.')

    def __add__(self, other: QickType) -> QickType:
        if isinstance(other, QickConstType):
            if not self.compatible_type(type(other)):
                raise TypeError(f'Tried to add [{self}] and [{other}] '
                    'but their types are incompatible.')
            if self.context.code != other.context.code:
                raise RuntimeError(f'Tried to add [{self}] and [{other}] '
                    'but they are associated with different code blocks.')
            return type(self)(val=self.val + other.val)
        else:
            return super().__add__(other)

class QickTime(QickConstType):
    """Represents a time."""
    def compatible_type(self, other: Type):
        return issubclass(other, QickTime)

class QickEpoch(QickTime):
    """Represents the time at which a pulse will be played."""
    pass

class QickLength(QickTime):
    """Represents the length of a pulse."""
    pass

class QickFreq(QickConstType):
    """Represents a frequency."""
    pass

class QickVarType(QickType):
    """Base class for variable types."""
    def holds_type(self) -> QickConstType:
        return self.held_type

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
        # TODO
        self.held_type: Optional[QickConstType] = None

class QickExpression(QickVarType):
    """Represents a mathematical expression containing a combination of
    QickConstType and QickReg."""
    def __init__(
            self,
            left: QickType,
            right: QickType,
            operator: str,
        ):
        """
        Args:
            left: TODO
            right: 
            operator: 

        """
        super().__init__()

        if left.holds_type() is None:
            raise RuntimeError(f'[{left}] is undergoing an operation '
                'but it has not yet been assigned.')
        if right.holds_type() is None:
            raise RuntimeError(f'[{right}] is undergoing an operation '
                'but it has not yet been assigned.')
        if left.holds_type() != right.holds_type():
            raise TypeError('Tried to create an expression with incompatible '
                f'types [{left}] and [{right}].')

        self.left = left
        self.right = right
        self.operator = operator
        self.held_type: QickConstType = left.holds_type()

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

    # def deembed_io(self, io: Union[QickIODevice, QickIO, int]) -> Tuple:
    #     """Consolidate all of the offsets relevant to the provided IO.

    #     Args:
    #         io: QickIODevice, QickIO, or port to calculate the offsets of.

    #     Returns:
    #         A tuple containing (port, offset). The port is the firmware port
    #         number and the offset is a QickTime.

    #     """
    #     offset = self.offset
    #     if isinstance(io, QickIODevice):
    #         port = self.key(io)
    #         offset += io.total_offset()
    #     elif isinstance(io, QickIO):
    #         port = self.key(io)
    #         offset += io.offset
    #     else:
    #         port = io
    #     offset = QickTime(time=offset, relative=False, code=self)

    #     return port, offset

    def assign_reg(
            self,
            reg: QickReg,
            value: Union[int, QickFreq, QickTime, QickReg, QickExpression]
        ):
        """TODO

        Args:
            reg: TODO

        """
        asm = ''
        if isinstance(value, QickFreq) or \
            isinstance(value, QickTime):
            asm += f'REG_WR {reg.reg} imm #{value}\n'
        elif isinstance(value, QickReg):
            asm += f'REG_WR w_freq op -op({value})\n'



            elif isinstance(freq, QickFreq):
                asm += f"""REG_WR w_freq imm #{freq}\n"""
            elif isinstance(freq, Number):
                asm += f"""REG_WR w_freq imm #{QickFreq(freq=freq, code=self)}\n"""

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
    #     self._check_board(code)

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
