"""User-defined functions: how a function written in Python becomes a function in formulas.

A function is a subclass of ``UserFunction``::

    class SQUARE(UserFunction):
        description = "A number times itself"
        examples = (Example("=SQUARE(4)", 16),)

        def call(self, x: float) -> float:
            return x * x

and a cell can then say ``=SQUARE(A1)``. The contract:

``name``         what formulas call it; the class name unless ``name = "..."`` is set. Upper case in the end, letters,
                 digits, underscore and dot, starting with a letter. The names of the core's own functions (``IF``,
                 ``XLOOKUP`` ...) cannot be taken.
``call(*args)``  does the work. The signature says how many arguments a formula may pass: ``call(self, a, b=1)`` takes
                 one or two, ``call(self, *xs)`` any number. Annotations say what each argument should be and the
                 formula's value is converted for you:

                   float       a number; an empty cell is 0.0; text is ``#VALUE!``
                   int         a number cut at the decimal point; an empty cell is 0
                   bool        TRUE or FALSE; a number is TRUE unless it is 0
                   str         any value as text; an empty cell is ""
                   Range       the cells of ``A1:C5`` (a single value arrives as a range of one cell)
                   X | None    like X, but an empty cell arrives as None
                   (none)      the value as it is: int, float, bool, str, None or a Range

                 A function that takes a ``Range`` reads only the cells that hold something (``range.numbers()``,
                 ``range.present()``), so ``SUM(A:A)`` costs what the column holds, not a million rows.
return           an int, float, bool, text or a ``Range``. Anything else (``None`` too) is ``#VALUE!``.
errors           ``raise FunctionError("#NUM!", "why")`` for an Excel-style code with a reason; ``ZeroDivisionError`` is
                 ``#DIV/0!``, ``ValueError`` and ``OverflowError`` are ``#NUM!``, ``TypeError`` is ``#VALUE!``, any
                 other exception is ``#ERROR!`` (the traceback goes to the log).
``description``  one line: what it does. Required, as the tooltip is made from it (``get_tooltip``).
``examples``     at least one ``Example``: formulas with the result they give. They are the help topic's worked example
                 (``get_help``) and they are run as tests when the function is loaded, so help cannot go stale.

The function must be **pure**: the same arguments, the same result, nothing else read. Results are recalculated from
the document alone, by the server, whenever an input changes.

Functions are trusted code: they run inside the server with all its privileges and are installed by whoever runs
the server, never taken from a document or from a network connection.
"""

from __future__ import annotations

import inspect
import logging
import math
import numbers
import types
import typing
from collections.abc import Mapping
from dataclasses import dataclass, field

from ..values import NUM, SYNTAX, VALUE, ErrorValue, FormulaError, Value, fits_int, format_value
from .range import Range

log = logging.getLogger("claudia_computes.functions")


class FunctionError(FormulaError):
    """Raise this from ``call`` to make the cell show an error code and say why."""

    def __init__(self, code: str = VALUE, message: str = ""):
        super().__init__(code, message)


@dataclass(frozen=True)
class Example:
    """A formula with the result it gives. ``cells`` are the cells it reads, by address (``{"A1": 1, "A2": 2}``)."""

    formula: str
    result: Value
    cells: Mapping[str, Value] = field(default_factory=dict)
    note: str = ""


class UserFunction:
    """The base of every function a user writes. See the module documentation."""

    name: str | None = None
    description: str = ""
    examples: tuple[Example, ...] = ()

    def call(self, *args):
        raise NotImplementedError(f"{type(self).__name__} must define call()")


@dataclass(frozen=True, slots=True)
class _Param:
    name: str
    kind: str  # float int bool str range any
    nullable: bool = False
    variadic: bool = False
    has_default: bool = False


_KINDS = {bool: "bool", float: "float", int: "int", str: "str", Range: "range"}


def _kind_of(annotation: object) -> tuple[str, bool]:
    nullable = False
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        members = [a for a in typing.get_args(annotation) if a is not type(None)]
        nullable = len(members) != len(typing.get_args(annotation))
        if len(members) != 1:
            raise ValueError(f"unsupported annotation {annotation!r}")
        annotation = members[0]
    if annotation is inspect.Parameter.empty or annotation is typing.Any or annotation is object:
        return "any", nullable
    if annotation in _KINDS:
        return _KINDS[annotation], nullable
    raise ValueError(f"unsupported annotation {annotation!r} (use float, int, bool, str, Range or X | None)")


def _params_of(call: typing.Callable) -> list[_Param]:
    try:
        hints = typing.get_type_hints(call)
    except Exception as exc:  # names in string annotations that cannot be resolved
        raise ValueError(f"cannot read the annotations of call(): {exc}") from None
    out: list[_Param] = []
    for p in inspect.signature(call).parameters.values():
        if p.kind is p.VAR_KEYWORD:
            continue
        if p.kind is p.KEYWORD_ONLY:
            if p.default is p.empty:
                raise ValueError(
                    f"call() has the keyword-only argument {p.name!r} without default: "
                    "formulas pass arguments by position"
                )
            continue
        kind, nullable = _kind_of(hints.get(p.name, inspect.Parameter.empty))
        out.append(_Param(p.name, kind, nullable, p.kind is p.VAR_POSITIONAL, p.default is not p.empty))
    for index, param in enumerate(out):
        if param.variadic and index != len(out) - 1:
            raise ValueError("call(): *args must come last")
    return out


def _convert(param: _Param, value: Value | Range):
    """One argument of the formula -> what ``call`` should get (``FormulaError`` when it cannot be)."""
    if param.kind == "any":
        return value
    if param.kind == "range":
        return value if isinstance(value, Range) else Range.of_value(value)
    if isinstance(value, Range):
        if len(value) != 1:
            raise FormulaError(VALUE, f"{param.name}: a range was given where one value is needed")
        value = value.at(0, 0)  # (a range of one cell is that cell)
        if isinstance(value, ErrorValue):
            raise value.raised()
    if value is None:
        if param.nullable:
            return None
        return {"float": 0.0, "int": 0, "bool": False, "str": ""}[param.kind]
    if param.kind in ("float", "int"):
        return _as_number(param, value)
    if param.kind == "bool":
        return _as_bool(param, value)
    return format_value(value)  # "str"


def _as_number(param: _Param, value: Value):
    if not isinstance(value, (int, float)):  # (TRUE and FALSE are the numbers 1 and 0 here, as in arithmetic)
        raise FormulaError(VALUE, f"{param.name} must be a number")
    if param.kind == "float":
        return float(value)
    try:
        return int(value)
    except (OverflowError, ValueError):
        raise FormulaError(NUM) from None


def _as_bool(param: _Param, value: Value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    raise FormulaError(VALUE, f"{param.name} must be TRUE or FALSE")


def _result(value: object) -> Value | Range:
    """What ``call`` returned -> a cell value (``FunctionError`` if it is not one)."""
    if isinstance(value, bool | str | Range):
        return value
    if isinstance(value, numbers.Integral):
        whole = int(value)
        return whole if fits_int(whole) else float(whole)
    if isinstance(value, numbers.Real):
        number = float(value)
        if not math.isfinite(number):
            raise FunctionError(NUM, "returned a number that is not finite")
        return number
    if isinstance(value, ErrorValue):
        raise value.raised()
    what = "None (is there a return?)" if value is None else type(value).__name__
    raise FunctionError(VALUE, f"returned {what}, which is not a number, text or range")


class Bound:
    """A ``UserFunction`` as the evaluator calls it: ``bound(arguments)`` with the formula's evaluated arguments."""

    def __init__(self, instance: UserFunction, name: str):
        self.instance = instance
        self.name = name
        self.params = _params_of(instance.call)
        self.min_args = sum(1 for p in self.params if not p.has_default and not p.variadic)
        self.max_args = None if any(p.variadic for p in self.params) else len(self.params)
        self.description = (instance.description or "").strip()
        self.examples = tuple(instance.examples)

    @property
    def signature(self) -> str:
        """``NAME(a, b?, *rest)``: optional arguments are marked with a question mark."""
        parts = [("*" if p.variadic else "") + p.name + ("?" if p.has_default else "") for p in self.params]
        return f"{self.name}({', '.join(parts)})"

    def get_tooltip(self) -> str:
        """One line for a tooltip: the signature and what the function does."""
        custom = getattr(self.instance, "get_tooltip", None)
        return custom() if callable(custom) else f"{self.signature}: {self.description}"

    def get_help(self) -> str:
        """The help topic as plain text: what it does and the worked examples."""
        custom = getattr(self.instance, "get_help", None)
        if callable(custom):
            return custom()
        lines = [self.get_tooltip(), ""]
        for example in self.examples:
            given = ", ".join(f"{address} = {format_value(value)}" for address, value in example.cells.items())
            lines.append(
                f"{example.formula}  gives  {format_value(example.result)}" + (f"  (with {given})" if given else "")
            )
            if example.note:
                lines.append(f"  {example.note}")
        return "\n".join(lines)

    def __call__(self, args: list):
        if len(args) < self.min_args or (self.max_args is not None and len(args) > self.max_args):
            raise FormulaError(VALUE, f"{self.name} takes {self._arity()} arguments, not {len(args)}")
        params = self.params
        last = len(params) - 1
        converted = [_convert(params[min(i, last)], arg) for i, arg in enumerate(args)]
        try:
            return _result(self.instance.call(*converted))
        except FormulaError:
            raise
        except ZeroDivisionError:
            raise FormulaError("#DIV/0!") from None
        except (ValueError, OverflowError):
            raise FormulaError(NUM) from None
        except TypeError:
            raise FormulaError(VALUE) from None
        except Exception:
            log.exception("function %s failed", self.name)
            raise FormulaError(SYNTAX, f"{self.name} failed: see the server's log") from None

    def _arity(self) -> str:
        if self.max_args is None:
            return f"at least {self.min_args}"
        return str(self.min_args) if self.min_args == self.max_args else f"{self.min_args} to {self.max_args}"
