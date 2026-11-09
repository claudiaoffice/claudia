"""Commands of the creates model: the slides.

Everything about objects — shapes, images, text boxes: define, forget, add, remove, move, resize, rotate, retext,
snap — is shared with composes and computes and lives in :mod:`claudia_core.objects` (E10.16). What is left here
is what only a presentation has: slides.

Every command carries final values and returns its exact inverse, so undo, replay and checkpoints work on the
kernel without any creates-specific code in it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from claudia_core import AddObject, Command, Context

from .events import SlidesChanged
from .model import SlideModel

register = SlideModel.registry.register


@register
@dataclass(frozen=True)
class AddSlide(Command):
    """Add an empty slide, at the end or at a place."""

    kind: ClassVar[str] = "creates.AddSlide"
    id: str
    at: int | None = None

    @property
    def label(self) -> str:
        return "Add slide"

    @property
    def summary(self) -> str:
        return "Added a slide"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        ctx.model.insert_slide(self.id, self.at)
        ctx.emit(SlidesChanged())
        return RemoveSlide(self.id)

    def to_data(self) -> dict:
        return {"id": self.id, "at": self.at}

    @classmethod
    def from_data(cls, data, registry) -> AddSlide:
        return cls(data["id"], data.get("at"))

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, AddSlide) and other.id == self.id else self

    def redacted(self) -> Command:
        return self


@register
@dataclass(frozen=True)
class RemoveSlide(Command):
    """Remove an empty slide (its objects must be removed first)."""

    kind: ClassVar[str] = "creates.RemoveSlide"
    id: str

    @property
    def label(self) -> str:
        return "Remove slide"

    @property
    def summary(self) -> str:
        return "Removed a slide"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        place = ctx.model.delete_slide(self.id)
        ctx.emit(SlidesChanged())
        return AddSlide(self.id, place)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> RemoveSlide:
        return cls(data["id"])

    def shifted_by(self, other: Command) -> Command | None:
        """A colleague put something on the slide meanwhile: it is no longer mine to take away."""
        return None if isinstance(other, AddObject) and other.anchor.get("container") == self.id else self

    def redacted(self) -> Command:
        return self
