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

import numpy as np
from qick import QickConfig
import sympy

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
            # inherit soc from parent scope
            parent_soc = qpc_scope[-1].code.soc
            this_soc = self.code.soc
            if this_soc is None:
                self.code.soc = parent_soc
            # inherit iomap from parent scope
            parent_iomap = qpc_scope[-1].code.iomap
            this_iomap = self.code.iomap
            if this_iomap is None:
                self.code.iomap = parent_iomap

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

class QickType:
    """Represents the type for a QickObject."""
    def __init__(
            self,
            type_class: Type,
            gen_ch: Optional[QickIODevice, QickIO, int] = None,
            ro_ch: Optional[QickIODevice, QickIO, int] = None,
        ):
        """

        Args:
            type_class: Class associated with this time.
            gen_ch: The generator channel associated with this object type.
            ro_ch: The readout channel associated with this object type.

        """
        self.type_class = type_class
        self.gen_ch = gen_ch
        self.ro_ch = ro_ch

class QickBaseType(QickObject, ABC):
    """Base class for fundamental types used in the qick firmware."""

    @abstractmethod
    def qick_type(self) -> Optional[QickType]:
        """Returns the QickType of this object."""
        pass

    @abstractmethod
    def typecast(self, other: Union[QickBaseType, Type]):
        """Return self converted into the qick type of other."""
        pass

    def scopecast(self):
        """Change the scope of this object to the current scope."""
        self._connect_scope()

    def typecastable(self, other: QickBaseType) -> bool:
        """Return true if self can be typecast into the QickType of other.

        Args:
            other: A QickBaseType object.

        """
        if self.qick_type().type_class is None:
            return True
        elif other.qick_type().type_class is None:
            return False
        else:
            return self.qick_type().type_class == other.qick_type().type_class

class QickConstType(QickBaseType, ABC):
    """Base class for types that have a constant value."""
    def __init__(
            self,
            val: Number,
            *args,
            gen_ch: Optional[QickIODevice, QickIO, int] = None,
            ro_ch: Optional[QickIODevice, QickIO, int] = None,
            **kwargs
        ):
        """

        Args:
            val: Value in SI units (s, Hz, etc.).
            args: Additional arguments passed to super constructor.
            gen_ch: The generator channel associated with this object.
            ro_ch: The readout channel associated with this object.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, **kwargs)

        if not isinstance(val, Number):
            raise TypeError('val must be a number.')
        self.val = val
        self._qick_type = QickType(
            type_class=self.__class__,
            gen_ch=gen_ch,
            ro_ch=ro_ch,
        )

    def qick_type(self) -> Optional[QickType]:
        """Returns the QickType of this object."""
        return self._qick_type

    def typecast(self, other: QickBaseType) -> QickConstType:
        """Return a copy of self converted into the qick type of other."""
        if self.typecastable(other):
            return other.qick_type().type_class(
                val=self.val,
                gen_ch=other.qick_type().gen_ch,
                ro_ch=other.qick_type().ro_ch
            )
        else:
            raise TypeError('Cannot cast to type of other because their types '
                'are incompatible.')

    def _gen_ro_ch(self) -> tuple[Optional[int], Optional[int]]:
        """Get the generator and readout firmware channel numbers."""
        gen_ch = self.qick_type().gen_ch
        if isinstance(gen_ch, QickIO):
            if self.scope.code.iomap is None:
                raise RuntimeError('iomap is not available.')
            else:
                gen_ch = self.scope.code.iomap.mappings[gen_ch.channel_type][gen_ch.channel].port
        elif gen_ch is None or isinstance(gen_ch, int):
            pass
        else:
            raise ValueError('gen_ch has an invalid type.')

        ro_ch = self.qick_type().ro_ch
        if isinstance(ro_ch, QickIO):
            if self.scope.code.iomap is None:
                raise RuntimeError('iomap is not available.')
            else:
                ro_ch = self.scope.code.iomap.mappings[ro_ch.channel_type][ro_ch.channel].port
        elif ro_ch is None or isinstance(ro_ch, int):
            pass
        else:
            raise ValueError('ro_ch has an invalid type.')

        return (gen_ch, ro_ch)

    def clocks(self) -> int:
        """Convert to an integer number of device clock cycles."""
        if self.scope.code.soc is None:
            raise RuntimeError('Tried to convert to clock cycles but soc is '
                'not available.')
        else:
            gen_ch, ro_ch = self._gen_ro_ch()
            return self._clocks(gen_ch=gen_ch, ro_ch=ro_ch)

    def _clocks(self, gen_ch: int, ro_ch: int) -> int:
        """Convert to an integer number of device clock cycles. This should be
        overriden by subclasses."""
        raise RuntimeError('Tried to get the clocks() of an invalid type.')

    def actual(self) -> Number:
        """Convert to the actual value (in SI units) after rounding to the
        nearest clock cycle."""
        gen_ch, ro_ch = self._gen_ro_ch()
        cycles = self._clocks(gen_ch=gen_ch, ro_ch=ro_ch)
        return self._actual(cycles=cycles, gen_ch=gen_ch, ro_ch=ro_ch)

    def _actual(self, cycles: int, gen_ch: int, ro_ch: int):
        """Convert to the actual value (in SI units) after rounding to the
        nearest clock cycle. This should be overriden by subclasses."""
        raise RuntimeError('Tried to get the actual() of an invalid type.')

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

        return self.qick_type().type_class(val=self.val + other_val)

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
            return self.qick_type().type_class(val=other_val - self.val)
        else:
            return self.qick_type().type_class(val=self.val - other_val)

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

        return self.qick_type().type_class(val=self.val * other_val)

    def __rmul__(self, other) -> QickConstType:
        return self.__mul__(other)

    def _to_sympy(self, regs: Dict):
        """Create a sympy expression from a QickExpression.

        Args:
            regs: Dict mapping register _key() to register objects utilized
                during the conversion

        """
        return self.val

class QickInt(QickConstType):
    """Represents an integer."""
    pass

class QickTime(QickConstType):
    """Represents a time."""
    def typecastable(self, other: QickBaseType) -> bool:
        """Return true if self can be typecast into the QickType of other.

        Args:
            other: A QickBaseType object.

        """
        if self.qick_type().type_class is None:
            return True
        elif other.qick_type().type_class is None:
            return False
        else:
            # freely convert between other types of QickTimes
            return issubclass(self.qick_type().type_class, QickTime) and \
                issubclass(other.qick_type().type_class, QickTime)

    def _clocks(self, gen_ch: Optional[int], ro_ch: Optional[int]):
        """Convert to an integer number of device clock cycles."""
        return self.scope.code.soc.us2cycles(
            us=self.val * 1e6,
            gen_ch=gen_ch,
            ro_ch=ro_ch
        )

    def _actual(self, cycles: int, gen_ch: Optional[int], ro_ch: Optional[int]):
        """Convert to the actual value (in SI units) after rounding to the
        nearest clock cycle."""
        return self.scope.code.soc.cycles2us(
            cycles=cycles,
            gen_ch=gen_ch,
            ro_ch=ro_ch
        ) / 1e6

class QickFreq(QickConstType):
    """Represents a frequency."""
    def _clocks(self, gen_ch: Optional[int], ro_ch: Optional[int]):
        """Convert to an integer number of device clock cycles."""
        if gen_ch is None:
            raise RuntimeError('QickFreq was never associated with a '
                'generator channel.')
        return self.scope.code.soc.freq2reg(
            f=self.val / 1e6,
            gen_ch=gen_ch,
            ro_ch=ro_ch
        )

    def _actual(self, cycles: int, gen_ch: Optional[int], ro_ch: Optional[int]):
        """Convert to the actual value (in SI units) after rounding to the
        nearest clock cycle."""
        return self.scope.code.soc.reg2freq(
            r=cycles,
            gen_ch=gen_ch,
        ) * 1e6

class QickPhase(QickConstType):
    """Represents a phase in degrees."""
    def _clocks(self, gen_ch: Optional[int], ro_ch: Optional[int]):
        """Convert to an integer number of device clock cycles."""
        if gen_ch is None:
            raise RuntimeError('QickPhase was never associated with a '
                'generator channel.')
        return self.scope.code.soc.deg2reg(
            deg=self.val,
            gen_ch=gen_ch,
            ro_ch=ro_ch
        )

    def _actual(self, cycles: int, gen_ch: Optional[int], ro_ch: Optional[int]):
        """Convert to the actual value (in degrees) after rounding to the
        nearest clock cycle."""
        return self.scope.code.soc.reg2deg(
            r=cycles,
            gen_ch=gen_ch,
        )

class QickVarType(QickBaseType):
    """Base class for variable types."""
    def __init__(self, *args, **kwargs):
        """

        Args:
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, **kwargs)
        self.held_type: Optional[QickType] = QickType(type_class=None)

    def qick_type(self) -> Optional[QickType]:
        return self.held_type

    def __add__(self, other) -> QickExpression:
        if not self.typecastable(other):
            raise TypeError('Cannot add these QickVarType because their '
                'types are not compatible.')

        return QickExpression(left=self, operator='+', right=other).simplify()

    def __radd__(self, other) -> QickExpression:
        return self.__add__(other)

    def __sub__(self, other, swap: bool = False) -> QickExpression:
        if not self.typecastable(other):
            raise TypeError('Cannot subtract these QickVarType because their '
                'types are not compatible.')

        # swap the orientation if called from __rsub__
        if swap:
            return QickExpression(left=other, operator='-', right=self).simplify()
        else:
            return QickExpression(left=self, operator='-', right=other).simplify()

    def __rsub__(self, other) -> QickExpression:
        return self.__add__(other, swap=True)

    def __mul__(self, other) -> QickConstType:
        # TODO
        return NotImplemented

    def __rmul__(self, other) -> QickConstType:
        return self.__mul__(other)

class QickReg(QickVarType):
    """Represents a register in the tproc."""
    def __init__(
            self,
            *args,
            val: Optional[QickBaseType] = None,
            reg: Optional[str] = None,
            **kwargs
        ):
        """

        Args:
            reg: Register to use. If None, a register will be
                automatically assigned.
            val: If not None, assign the variable to this value.
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, **kwargs)
        self.reg = reg
        if val is not None:
            self.assign(val)

    def scopecast(self):
        """Regs don't get their scope changed - do nothing."""
        pass

    def typecastable(self, other: QickBaseType) -> bool:
        """Return true if self can be typecast into the QickType of other.

        Args:
            other: A QickBaseType object.

        """
        if self.qick_type().type_class is None:
            return True
        elif other.qick_type().type_class is None:
            return False
        else:
            # registers require stricter typecasting rules than other objects
            # the class, gen, and ro channels must all match
            # this prevents a situation such as, e.g.:
            # r0 = 5 clock cycles (in units of generator 0)
            # r1 = 10 clock cycles (in units of generator 1)
            # r2 = r0 + r1 (this would be an invalid result!)
            return self.qick_type().type_class == other.qick_type().type_class and \
                self.qick_type().gen_ch == other.qick_type().gen_ch and \
                self.qick_type().ro_ch == other.qick_type().ro_ch

    def typecast(self, other: QickBaseType) -> QickReg:
        """Convert self into the QickType of other."""
        if self.typecastable(other):
            self.held_type = other.qick_type()
            return self
        else:
            raise TypeError('QickReg could not be typecast.')

    def _assign(self, value: QickBaseType):
        if self.typecastable(value):
            assignment = QickAssignment(reg=self.typecast(value), rhs=value)
            return str(assignment)
        else:
            raise TypeError('reg cannot be typecast into QickType of value.')

    def assign(self, value: QickBaseType):
        """Assign a value to a register.

        Args:
            value: The value to assign.

        """
        self.scope.code.asm += self._assign(value=value)

    # TODO use this implementation once multiplication / ARITH is implemented
    # def _to_sympy(self, regs: Dict):
    #     """Create a sympy expression from a QickExpression.

    #     Args:
    #         regs: Dict mapping register _key() to register objects utilized
    #             during the conversion

    #     """
    #     regs[self._key()] = self
    #     return sympy.Symbol(self._key())

    def _to_sympy(self, regs: Dict):
        """Create a sympy expression from a QickExpression.

        Args:
            regs: Dict mapping register _key() to register objects utilized
                during the conversion

        """
        # make each register unique in sympy so it doesn't consolidate them
        # into a product term
        n = 0
        while self._key() + str(n) in regs:
            n += 1
        key = self._key() + str(n)
        regs[key] = self
        return sympy.Symbol(key)

class QickSweptReg(QickReg):
    """Represents the arguments to a swept variable."""
    def __init__(
            self,
            start: Union[QickConstType, QickVarType],
            stop: Union[QickConstType, QickVarType],
            step: Union[QickConstType, QickVarType],
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
        
        if not start.typecastable(stop):
            raise ValueError('start and stop have different type.')
        if not start.typecastable(step):
            raise ValueError('start and step have different type.')

        self.typecast(start)

        self.start = start
        self.stop = stop
        self.step = step

    def actual(self):
        """Return a numpy array of the actual points that will be swept over."""
        start_cyc = self.start.clocks()
        stop_cyc = self.stop.clocks()
        step_cyc = self.step.clocks()

        gen_ch, ro_ch = self.start._gen_ro_ch()
        # length of one cycle in SI units
        one_cycle = self.start._actual(cycles=1, gen_ch=gen_ch, ro_ch=ro_ch)

        return one_cycle * np.arange(start_cyc, stop_cyc, step_cyc)

class QickExpression(QickVarType):
    """Represents a mathematical expression containing QickBaseType."""
    def __init__(
            self,
            left: QickBaseType,
            operator: str,
            right: QickBaseType,
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
            right = right.typecast(left)
        except TypeError:
            try:
                left = left.typecast(right)
            except TypeError:
                raise TypeError('Could not create new QickExpression because '
                    'left and right could not be typecast to the same type.')

        self.left = left
        self.right = right
        self.operator = operator
        self.held_type: QickType = left.qick_type()

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
        if isinstance(self.left, QickBaseType):
            self.left._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)
        if isinstance(self.right, QickBaseType):
            self.right._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)

    def pre_asm_key(self) -> str:
        return self.key(subid='pre_asm')

    def exp_asm_key(self) -> str:
        return self.key(subid='exp_asm')

    def scopecast(self):
        """Change the scope of this object to the current scope."""
        self._connect_scope()
        if isinstance(self.left, QickBaseType):
            self.left.scopecast()
        if isinstance(self.right, QickBaseType):
            self.right.scopecast()

    def typecast(self, other: Union[QickBaseType, Type]) -> QickExpression:
        """Return self converted into the type of other."""
        try:
            if isinstance(self.left, QickBaseType):
                left = self.left.typecast(other)
            else:
                left = self.left

            if isinstance(self.right, QickBaseType):
                right = self.right.typecast(other)
            else:
                right = self.right

        except TypeError as err:
            raise TypeError('QickExpression failed to typecast into new '
                'type.') from err
        return type(self)(left=left, operator=self.operator, right=right)

    def _to_sympy(self, regs: Dict):
        """Create a sympy expression from a QickExpression.

        Args:
            regs: Dict mapping register _key() to register objects utilized
                during the conversion

        """
        if isinstance(self.left, QickBaseType):
            left = self.left._to_sympy(regs=regs)
        else:
            left = self.left

        if isinstance(self.right, QickBaseType):
            right = self.right._to_sympy(regs=regs)
        else:
            right = self.right

        if self.operator == '+':
            return left + right
        elif self.operator == '-':
            return left - right
        elif self.operator == '*':
            return left * right
        else:
            raise RuntimeError('Unknown operator.')

    @staticmethod
    def _from_sympy(exp: sympy.Expr, regs: Dict, qick_type: QickType):
        """Create a QickExpression from a sympy expression.

        Args:
            regs: Dict mapping register _key() to register objects utilized
                during the conversion
            qick_type: QickType of objects in the original
                QickExpression.

        """
        if isinstance(exp, sympy.core.add.Add) or \
                isinstance(exp, sympy.core.mul.Mul):
            # create new expressions with the args split in half
            split = round(len(exp.args)/2)
            left_args = exp.args[:split]
            right_args = exp.args[split:]

            # left side expression with half of the args
            left_sympy_exp = type(exp)(*left_args)
            left_qick_exp = QickExpression._from_sympy(
                exp=left_sympy_exp,
                regs=regs,
                qick_type=qick_type
            )

            # right side expression with the other half of the args
            right_sympy_exp = type(exp)(*right_args)
            right_qick_exp = QickExpression._from_sympy(
                exp=right_sympy_exp,
                regs=regs,
                qick_type=qick_type
            )

            if isinstance(exp, sympy.core.add.Add):
                op = '+'
            elif isinstance(exp, sympy.core.mul.Mul):
                op = '*'

            return QickExpression(
                left=left_qick_exp,
                operator=op,
                right=right_qick_exp
            )

        elif isinstance(exp, sympy.core.power.Pow):
            # TODO
            raise RuntimeError('Exponentiation not yet implemented')
        elif isinstance(exp, sympy.core.symbol.Symbol):
            return regs[str(exp)]
        elif isinstance(exp, sympy.core.numbers.Integer):
            return qick_type.type_class(val=int(exp))
        elif isinstance(exp, sympy.core.numbers.Float):
            return qick_type.type_class(val=float(exp))
        else:
            raise RuntimeError('Unrecognized expression type in sympy conversion.')

    def simplify(self) -> QickExpression:
        """Simplify a QickExpression using sympy."""

        # store the mapping between register ids and register objects
        # for later reconstructin of the expression
        regs = {}
        
        # generate a sympy expression constructed from this expression
        sym_exp = self._to_sympy(regs=regs)

        # simplify the expression
        sym_exp.simplify()

        # convert the sympy expression back into a QickExpression
        return QickExpression._from_sympy(
            exp=sym_exp,
            regs=regs,
            qick_type=self.qick_type()
        )

class QickAssignment(QickObject):
    """Represents assignment of a value containing QickBaseType to a register."""
    def __init__(
            self,
            reg: QickReg,
            rhs: Union[int, QickBaseType],
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
        if isinstance(self.rhs, QickBaseType):
            self.rhs._qick_copy(scopes=scopes, new_ids=new_ids, new_ids_lut=new_ids_lut)

    def qick_type(self) -> Optional[QickType]:
        return self.rhs.qick_type()

    def scopecast(self):
        """Change the scope of this object to the current scope."""
        self._connect_scope()
        self.reg.scopecast()
        self.rhs.scopecast()

    def typecastable(self, other: QickBaseType) -> bool:
        """Return true if self can be typecast into the QickType of other.

        Args:
            other: a QickBaseType object.

        """
        return False

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
            offset: Optional[Number, QickBaseType] = None,
            length: Optional[Number, QickBaseType] = None,
            name: Optional[str] = None,
            soc: Optional[QickConfig] = None,
            iomap: Optional[QickIOMap] = None,
            *args,
            **kwargs
        ):
        """

        Args:
            offset: Offset to add to all pulses in this code block.
            length: Length of code block.
            name: Optional name that will be added as a comment at the top of
                the code segment.
            soc: Qick SoC object.
            iomap: Mapping between input/output names and their firmware ports.
            args: Additional arguments passed to super constructor.
            kwargs: Additional keyword arguments passed to super constructor.

        """
        super().__init__(*args, scope_required=False, **kwargs)
        # assembly code string
        self.asm = ''
        # key-value pairs
        self.kvp = {}

        self.name = name
        self.soc = soc
        self.iomap = iomap

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
            ref_reg = QickReg()
            ref_reg.assign(self.length)
            self.asm += f'TIME inc_ref {ref_reg}\n'
            # reset the length
            self.length = QickTime(0)

    def update_key(self, old_key: str, new_obj: QickBaseType):
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
        if isinstance(io, QickIO):
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

    def sig_gen_conf(
            self,
            outsel = 'dds',
            mode = 'oneshot',
            stdysel = 'zero',
            phrst = False
        ) -> int:
        """Return the firmware register value for the given signal
        generator config settings.

        Args:
            outsel: 'dds' to output a sine wave, 'input' to output
                the value stored in waveform memory, 'product' to output
                the product of 'dds' and 'input', and 'zero' to output 0.
            mode: 'oneshot' to play the pulse normally, 'periodic' to play
                the pulse, then repeat it until another pulse is played
                on this channel.
            stdysel: 'last' to continue playing the last sample of the pulse
                when the pulse finishes, 'zero' to play 0 after the pulse
                finishes.
            phrst: True to reset the phase, False to retain the phase from the
                free-running DDS counter.

        """
        outsel_reg = {'product': 0, 'dds': 1, 'input': 2, 'zero': 3}[outsel]
        mode_reg = {'oneshot': 0, 'periodic': 1}[mode]
        stdysel_reg = {'last': 0, 'zero': 1}[stdysel]
        if phrst:
            phrst = 1
        else:
            phrst = 0

        mc = phrst * 0b10000 + stdysel_reg * 0b01000 + mode_reg * 0b00100 + outsel_reg
        return QickInt(mc)

    def rf_pulse(
            self,
            ch: Union[QickIODevice, QickIO, int],
            time: Optional[Union[Number, QickTime, QickVarType]],
            length: Optional[Union[Number, QickTime, QickVarType]],
            amp: Optional[int, QickInt, QickVarType],
            freq: Optional[Union[Number, QickFreq, QickVarType]],
            phase: Optional[Union[Number, QickPhase, QickVarType]],
            **conf,
        ):
        """Generate an RF pulse.

        Args:
            ch: QickIODevice, QickIO, or port to output an RF pulse.
            time: Time at which to play the pulse. Pass a time (s) or other
                Qick type. Set to None to use the value currently in
                out_usr_time.
            length: Length of the RF pulse. Pass a time (s) or other Qick
                type. Set to None to use the value currently in w_length.
            amp: RF amplitude. Pass an integer (-32,768 to 32,767) or other
                Qick type. Set to None to use the value currently stored in
                w_gain.
            freq: RF frequency of the pulse. Pass a frequency (s) or other
                QickFreq, Qick type. Set to None to use the value currently
                in w_freq.
            phase: Phase of the RF pulse. Pass a phase (deg) or other Qick
                type. Set to None to use the value currently in w_phase.
            conf: Keyword arguments to pass to sig_gen_conf(). Otherwise the
                default values will be used.

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
                    length = QickTime(val=length, gen_ch=ch)
                elif isinstance(length, QickTime):
                    if length.gen_ch is None:
                        # set the gen_ch if it wasn't set yet
                        length.gen_ch = ch
                # set the length of the pulse
                w_length = QickReg(reg='w_length')
                w_length.assign(length)

            if amp is not None:
                if isinstance(amp, int):
                    amp = QickInt(amp)
                # set the amplitude of the pulse
                w_gain = QickReg(reg='w_gain')
                w_gain.assign(amp)

            if freq is not None:
                if isinstance(freq, Number):
                    freq = QickFreq(freq, gen_ch=ch)
                elif isinstance(freq, QickFreq):
                    if freq.gen_ch is None:
                        freq.gen_ch = ch
                # set the frequency of the pulse
                w_freq = QickReg(reg='w_freq')
                w_freq.assign(freq)

            if phase is not None:
                if isinstance(phase, Number):
                    phase = QickPhase(phase, gen_ch=ch)
                elif isinstance(phase, QickPhase):
                    if phase.gen_ch is None:
                        phase.gen_ch = ch
                # set the phase of the pulse
                w_phase = QickReg(reg='w_phase')
                w_phase.assign(phase)

            # set the configuration settings of the pulse
            w_conf = QickReg(reg='w_conf')
            w_conf.assign(self.sig_gen_conf(**conf))

            self.asm += f'WPORT_WR p{port} r_wave\n'

    def epoch_offset(self, offset: QickBaseType):
        """Find all out_usr_time assignments and offset them.

        Args:
            offset: The amount to add to each out_usr_time.

        """
        for old_key, qick_obj in self.kvp.copy().items():
            if isinstance(qick_obj, QickCode):
                qick_obj.epoch_offset(offset)
            elif isinstance(qick_obj, QickAssignment) and qick_obj.reg.reg == 'out_usr_time':
                with QickScope(code=self):
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
                    self.length.scopecast()

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
