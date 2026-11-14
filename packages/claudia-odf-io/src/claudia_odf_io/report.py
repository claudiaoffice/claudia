"""What could not be kept when a file was read or written: a list a person can read (D401, E12.6).

A loss is a *code* for what it is (``"table"``, ``"footnote"``, ``"style"``...), an optional detail that goes with
it (the name of a style) and how many there were. The code is for the interface to put into words in the person's
language; this layer never writes a sentence for a person."""

from __future__ import annotations

from collections.abc import Collection, Mapping
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


#: The code of a change no writer of the format can put into the file, when the facet has no code of its own.
NOT_WRITTEN = "not-written"


def unwritten_changes(
    before: Mapping[str, object],
    after: Mapping[str, object],
    *,
    written: Collection[str],
    kinds: Mapping[str, str] | None = None,
) -> tuple[Loss, ...]:
    """What differs between two states of a document in a part the writer of a format does not write (D450).

    ``before`` and ``after`` are the ``serialize()`` forms of two models, split into *facets* (a state's top-level
    keys, or parts of them an app picks out): the file an import came from and the document as it is now, or an empty
    document and a new one. A facet that is in ``written`` is the writer's business; every other facet that differs is
    a loss, ``count`` being how many of its entries differ. It is lost under the code ``kinds`` gives it, or else as
    ``"not-written"`` with the facet's name as detail. This is what keeps an export from saying nothing about what it
    left out: a new feature is reported until its writer is built."""
    codes = kinds or {}
    losses = LossLog()
    for facet in (*after, *(name for name in before if name not in after)):
        if facet in written or before.get(facet) == after.get(facet):
            continue
        count = _differences(before.get(facet), after.get(facet))
        if facet in codes:
            losses.add(codes[facet], count=count)
        else:
            losses.add(NOT_WRITTEN, facet, count)
    return losses.result()


def _differences(before: object, after: object) -> int:
    """How many entries of two values differ: keys of mappings, places of sequences (and a length that changed)."""
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        return sum(1 for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    if isinstance(before, list) and isinstance(after, list):
        return sum(1 for old, new in zip(before, after, strict=False) if old != new) + abs(len(before) - len(after))
    return 1
