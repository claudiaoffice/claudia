"""The pivot tables of a workbook (E6.30, D620): each a name, a definition and the words it was made with.

A pivot is *shown* by a ``PIVOT("name")`` formula in the cell where it starts, like a query result is shown by a
``SQL()`` formula, and what it fills is a name of its own (D607). What the pivot *is* — its source, its fields, how it
adds up — lives here, so that the field panel changes a definition and never a formula (D620). The formula and the name
are made, changed and removed together with the definition by the commands of :mod:`claudia_computes.pivot_commands`.

The pivots are part of the document; the grid each one last gave (:class:`~claudia_computes.PivotResult`, with the
role of every cell and the SQL it ran) is not: it is made again whenever the workbook is calculated.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

from .pivot import DEFAULT_LABELS, PivotDefinition, PivotError, PivotLabels
from .pivot_render import PivotResult


@dataclass(frozen=True, slots=True)
class PivotEntry:
    """One pivot: its ``name`` (a name of the workbook, D600), what it is ``definition``, and the ``labels`` it puts in
    its cells (the words of the person's language when it was made)."""

    name: str
    definition: PivotDefinition
    labels: PivotLabels = DEFAULT_LABELS

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {"name": self.name, "definition": self.definition.to_data(), "labels": self.labels.to_data()}

    @classmethod
    def from_data(cls, data: object) -> PivotEntry:
        """Inverse of :meth:`to_data`; :class:`PivotError` names what is wrong."""
        if not isinstance(data, dict) or not isinstance(data.get("name"), str) or "definition" not in data:
            raise PivotError("a pivot is an object with a name and a definition")
        return cls(
            data["name"], PivotDefinition.from_data(data["definition"]), PivotLabels.from_data(data.get("labels", {}))
        )


class Pivots:
    """The pivots of a workbook by name (without regard to case, like every name), and the grids they last gave."""

    def __init__(self) -> None:
        self._by_name: dict[str, PivotEntry] = {}
        self._results: dict[str, PivotResult] = {}

    def __len__(self) -> int:
        return len(self._by_name)

    def __iter__(self) -> Iterator[PivotEntry]:
        return iter(self._by_name.values())

    def get(self, name: str) -> PivotEntry | None:
        """The pivot called ``name``, or ``None``."""
        return self._by_name.get(name.casefold())

    def put(self, name: str, entry: PivotEntry | None) -> None:
        """File ``entry`` under ``name``, or with ``entry`` ``None`` take the pivot out."""
        key = name.casefold()
        if entry is None:
            self._by_name.pop(key, None)
            self._results.pop(key, None)
        else:
            self._by_name[key] = entry

    def result(self, name: str) -> PivotResult | None:
        """The grid the pivot gave the last time it was calculated; ``None`` for one that gave none (it failed, or it
        has no value field yet, or it was not calculated yet)."""
        return self._results.get(name.casefold())

    def record(self, name: str, result: PivotResult | None) -> None:
        """Note the grid a calculation of the pivot gave (``None``: it gave none)."""
        if result is None:
            self._results.pop(name.casefold(), None)
        else:
            self._results[name.casefold()] = result

    def sorted(self) -> list[PivotEntry]:
        """Every pivot, by name."""
        return sorted(self._by_name.values(), key=lambda entry: entry.name.casefold())

    def to_data(self) -> list[dict]:
        """Every pivot as plain data, in a fixed order."""
        return [entry.to_data() for entry in self.sorted()]

    @classmethod
    def from_data(cls, data: Sequence[dict] | Iterable[dict]) -> Pivots:
        """Inverse of :meth:`to_data`."""
        pivots = cls()
        for item in data:
            entry = PivotEntry.from_data(item)
            pivots.put(entry.name, entry)
        return pivots

    def clear(self) -> None:
        """Forget every pivot."""
        self._by_name.clear()
        self._results.clear()
