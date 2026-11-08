"""Commands of the creates model: slides, shapes and objects.

Every command carries final values and returns its exact inverse, so undo, replay and checkpoints work on the kernel
without any creates-specific code in it. The commands are fine-grained on purpose: one person moving an object and
another editing its text do not get in each other's way, while two people changing the same thing do (D46):
``shifted_by`` refuses an undo that would overwrite or destroy what a colleague did in the meantime.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import ClassVar

from claudia_core import Command, Context, ImageAsset

from .events import ImagesChanged, ShapesChanged, SlidesChanged
from .model import SlideModel, SlideObject
from .region import ObjectSet
from .shapes import ShapeDefinition

register = SlideModel.registry.register

MAX_LISTED_TEXT = 40  # characters of an object's text that a history sentence quotes


def _quote(text: str) -> str:
    """A short, one-line piece of an object's text for a sentence in the history."""
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= MAX_LISTED_TEXT else flat[: MAX_LISTED_TEXT - 1] + "…"


def _selection(model: SlideModel, object_id: str) -> tuple[ObjectSet, ...]:
    obj = model.objects.get(object_id)
    return () if obj is None else (ObjectSet(obj.slide, frozenset({object_id})),)


# ------------------------------------------------------------------------------ slides
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
        return None if isinstance(other, AddObject) and other.obj.slide == self.id else self

    def redacted(self) -> Command:
        return self


# ------------------------------------------------------------------------------ shapes
@register
@dataclass(frozen=True)
class DefineShape(Command):
    """Take a shape's outline from a library into the document, so that the document opens the same anywhere."""

    kind: ClassVar[str] = "creates.DefineShape"
    shape: ShapeDefinition

    @property
    def label(self) -> str:
        return "Define shape"

    @property
    def summary(self) -> str:
        return f"The document takes the shape {self.shape.name}"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        ctx.model.define_shape(self.shape)
        ctx.emit(ShapesChanged(self.shape.id, self.shape))
        return ForgetShape(self.shape.id)

    def to_data(self) -> dict:
        return {"shape": self.shape.to_data()}

    @classmethod
    def from_data(cls, data, registry) -> DefineShape:
        return cls(ShapeDefinition.from_data(data["shape"]))

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, DefineShape) and other.shape.id == self.shape.id else self

    def redacted(self) -> Command:
        return self


@register
@dataclass(frozen=True)
class ForgetShape(Command):
    """Let go of a shape that no object uses (the undo of :class:`DefineShape`)."""

    kind: ClassVar[str] = "creates.ForgetShape"
    id: str

    @property
    def label(self) -> str:
        return "Forget shape"

    @property
    def summary(self) -> str:
        return f"The document lets go of the shape {self.id}"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        shape = ctx.model.forget_shape(self.id)
        ctx.emit(ShapesChanged(self.id, None))
        return DefineShape(shape)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> ForgetShape:
        return cls(data["id"])

    def shifted_by(self, other: Command) -> Command | None:
        """Refuse when a colleague now uses the shape, or defined it anew."""
        if isinstance(other, AddObject) and other.obj.shape == self.id:
            return None
        return None if isinstance(other, DefineShape) and other.shape.id == self.id else self

    def redacted(self) -> Command:
        return self


# ------------------------------------------------------------------------------ images
@register
@dataclass(frozen=True)
class DefineImage(Command):
    """Take a decoded image into the document, so that it opens the same anywhere (mirrors :class:`DefineShape`)."""

    kind: ClassVar[str] = "creates.DefineImage"
    image: ImageAsset

    @property
    def label(self) -> str:
        return "Define image"

    @property
    def summary(self) -> str:
        return f"The document takes an image ({self.image.width} × {self.image.height})"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        ctx.model.define_image(self.image)
        ctx.emit(ImagesChanged(self.image.id, self.image))
        return ForgetImage(self.image.id)

    def to_data(self) -> dict:
        return {"image": self.image.to_data()}

    @classmethod
    def from_data(cls, data, registry) -> DefineImage:
        return cls(ImageAsset.from_data(data["image"]))

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, DefineImage) and other.image.id == self.image.id else self

    def redacted(self) -> Command:
        return self


@register
@dataclass(frozen=True)
class ForgetImage(Command):
    """Let go of an image that no object uses (the undo of :class:`DefineImage`)."""

    kind: ClassVar[str] = "creates.ForgetImage"
    id: str

    @property
    def label(self) -> str:
        return "Forget image"

    @property
    def summary(self) -> str:
        return f"The document lets go of the image {self.id}"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        image = ctx.model.forget_image(self.id)
        ctx.emit(ImagesChanged(self.id, None))
        return DefineImage(image)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> ForgetImage:
        return cls(data["id"])

    def shifted_by(self, other: Command) -> Command | None:
        """Refuse when a colleague now uses the image, or defined it anew."""
        if isinstance(other, AddObject) and other.obj.image == self.id:
            return None
        return None if isinstance(other, DefineImage) and other.image.id == self.id else self

    def redacted(self) -> Command:
        return self


# ------------------------------------------------------------------------------ objects
@register
@dataclass(frozen=True)
class AddObject(Command):
    """Put a text box, a shape or an image on a slide: on top of the others, or at stacking place ``at``."""

    kind: ClassVar[str] = "creates.AddObject"
    schema: ClassVar[int] = 3
    obj: SlideObject
    at: int | None = None

    @property
    def label(self) -> str:
        return {"text": "Add text box", "shape": "Add shape", "image": "Add image"}[self.obj.kind]

    @property
    def summary(self) -> str:
        if self.obj.kind == "text":
            return f"Added a text box: {_quote(self.obj.text)}" if self.obj.text.strip() else "Added a text box"
        if self.obj.kind == "image":
            alt = self.obj.imported.alt if self.obj.imported else ""
            return f"Added an image: {_quote(alt)}" if alt.strip() else "Added an image"
        return f"Added a {self.obj.shape}"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        ctx.model.insert_object(self.obj, self.at)
        ctx.emit(ctx.model.changed(self.obj.slide, changed=(self.obj,)))
        return RemoveObject(self.obj.id)

    def to_data(self) -> dict:
        return {"object": self.obj.to_data(), "at": self.at}

    @classmethod
    def from_data(cls, data, registry) -> AddObject:
        return cls(SlideObject.from_data(data["object"]), data.get("at"))

    def regions(self, model: SlideModel) -> tuple[ObjectSet, ...]:  # type: ignore[override]
        return (ObjectSet(self.obj.slide, frozenset({self.obj.id})),)

    def shifted_by(self, other: Command) -> Command | None:
        """Bringing an object back is refused when somebody made another one with its id, or took its shape or
        image away."""
        if isinstance(other, AddObject) and other.obj.id == self.obj.id:
            return None
        if isinstance(other, ForgetShape) and other.id == self.obj.shape:
            return None
        return None if isinstance(other, ForgetImage) and other.id == self.obj.image else self

    def redacted(self) -> Command:
        return AddObject(replace(self.obj, text=""), self.at)  # the object stays, its words go


@register
@dataclass(frozen=True)
class RemoveObject(Command):
    """Take an object off its slide."""

    kind: ClassVar[str] = "creates.RemoveObject"
    id: str

    @property
    def label(self) -> str:
        return "Remove object"

    @property
    def summary(self) -> str:
        return "Removed an object"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        obj, place = ctx.model.delete_object(self.id)
        ctx.emit(ctx.model.changed(obj.slide, removed=(obj.id,)))
        return AddObject(obj, place)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> RemoveObject:
        return cls(data["id"])

    def regions(self, model: SlideModel) -> tuple[ObjectSet, ...]:  # type: ignore[override]
        return _selection(model, self.id)

    def shifted_by(self, other: Command) -> Command | None:
        """Never destroy what a colleague has done to the object since (this is the undo of adding it)."""
        return None if _touches(other, self.id) else self

    def redacted(self) -> Command:
        return self


@register
@dataclass(frozen=True)
class MoveObject(Command):
    """Put an object at a new place; its size stays."""

    kind: ClassVar[str] = "creates.MoveObject"
    id: str
    x: int
    y: int

    @property
    def label(self) -> str:
        return "Move object"

    @property
    def summary(self) -> str:
        return f"Moved an object to {self.x}, {self.y}"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old = ctx.model.get(self.id)
        new = replace(old, x=self.x, y=self.y)
        ctx.model.replace_object(new)
        ctx.emit(ctx.model.changed(new.slide, changed=(new,)))
        return MoveObject(self.id, old.x, old.y)

    def to_data(self) -> dict:
        return {"id": self.id, "x": self.x, "y": self.y}

    @classmethod
    def from_data(cls, data, registry) -> MoveObject:
        return cls(data["id"], data["x"], data["y"])

    def regions(self, model: SlideModel) -> tuple[ObjectSet, ...]:  # type: ignore[override]
        return _selection(model, self.id)

    def shifted_by(self, other: Command) -> Command | None:
        return None if _changes_frame(other, self.id) else self

    def redacted(self) -> Command:
        return self


@register
@dataclass(frozen=True)
class ResizeObject(Command):
    """Give an object a new frame: place and size together, since dragging a corner moves the corner."""

    kind: ClassVar[str] = "creates.ResizeObject"
    id: str
    x: int
    y: int
    w: int
    h: int

    @property
    def label(self) -> str:
        return "Resize object"

    @property
    def summary(self) -> str:
        return f"Resized an object to {self.w} × {self.h}"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old = ctx.model.get(self.id)
        new = replace(old, x=self.x, y=self.y, w=self.w, h=self.h)
        ctx.model.replace_object(new)
        ctx.emit(ctx.model.changed(new.slide, changed=(new,)))
        return ResizeObject(self.id, old.x, old.y, old.w, old.h)

    def to_data(self) -> dict:
        return {"id": self.id, "x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_data(cls, data, registry) -> ResizeObject:
        return cls(data["id"], data["x"], data["y"], data["w"], data["h"])

    def regions(self, model: SlideModel) -> tuple[ObjectSet, ...]:  # type: ignore[override]
        return _selection(model, self.id)

    def shifted_by(self, other: Command) -> Command | None:
        return None if _changes_frame(other, self.id) else self

    def redacted(self) -> Command:
        return self


@register
@dataclass(frozen=True)
class SetText(Command):
    """Replace the whole text of an object."""

    kind: ClassVar[str] = "creates.SetText"
    id: str
    text: str

    @property
    def label(self) -> str:
        return "Edit text"

    @property
    def summary(self) -> str:
        return f"Changed the text to: {_quote(self.text)}" if self.text.strip() else "Cleared the text of an object"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old = ctx.model.get(self.id)
        new = replace(old, text=self.text)
        ctx.model.replace_object(new)
        ctx.emit(ctx.model.changed(new.slide, changed=(new,)))
        return SetText(self.id, old.text)

    def to_data(self) -> dict:
        return {"id": self.id, "text": self.text}

    @classmethod
    def from_data(cls, data, registry) -> SetText:
        return cls(data["id"], data["text"])

    def regions(self, model: SlideModel) -> tuple[ObjectSet, ...]:  # type: ignore[override]
        return _selection(model, self.id)

    def shifted_by(self, other: Command) -> Command | None:
        """Moving or resizing the box does not matter to its words; another text or a removal does."""
        return None if isinstance(other, SetText | RemoveObject | AddObject) and _target(other) == self.id else self

    def redacted(self) -> Command:
        return SetText(self.id, "")


@register
@dataclass(frozen=True)
class SetSnap(Command):
    """Hold or release an object's snap to the grid (E10.15). The grid itself is only a helper the view draws,
    never part of the slide, but whether an object follows it is a real, persisted choice with its own history
    entry — so it keeps holding (or not) even if the grid is hidden, and survives for everyone who opens the
    document."""

    kind: ClassVar[str] = "creates.SetSnap"
    id: str
    snap: bool

    @property
    def label(self) -> str:
        return "Snap to grid" if self.snap else "Release from grid"

    @property
    def summary(self) -> str:
        return "Snapped an object to the grid" if self.snap else "Released an object from the grid"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old = ctx.model.get(self.id)
        new = replace(old, snap=self.snap)
        ctx.model.replace_object(new)
        ctx.emit(ctx.model.changed(new.slide, changed=(new,)))
        return SetSnap(self.id, old.snap)

    def to_data(self) -> dict:
        return {"id": self.id, "snap": self.snap}

    @classmethod
    def from_data(cls, data, registry) -> SetSnap:
        return cls(data["id"], data["snap"])

    def regions(self, model: SlideModel) -> tuple[ObjectSet, ...]:  # type: ignore[override]
        return _selection(model, self.id)

    def shifted_by(self, other: Command) -> Command | None:
        """Moving, resizing or editing the box does not matter to its snap; another snap change or a
        removal/re-creation does."""
        return None if isinstance(other, SetSnap | RemoveObject | AddObject) and _target(other) == self.id else self

    def redacted(self) -> Command:
        return self


# ------------------------------------------------------------------------------ who touched what
def _target(command: Command) -> str | None:
    """The id of the object a command is about, if it is about one."""
    if isinstance(command, AddObject):
        return command.obj.id
    if isinstance(command, MoveObject | ResizeObject | SetText | SetSnap | RemoveObject):
        return command.id
    return None


def _touches(other: Command, object_id: str) -> bool:
    return _target(other) == object_id


def _changes_frame(other: Command, object_id: str) -> bool:
    """Did ``other`` place, size, remove or re-create the object? (Its text is another matter.)"""
    return isinstance(other, MoveObject | ResizeObject | RemoveObject | AddObject) and _target(other) == object_id


# ------------------------------------------------------------------------------ documents are forever
@SlideModel.registry.upcaster("creates.AddObject", 1)
def _object_gets_image_fields(data: dict) -> dict:
    """Schema 1 had no images (E10.8): every stored object gets the new fields, unset."""
    return {**data, "object": {**data["object"], "image": None, "imported": None}}


@SlideModel.registry.upcaster("creates.AddObject", 2)
def _object_gets_snap_field(data: dict) -> dict:
    """Schema 2 had no grid (E10.15): every object already on a slide snapped to it, since there was no way to
    tell it not to — so it gets the new field set to ``True``, not unset, to keep behaving the way it always
    looked like it did."""
    return {**data, "object": {**data["object"], "snap": True}}
