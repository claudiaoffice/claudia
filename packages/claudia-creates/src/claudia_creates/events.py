"""State events the creates model raises through ``Context.emit`` (the kernel adds its own)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claudia_core import ImageAsset

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
        """The plain-data form of the event. Carries every ``changed`` object's import record unmasked; a client
        that goes straight to this (rather than through ``to_data_for``) is trusted with the full record, as the
        log is."""
        return {
            "type": "objects",
            "slide": self.slide,
            "changed": [obj.to_data() for obj in self.changed],
            "removed": list(self.removed),
            "order": list(self.order),
        }

    def to_data_for(self, viewer: str) -> dict:
        """What ``viewer`` is sent: as :meth:`to_data`, with each changed image's import record masked for anyone
        but the person who imported it (``hub.py`` calls this per connection when an event offers it)."""
        return {**self.to_data(), "changed": [obj.to_data_for(viewer) for obj in self.changed]}


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
class ImagesChanged:
    """The document learned an image (``asset`` is it) or forgot one (``asset`` is ``None``)."""

    image_id: str
    asset: ImageAsset | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "image",
            "id": self.image_id,
            "asset": None if self.asset is None else self.asset.to_data(),
        }


@dataclass(frozen=True)
class SlidesChanged:
    """Slides were added, removed or reordered: a view asks for the list again."""

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "slides"}
