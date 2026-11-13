"""Commands of the creates model: the slides.

Everything about objects — shapes, images, text boxes: define, forget, add, remove, move, resize, rotate, retext,
snap — is shared with composes and computes and lives in :mod:`claudia_core.objects` (E10.16). What is left here
is what only a presentation has: slides, their speaker notes (D342) and planned times (D343), and how it is
printed (D917). Its language is the kernel's
(:class:`~claudia_core.SetLanguage`), the same command composes uses.

Every command carries final values and returns its exact inverse, so undo, replay and checkpoints work on the
kernel without any creates-specific code in it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from claudia_core import AddObject, Command, Context

from .events import PrintSetupChanged, SlideNotesChanged, SlidesChanged, SlideTimeChanged
from .model import SlideModel
from .printing import PrintSetup

register = SlideModel.registry.register


@register
@dataclass(frozen=True)
class AddSlide(Command):
    """Add an empty slide, at the end or at a place. It carries notes and a planned time only when it is the
    inverse of removing a slide that had them."""

    kind: ClassVar[str] = "creates.AddSlide"
    id: str
    at: int | None = None
    notes: str = ""
    seconds: int | None = None

    @property
    def label(self) -> str:
        return "Add slide"

    @property
    def summary(self) -> str:
        return "Added a slide"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        ctx.model.insert_slide(self.id, self.at, self.notes, self.seconds)
        ctx.emit(SlidesChanged())
        return RemoveSlide(self.id)

    def to_data(self) -> dict:
        data: dict = {"id": self.id, "at": self.at}
        if self.notes:
            data["notes"] = self.notes
        if self.seconds is not None:
            data["seconds"] = self.seconds
        return data

    @classmethod
    def from_data(cls, data, registry) -> AddSlide:
        return cls(data["id"], data.get("at"), data.get("notes", ""), data.get("seconds"))

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, AddSlide) and other.id == self.id else self

    def redacted(self) -> Command:
        """Notes are content (E1.8); the slide itself is what later commands refer to."""
        return AddSlide(self.id, self.at)


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
        notes = ctx.model.notes.get(self.id, "")
        seconds = ctx.model.times.get(self.id)
        place = ctx.model.delete_slide(self.id)
        ctx.emit(SlidesChanged())
        return AddSlide(self.id, place, notes, seconds)

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


@register
@dataclass(frozen=True)
class SetPrintSetup(Command):
    """Say how the presentation is printed (D917): the layout and the page. One step for everybody."""

    kind: ClassVar[str] = "creates.SetPrintSetup"
    setup: PrintSetup

    @property
    def label(self) -> str:
        return "Print setup"

    @property
    def summary(self) -> str:
        return f"set printing to {self.setup.describe()}"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old = ctx.model.print_setup
        ctx.model.print_setup = self.setup
        ctx.emit(PrintSetupChanged(self.setup.to_data()))
        return SetPrintSetup(old)

    def to_data(self) -> dict:
        return {"setup": self.setup.to_data()}

    @classmethod
    def from_data(cls, data, registry) -> SetPrintSetup:
        return cls(PrintSetup.from_data(data["setup"]))


@register
@dataclass(frozen=True)
class SetSlideNotes(Command):
    """Set the speaker notes of a slide (D342): Markdown, shown formatted in the presenter view and nowhere else.
    ``""`` clears them."""

    kind: ClassVar[str] = "creates.SetSlideNotes"
    slide: str
    notes: str

    @property
    def label(self) -> str:
        return "Speaker notes"

    @property
    def summary(self) -> str:
        return "cleared the speaker notes of a slide" if not self.notes else "edited the speaker notes of a slide"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old = ctx.model.set_notes(self.slide, self.notes)
        ctx.emit(SlideNotesChanged(self.slide, ctx.model.notes_of(self.slide)))
        return SetSlideNotes(self.slide, old)

    def to_data(self) -> dict:
        return {"slide": self.slide, "notes": self.notes}

    @classmethod
    def from_data(cls, data, registry) -> SetSlideNotes:
        return cls(data["slide"], data["notes"])

    def shifted_by(self, other: Command) -> Command | None:
        """Notes are one piece of text: undoing mine must not overwrite what a colleague wrote since, nor notes of a
        slide that is gone."""
        if isinstance(other, SetSlideNotes | RemoveSlide) and _slide_of(other) == self.slide:
            return None
        return self

    def redacted(self) -> Command:
        return SetSlideNotes(self.slide, "")

    def stub(self) -> dict:
        return {"slide": self.slide}


@register
@dataclass(frozen=True)
class SetSlideTime(Command):
    """Set the planned time of a slide (D343) in whole seconds; ``None`` clears it."""

    kind: ClassVar[str] = "creates.SetSlideTime"
    slide: str
    seconds: int | None

    @property
    def label(self) -> str:
        return "Planned time"

    @property
    def summary(self) -> str:
        if self.seconds is None:
            return "removed the planned time of a slide"
        return f"planned {self.seconds // 60}:{self.seconds % 60:02d} for a slide"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old = ctx.model.set_time(self.slide, self.seconds)
        ctx.emit(SlideTimeChanged(self.slide, self.seconds))
        return SetSlideTime(self.slide, old)

    def to_data(self) -> dict:
        return {"slide": self.slide, "seconds": self.seconds}

    @classmethod
    def from_data(cls, data, registry) -> SetSlideTime:
        return cls(data["slide"], data.get("seconds"))

    def shifted_by(self, other: Command) -> Command | None:
        if isinstance(other, SetSlideTime | RemoveSlide) and _slide_of(other) == self.slide:
            return None
        return self

    def redacted(self) -> Command:
        return self


def _slide_of(command: SetSlideNotes | SetSlideTime | RemoveSlide) -> str:
    """The slide a notes, time or removal command is about."""
    return command.id if isinstance(command, RemoveSlide) else command.slide
