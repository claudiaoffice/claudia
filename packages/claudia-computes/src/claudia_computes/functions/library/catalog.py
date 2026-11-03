"""The list of built-in functions. A library class joins it with ``@builtin``; nothing else is needed to ship one."""

from __future__ import annotations

from ..base import UserFunction

CLASSES: list[type[UserFunction]] = []


def builtin[F: type[UserFunction]](cls: F) -> F:
    """Mark a ``UserFunction`` class as one that comes with Claudia Computes."""
    CLASSES.append(cls)
    return cls
