"""Fundamental types to be used in generating pusle programs that can be
compiled using the Qick Pulse Compiler (QPC).

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
    associated with the code given in the constructor."""
    def __init__(
            self,
            code: QickCode,
        ):
        """
        Args:
            code: QickObjects created within this scope will be associated
                with this code block.

        """
        self.code = code

    def __enter__(self):
        if len(qpc_scope):
            parent_soccfg = qpc_scope[-1].code.soccfg
            this_soccfg = self.code.soccfg
            if this_soccfg is None:
                # inherit soccfg from parent scope
                self.code.soccfg = parent_soccfg

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
        """Connect object to the local scope."""
        if len(qpc_scope):
            self.scope = qpc_scope[-1]
        else:
            if self.scope_required:
                raise RuntimeError('Cannot create a QickObject outside of a QickScope.')
            else:
                self.scope = None

    def _qick_copy(self, scopes: Dict, new_ids: list, new_ids_lut: Dict):
        """Implements deepcopy-like behavior.

        Args:
            scopes: Values are QickCode that are in the scope of what's being
                copied, keys are the corresponding QickCode.key()
            new_ids: List of new ids.
            new_ids_lut: Values are QickObject that have been assigned a new id,
                keys are their corresponding old QickObject.key() before
                reassignment.

        """

        key = self._key()

        code_key = self.scope.code._key()
        if code_key in new_ids_lut:
            # if the scope is changing id, reassign it 
            self.scope.code = new_ids_lut[code_key]

        if self.scope.code._key() in scopes:
            if key in new_ids:
                # this exact object has already been processed and assigned a new id
                return

            if key in new_ids_lut:
                # this is a different copy of an object that has already been
                # assigned a new id
                self.id = new_ids_lut[key].id
            else:
                # this key has not been previously processed
                # the object was created inside the scope, so it needs a new id
                self._alloc_qpc_id()
                new_ids_lut[key] = self
                new_key = self._key()
                new_ids.append(new_key)
        else:
            # the object was created outside the scope of what is currently
            # being copied, and should retain its id
            pass

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

    @abstractmethod
    def qick_type(self):
        """Returns the type of this object."""
        pass

    @abstractmethod
    def typecast(self, other: Union[QickType, Type]):
        """Return self converted into the qick type of other."""
        pass

    def scopecast(self):
        """Change the scope of this object to the current scope."""
        self._connect_scope()

    def qick_type_class(self, other: Union[QickType, Type]) -> Type:
        """Similar to qick_type except it may also accept a class."""
        if (isclass(other) and issubclass(other, QickType)) or other is None:
            return other
        elif isinstance(other, QickType):
            return other.qick_type()
        else:
            raise TypeError('other must be an instance of QickType '
                'or a subclass of QickType.')

    def typecastable(self, other: Union[QickType, Type]) -> bool:
        """Return true if self can be typecast into the qick type of other.

        Args:
            other: a QickType object or class.

        """
        if self.qick_type() is None:
            return True
        elif other.qick_type() is None:
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
            raise TypeError('Cannot cast to type of other because their types '
                'are incompatible.')

    def __add__(self, other) -> QickConstType:
        if isinstance(other, QickConstType):
            if not self.typecastable(other):
                raise TypeError('Cannot add these QickConstType because their '
                    'types are incompatible.')
            other_val = other.val
        elif isinstance(other, Number):
            other_val = other
        else:
            return NotImplemented

        return self.qick_type()(val=self.val + other_val)

    def __radd__(self, other) -> QickConstType:
        return self.__add__(other)

    def __sub__(self, other, swap: bool = False) -> QickConstType:
        if isinstance(other, QickConstType):
            if not self.typecastable(other):
                raise TypeError('Cannot subtract these QickConstType because '
                    'their types are incompatible.')
            other_val = other.val
        elif isinstance(other, Number):
            other_val = other
        else:
            return NotImplemented

        if swap:
            return self.qick_type()(val=other_val - self.val)
        else:
            return self.qick_type()(val=self.val - other_val)

    def __rsub__(self, other) -> QickConstType:
        return self.__sub__(other, swap=True)

    def __mul__(self, other) -> QickConstType:
        if isinstance(other, QickConstType):
            if not self.typecastable(other):
                raise TypeError('Cannot multiply these QickConstType because '
                    'their types are incompatible.')
            other_val = other.val
        elif isinstance(other, Number):
            other_val = other
        else:
            return NotImplemented

        return self.qick_type()(val=self.val * other_val)

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

    # TODO convert to/from a QickExpression tree <-> a sympy expression
    # use sympy to simplify expressions

    def __add__(self, other) -> QickExpression:
        if not self.typecastable(other):
            raise TypeError('Cannot add these QickVarType because their '
                'types are not compatible.')

        if isinstance(self, QickExpression) and \
            self.operator == '+' and \
            isinstance(other, QickConstType):
            # addition associative property that can save some instructions
            # e.g. self = (x + 3), other = 5
            # e.g. result = (x + 3) + 5 = x + (3 + 5) = x + 8
            if isinstance(self.left, QickConstType):
                return QickExpression(
                        left=self.right,
                        operator='+',
                        right=other + self.left
                    )
            elif isinstance(self.right, QickConstType):
                return QickExpression(
                        left=self.left,
                        operator='+',
                        right=other + self.right
                    )

        return QickExpression(left=self, operator='+', right=other)

    def __radd__(self, other) -> QickExpression:
        return self.__add__(other)

    def __sub__(self, other, swap: bool = False) -> QickExpression:
        if not self.typecastable(other):
            raise TypeError('Cannot subtract these QickVarType because their '
                'types are not compatible.')

        # TODO implement analogous associative property as in __add__

        # swap the orientation if called from __rsub__
        if swap:
            return QickExpression(left=other, operator='-', right=self)
        else:
            return QickExpression(left=self, operator='-', right=other)

    def __rsub__(self, other) -> QickExpression:
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

    def scopecast(self):
        """Regs don't get their scope changed - do nothing."""
        pass

    def typecast(self, other: Union[QickType, Type]) -> QickReg:
        """Convert self into the qick type of other."""
        if self.held_type is None:
            self.held_type = self.qick_type_class(other)
            return self

        if self.qick_type() == self.qick_type_class(other):
            return self
        else:
            raise TypeError('QickReg cannot be typecast.')

    def _assign(self, value: Union[int, QickType]):
        if self.held_type is None:
            if isinstance(value, QickType):
                self.held_type = value.qick_type()
            elif isinstance(value, int):
                self.held_type = None
            else:
                raise TypeError('value must be a QickType or int.')

        assignment = QickAssignment(reg=self, rhs=value)

        return str(assignment)

    def assign(self, value: Union[int, QickType]):
        """Assign a value to a register.

        Args:
            value: The value to assign.

        """
        self.scope.code.asm += self._assign(value=value)

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

class QickExpression(QickVarType):
    """Represents a mathematical expression containing QickType."""
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
                raise TypeError('Could not create new QickExpression because '
                    'left and right could not be typecast.')

        self.left = left
        self.right = right
        self.operator = operator
        self.held_type: QickConstType = left.qick_type()

    def __str__(self):
        raise ValueError('QickExpression cannot be converted into a string '
            'key. Use pre_asm_key() and exp_asm_key().')

    def _qick_copy(self, scopes: Dict, new_ids: list, new_ids_lut: Dict):
        """Implements deepcopy-like behavior.

        Args:
            scopes: Values are QickCode that are in the scope of what's being
                copied, keys are the corresponding QickCode.key()
            new_ids: List of new ids.
            new_ids_lut: Values are QickObject that have been assigned a new id,
                keys are their corresponding old QickObject.key() before
                reassignment.

        """
        super()._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)
        if isinstance(self.left, QickType):
            self.left._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)
        if isinstance(self.right, QickType):
            self.right._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)

    def pre_asm_key(self) -> str:
        return self.key(subid='pre_asm')

    def exp_asm_key(self) -> str:
        return self.key(subid='exp_asm')

    def scopecast(self):
        """Change the scope of this object to the current scope."""
        self._connect_scope()
        self.left.scopecast()
        self.right.scopecast()

    def typecast(self, other: Union[QickType, Type]) -> QickExpression:
        """Return self converted into the type of other."""
        try:
            left = self.left.typecast(other)
            right = self.right.typecast(other)
        except TypeError as err:
            raise TypeError('QickExpression failed to typecast into new '
                'type.') from err
        return type(self)(left=left, operator=self.operator, right=right)

class QickAssignment(QickObject):
    """Represents assignment of a value containing QickType to a register."""
    def __init__(
            self,
            reg: QickReg,
            rhs: Union[int, QickType],
            *args,
            **kwargs
        ):
        """
        Args:
            reg: Register being assigned.
            rhs: Right-hand-side of register assignment.
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, **kwargs)
        self.reg = reg
        self.rhs = rhs

    def _qick_copy(self, scopes: Dict, new_ids: list, new_ids_lut: Dict):
        """Implements deepcopy-like behavior.

        Args:
            scopes: Values are QickCode that are in the scope of what's being
                copied, keys are the corresponding QickCode.key()
            new_ids: List of new ids.
            new_ids_lut: Values are QickObject that have been assigned a new id,
                keys are their corresponding old QickObject.key() before
                reassignment.

        """
        super()._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)
        self.reg._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)
        if isinstance(self.rhs, QickType):
            self.rhs._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)

    def qick_type(self) -> Optional[QickConstType]:
        return self.rhs.qick_type()

    def scopecast(self):
        """Change the scope of this object to the current scope."""
        self._connect_scope()
        self.reg.scopecast()
        self.rhs.scopecast()

    def typecast(self, other: Union[QickType, Type]) -> QickExpression:
        """Return self converted into the type of other."""
        try:
            typecast_rhs = self.rhs.typecast(other)
        except TypeError as err:
            raise TypeError('QickAssignment failed to typecast into new '
                'type.') from err
        return type(self)(reg=self.reg, rhs=typecast_rhs)

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
            soccfg: Optional[QickConfig] = None,
            *args,
            **kwargs
        ):
        """

        Args:
            offset: Offset to add to all pulses in this code block.
            length: Length of code block.
            name: Optional name that will be added as a comment at the top of
                the code segment.
            soccfg: Qick firmware config.
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, scope_required=False, **kwargs)
        # assembly code string
        self.asm = ''
        # key-value pairs
        self.kvp = {}

        self.name = name
        self.soccfg = soccfg

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
            elif offset is None:
                self.offset = QickTime(0)
            elif isinstance(offset, QickTime) or isinstance(offset, QickVarType):
                self.offset = offset
            else:
                raise ValueError('offset has an invalid type')

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
                v.scope.code = self

    def inc_ref(self):
        """Increment the reference by the length of this code block."""
        with QickScope(code=self):
            # the amount to inc_ref by
            ref_reg = QickReg()
            ref_reg.assign(self.length)
            self.asm += f'TIME inc_ref {ref_reg}\n'

    def update_key(self, old_key: str, new_obj: QickType):
        """Update the given key in the assembly code and key-value pair
        dictionary of this QickCode, and then recursively for all QickCode
        within this QickCode.

        Args:
            old_key: The key that needs to be updated.
            new_obj: The object that will take the place of the object pointed
                to by old_key.

        """
        # get the new key
        new_key = new_obj._key()
        # replace all instances of the old key with the new key in the assembly code
        self.asm = self.asm.replace(old_key, new_key)

        if old_key in self.kvp:
            # delete the old key
            del self.kvp[old_key]
            # replace the old key with the new
            self.kvp[new_key] = new_obj

        # recursively fix other instances of old_key
        for qick_obj in self.kvp.values():
            if isinstance(qick_obj, QickCode):
                qick_obj.update_key(old_key=old_key, new_obj=new_obj)

    def _qick_copy(self, scopes: Dict, new_ids: list, new_ids_lut: Dict):
        """Implements deepcopy-like behavior.

        Args:
            scopes: Values are QickCode that are in the scope of what's being
                copied, keys are the corresponding QickCode.key()
            new_ids: List of new ids.
            new_ids_lut: Values are QickObject that have been assigned a new id,
                keys are their corresponding old QickObject.key() before
                reassignment.

        """
        scopes[self._key()] = self

        super()._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)

        for qick_obj in self.kvp.values():
            qick_obj._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)

    def qick_copy(self):
        """Implements deepcopy-like behavior. Replace all qpc id's with new
        id's, unless the object is from outside the scope."""

        # copy the object
        new_code = deepcopy(self)

        # put the new code in the current scope
        new_code._connect_scope()
        # give the code a new id
        new_code._alloc_qpc_id()

        scopes = {}
        new_ids = []
        new_ids_lut = {self._key(): new_code}
        # process all sub objects
        new_code._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)

        # for the objects that acquired new keys, update them in the kvp and asm
        for old_key, new_obj in new_ids_lut.items():
            new_code.update_key(old_key=old_key, new_obj=new_obj)

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
            port_offset = QickTime(0)
            port = io
        else:
            raise ValueError('io has invalid type.')

        return port, port_offset

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
            port, port_offset = self.deembed_io(ch)
            self.asm += f'// setting trigger port {port} to {state}\n'
            if time is not None:
                if isinstance(time, Number):
                    time = QickTime(time)
                # set the play time of the trig
                out_usr_time = QickReg(reg='out_usr_time')
                out_usr_time.assign(self.offset + port_offset + time)

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
            port, port_offset = self.deembed_io(ch)

            self.asm += f'// pulsing RF port {port}\n'

            if time is not None:
                if isinstance(time, Number):
                    time = QickTime(time)
                # set the play time of the pulse
                out_usr_time = QickReg(reg='out_usr_time')
                out_usr_time.assign(self.offset + port_offset + time)

            if length is not None:
                if isinstance(length, Number):
                    length = QickLength(val=length)
                # set the length of the pulse
                w_length = QickReg(reg='w_length')
                w_length.assign(length)

            if freq is not None:
                if isinstance(freq, Number):
                    freq = QickFreq(freq)
                # set the frequency of the pulse
                w_freq = QickReg(reg='w_freq')
                w_freq.assign(freq)

            if amp is not None:
                # set the amplitude of the pulse
                w_gain = QickReg(reg='w_gain')
                w_gain.assign(amp)

            # set the configuration settings of the pulse
            w_conf = QickReg(reg='w_conf')
            w_conf.assign(self.sig_gen_conf(outsel='dds', mode='oneshot', stdysel='zero', phrst=0))

            self.asm += f'WPORT_WR p{port} r_wave\n'

    def epoch_offset(self, offset: QickType):
        """Find all out_usr_time assignments and offset them.

        Args:
            offset: The amount to add to each out_usr_time.

        """
        for old_key, qick_obj in self.kvp.copy().items():
            if isinstance(qick_obj, QickCode):
                qick_obj.epoch_offset(offset)
            elif isinstance(qick_obj, QickAssignment) and \
                qick_obj.reg.reg == 'out_usr_time':
                    new_rhs = qick_obj.rhs + offset
                    new_rhs.scopecast()
                    qick_obj.rhs = new_rhs

    def add(self, code: QickCode):
        """Set another code block to run sequentially after this block.

        Args:
            code: Code to run after this code.

        """
        with QickScope(code=self):
            # make a copy so we don't modify the original code
            code = code.qick_copy()

            code.epoch_offset(offset=self.length)

            self.length += code.length
            self.asm += str(code)

        if self.name is None and code.name is not None:
            self.name = code.name
        elif self.name is not None and code.name is not None:
            self.name = f'({self.name} + {code.name})'

    def parallel(self, code: QickCode, auto_length: bool = True):
        """Set another code block to run in parallel with this block.
        The code of the right operand will be placed after the left. The length
        is set to that of the longest operand, unless auto_length is overriden.

        Args:
            code: Code to run in parallel with this code.
            auto_length: If false, don't modify the length. If true, set the
                length to that of the longer code block. If that cannot be
                determined, don't modify the length.

        """
        with QickScope(code=self):
            # make a copy so we don't modify the original code
            code = code.qick_copy()

            if auto_length:
                if isinstance(self.length, QickConstType) and \
                    isinstance(code.length, QickConstType) and \
                    code.length.val > self.length.val:
                    self.length = code.length

            self.asm += code.asm
            self.merge_kvp(code.kvp)

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
