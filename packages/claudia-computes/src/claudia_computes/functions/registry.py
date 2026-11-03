"""The table of functions formulas can call, apart from the core's own."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from .base import Bound, UserFunction

_NAME = re.compile(r"[A-Z][A-Z0-9_.]*")


class RegistrationError(ValueError):
    """A function was refused. The message says what is wrong, for the person who wrote it."""


class FunctionRegistry:
    """Functions by name. ``reserved`` are names that belong to the core and cannot be taken."""

    def __init__(self, reserved: Iterable[str] = ()):
        self._reserved = frozenset(reserved)
        self._functions: dict[str, Bound] = {}
        self.version = 0  # changes whenever the table does, so that anything compiled against it can tell

    def register(self, cls: type[UserFunction]) -> Bound:
        """Add a function class. Refused (``RegistrationError``) with a reason when its name is taken or unusable, or
        when it has no description or no example: help is not optional."""
        name = (cls.name or cls.__name__).upper()
        if _NAME.fullmatch(name) is None:
            raise RegistrationError(
                f"{name!r} is not a function name: use letters, digits and underscores, starting with a letter"
            )
        if name in self._reserved:
            raise RegistrationError(f"{name} is a function of the core and cannot be replaced")
        if name in self._functions:
            raise RegistrationError(f"{name} is already defined")
        if not (cls.description or "").strip():
            raise RegistrationError(f"{name} has no description: say in one line what it does (description = ...)")
        if not cls.examples:
            raise RegistrationError(f'{name} has no example: give at least one (examples = (Example("=...", result),))')
        try:
            bound = Bound(cls(), name)
        except ValueError as problem:
            raise RegistrationError(f"{name}: {problem}") from None
        self._functions[name] = bound
        self.version += 1
        return bound

    def get(self, name: str) -> Bound | None:
        return self._functions.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._functions or name in self._reserved

    def __iter__(self) -> Iterator[Bound]:
        return iter(sorted(self._functions.values(), key=lambda bound: bound.name))

    def __len__(self) -> int:
        return len(self._functions)
