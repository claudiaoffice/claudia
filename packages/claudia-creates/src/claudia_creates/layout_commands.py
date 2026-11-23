"""Commands about layouts (E10.4, D1530): define one, remove it again, put a slide on one.

Like every command they carry final values and return their exact inverse."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from claudia_core import Command, Context, Layout

from .events import LayoutsChanged, SlideLayoutChanged
from .model import SlideModel

register = SlideModel.registry.register


@register
@dataclass(frozen=True)
class DefineLayout(Command):
    """Keep a new layout, at the end of the list or at a place. It is a document layout with nothing on it."""

    kind: ClassVar[str] = "creates.DefineLayout"
    id: str
    name: str
    at: int | None = None

    @property
    def label(self) -> str:
        return "New layout"

    @property
    def summary(self) -> str:
        return f"made the layout {self.name}"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        ctx.model.define_layout(Layout(self.id, self.name), self.at)
        ctx.emit(LayoutsChanged())
        return RemoveLayout(self.id)

    def to_data(self) -> dict:
        return {"id": self.id, "name": self.name, "at": self.at}

    @classmethod
    def from_data(cls, data, registry) -> DefineLayout:
        return cls(data["id"], data["name"], data.get("at"))


@register
@dataclass(frozen=True)
class RemoveLayout(Command):
    """Take a layout away that no slide follows."""

    kind: ClassVar[str] = "creates.RemoveLayout"
    id: str

    @property
    def label(self) -> str:
        return "Remove layout"

    @property
    def summary(self) -> str:
        return "removed a layout"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        layout, place = ctx.model.remove_layout(self.id)
        ctx.emit(LayoutsChanged())
        return DefineLayout(layout.id, layout.name, place)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> RemoveLayout:
        return cls(data["id"])


@register
@dataclass(frozen=True)
class SetSlideLayout(Command):
    """Let a slide follow another layout."""

    kind: ClassVar[str] = "creates.SetSlideLayout"
    slide: str
    layout: str

    @property
    def label(self) -> str:
        return "Slide layout"

    @property
    def summary(self) -> str:
        return "changed the layout of a slide"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old = ctx.model.put_slide_on_layout(self.slide, self.layout)
        ctx.emit(SlideLayoutChanged(self.slide, self.layout))
        return SetSlideLayout(self.slide, old)

    def to_data(self) -> dict:
        return {"slide": self.slide, "layout": self.layout}

    @classmethod
    def from_data(cls, data, registry) -> SetSlideLayout:
        return cls(data["slide"], data["layout"])
