"""claudia-creates: a stub. Slides holding objects, and the object-set Region of D17.

The real model reuses the demo's object layer (drawing.py: anchors, z-order, groups) and arrives with E10.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Self

from claudia_core import Command, CommandRegistry, Context, DocumentModel, Region, new_registry


class SlideModel(DocumentModel):
    app: ClassVar[str] = "creates"
    state_schema: ClassVar[int] = 1
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(self):
        self.slides: list[str] = []
        self.objects: dict[str, dict] = {}  # id -> {"slide": ..., "x": ..., "text": ...}

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {"slides": list(self.slides), "objects": {k: dict(v) for k, v in sorted(self.objects.items())}}

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls()
        model.slides = list(state["slides"])
        model.objects = {k: dict(v) for k, v in state["objects"].items()}
        return model

    def region_from_data(self, data: dict) -> Region:
        return ObjectSet(data["slide"], frozenset(data["ids"]))


@dataclass(frozen=True)
class ObjectSet:
    """Some objects on one slide (a selection, an area the AI is working on)."""

    kind: ClassVar[str] = "objects"
    slide: str
    ids: frozenset[str] = field(default_factory=frozenset)

    def overlaps(self, other: Region) -> bool:
        return isinstance(other, ObjectSet) and self.slide == other.slide and bool(self.ids & other.ids)

    def transformed(self, command: Command) -> ObjectSet | None:
        if isinstance(command, RemoveObject) and command.id in self.ids:
            rest = self.ids - {command.id}
            return ObjectSet(self.slide, rest) if rest else None
        return self

    def to_data(self) -> dict:
        return {"kind": self.kind, "slide": self.slide, "ids": sorted(self.ids)}


@SlideModel.registry.register
@dataclass(frozen=True)
class AddSlide(Command):
    kind: ClassVar[str] = "creates.AddSlide"
    id: str

    def apply(self, ctx: Context[SlideModel]) -> Command:
        if self.id in ctx.model.slides:
            raise ValueError(f"slide {self.id!r} exists")
        ctx.model.slides.append(self.id)
        return RemoveSlide(self.id)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> AddSlide:
        return cls(data["id"])

    def redacted(self) -> Command:
        return self


@SlideModel.registry.register
@dataclass(frozen=True)
class RemoveSlide(Command):
    """Removes an empty slide (objects must be removed first)."""

    kind: ClassVar[str] = "creates.RemoveSlide"
    id: str

    def apply(self, ctx: Context[SlideModel]) -> Command:
        if any(o["slide"] == self.id for o in ctx.model.objects.values()):
            raise ValueError(f"slide {self.id!r} still has objects")
        ctx.model.slides.remove(self.id)
        return AddSlide(self.id)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> RemoveSlide:
        return cls(data["id"])

    def redacted(self) -> Command:
        return self


@SlideModel.registry.register
@dataclass(frozen=True)
class PutObject(Command):
    """Create an object or replace its properties (position, text...)."""

    kind: ClassVar[str] = "creates.PutObject"
    id: str
    props: dict

    @property
    def label(self) -> str:
        return "Change object"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        model = ctx.model
        if self.props["slide"] not in model.slides:
            raise ValueError(f"unknown slide {self.props['slide']!r}")
        old = model.objects.get(self.id)
        model.objects[self.id] = dict(self.props)
        return RemoveObject(self.id) if old is None else PutObject(self.id, old)

    def to_data(self) -> dict:
        return {"id": self.id, "props": self.props}

    @classmethod
    def from_data(cls, data, registry) -> PutObject:
        return cls(data["id"], data["props"])

    def regions(self, model) -> tuple[Region, ...]:
        return (ObjectSet(self.props["slide"], frozenset({self.id})),)

    def shifted_by(self, other: Command) -> Command | None:
        """Objects are named by id, so nothing shifts; but never overwrite what a colleague changed since."""
        if isinstance(other, PutObject) and other.id == self.id:
            return None
        return self

    def redacted(self) -> Command:
        return PutObject(self.id, {**self.props, "text": ""})  # the object stays, its words go


@SlideModel.registry.register
@dataclass(frozen=True)
class RemoveObject(Command):
    kind: ClassVar[str] = "creates.RemoveObject"
    id: str

    @property
    def label(self) -> str:
        return "Remove object"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old = ctx.model.objects.pop(self.id, None)
        if old is None:
            raise ValueError(f"no object {self.id!r}")
        return PutObject(self.id, old)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> RemoveObject:
        return cls(data["id"])

    def redacted(self) -> Command:
        return self
