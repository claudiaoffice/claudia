"""The layouts of a presentation (E10.4, D1530): named arrangements of objects that a slide follows.

A layout is a definition, not a Thing (like a style): it has a name and an id, but no ``#`` reference and a namespace
of its own. What sits on it, placeholders and other objects, are ordinary objects whose holder is the layout (see
:class:`~claudia_core.ObjectModel.layout_holders`). This module keeps only the records: :class:`Layout` and
:class:`Layouts`, their order included, because the order is what a person sees and changes."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from .objects import _ID

#: Where a layout comes from, as for a style (D780): shipped with Claudia, taken from a template, or made in this
#: document. A built-in layout can only be hidden.
LAYOUT_ORIGINS = ("builtin", "template", "document")


@dataclass(frozen=True)
class Layout:
    """A layout as a record. ``purpose`` says what it is for (``""``: not said), ``hidden`` keeps it out of the list a
    slide's layout is chosen from, and ``to_name`` marks a provisional layout that nobody has named yet."""

    id: str
    name: str
    origin: str = "document"
    purpose: str = ""
    hidden: bool = False
    to_name: bool = False

    def to_data(self) -> dict:
        """The plain-data form; what is empty or false is not written."""
        data: dict = {"id": self.id, "name": self.name}
        if self.origin != "document":
            data["origin"] = self.origin
        if self.purpose:
            data["purpose"] = self.purpose
        if self.hidden:
            data["hidden"] = True
        if self.to_name:
            data["to_name"] = True
        return data

    @classmethod
    def from_data(cls, data: dict) -> Layout:
        """Inverse of :meth:`to_data`; ``ValueError`` if it is not a layout."""
        if not isinstance(data, dict):
            raise ValueError("a layout has an id and a name")
        layout = cls(
            data.get("id"),  # type: ignore[arg-type]  # checked below
            data.get("name"),  # type: ignore[arg-type]
            data.get("origin", "document"),
            data.get("purpose", ""),
            data.get("hidden", False),
            data.get("to_name", False),
        )
        texts = (layout.id, layout.name, layout.origin, layout.purpose)
        if not all(isinstance(text, str) for text in texts) or not layout.name:
            raise ValueError("a layout has an id and a name, and an origin and a purpose that are text")
        if layout.origin not in LAYOUT_ORIGINS:
            raise ValueError(f"a layout comes from {', '.join(LAYOUT_ORIGINS)}, not {layout.origin!r}")
        if not isinstance(layout.hidden, bool) or not isinstance(layout.to_name, bool):
            raise ValueError("a layout is hidden or not, and to be named or not")
        return layout


class Layouts:
    """The layouts of a document by id, in the order a person sees them."""

    def __init__(self) -> None:
        self._by_id: dict[str, Layout] = {}
        self._order: list[str] = []

    def __contains__(self, layout_id: object) -> bool:
        return layout_id in self._by_id

    def __getitem__(self, layout_id: str) -> Layout:
        try:
            return self._by_id[layout_id]
        except KeyError:
            raise ValueError(f"unknown layout {layout_id!r}") from None

    def __iter__(self) -> Iterator[Layout]:
        return (self._by_id[layout_id] for layout_id in self._order)

    def __len__(self) -> int:
        return len(self._order)

    def ids(self) -> list[str]:
        """The ids of the layouts, in order."""
        return list(self._order)

    def add(self, layout: Layout, at: int | None = None) -> None:
        """Keep a new layout at place ``at`` (the end by default); ``ValueError`` if its id is not an id or is taken."""
        if not _ID.fullmatch(layout.id):
            raise ValueError(f"layout id {layout.id!r}: lower-case letters, digits, '-' and '_', starting with a letter")
        if layout.id in self._by_id:
            raise ValueError(f"layout {layout.id!r} exists already")
        self._by_id[layout.id] = layout
        self._order.insert(len(self._order) if at is None else at, layout.id)

    def to_data(self) -> list[dict]:
        """The layouts as plain data, in order."""
        return [layout.to_data() for layout in self]

    @classmethod
    def from_data(cls, data: Iterable[dict]) -> Layouts:
        """Inverse of :meth:`to_data`; ``ValueError`` if it is not a list of layouts."""
        layouts = cls()
        for item in data:
            layouts.add(Layout.from_data(item))
        return layouts
