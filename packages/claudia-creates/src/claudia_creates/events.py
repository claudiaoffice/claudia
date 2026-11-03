"""State events the creates model raises through ``Context.emit`` (the kernel adds its own)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import SlideObject
    from .shapes import ShapeDefinition


@dataclass(frozen=True)
class ObjectsChanged:
    """Objects of one slide changed. ``changed`` are their new state (added or altered), ``removed`` their ids, and
    ``order`` is the stacking order of the whole slide afterwards (bottom first), so a view needs no query."""

    slide: str
    changed: tuple[SlideObject, ...]
    removed: tuple[str, ...]
    order: tuple[str, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "objects",
            "slide": self.slide,
            "changed": [obj.to_data() for obj in self.changed],
            "removed": list(self.removed),
            "order": list(self.order),
        }


@dataclass(frozen=True)
class ShapesChanged:
    """The document learned a shape (``definition`` is it) or forgot one (``definition`` is ``None``)."""

    shape_id: str
    definition: ShapeDefinition | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "shape",
            "id": self.shape_id,
            "definition": None if self.definition is None else self.definition.to_data(),
        }


@dataclass(frozen=True)
class SlidesChanged:
    """Slides were added, removed or reordered: a view asks for the list again."""

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "slides"}
