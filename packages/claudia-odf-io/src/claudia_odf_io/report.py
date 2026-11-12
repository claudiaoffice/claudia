"""What could not be kept when a file was read or written: a list a person can read (D401, E12.6).

A loss is a *code* for what it is (``"table"``, ``"footnote"``, ``"style"``...), an optional detail that goes with
it (the name of a style) and how many there were. The code is for the interface to put into words in the person's
language; this layer never writes a sentence for a person."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Loss:
    """``count`` times ``kind`` (a code), with ``detail`` where there is something to name."""

    kind: str
    detail: str = ""
    count: int = 1


class LossLog:
    """Collects losses; the same kind with the same detail is one line with a count, in the order first lost."""

    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], int] = {}

    def add(self, kind: str, detail: str = "", count: int = 1) -> None:
        """Note ``count`` more losses of ``kind`` (with ``detail``)."""
        key = (kind, detail)
        self._counts[key] = self._counts.get(key, 0) + count

    def result(self) -> tuple[Loss, ...]:
        """The losses noted so far, one per kind and detail."""
        return tuple(Loss(kind, detail, count) for (kind, detail), count in self._counts.items())
