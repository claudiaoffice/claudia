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
    """Let a slide follow another layout. ``rebind`` says, by final values, which placeholder each object of the slide
    is bound to afterwards (``""``: none): the command does not look for matches, so that undo, replay and a colleague's
    view all end the same way (see :meth:`SlideModel.set_layout_command`, which finds them by purpose)."""

    kind: ClassVar[str] = "creates.SetSlideLayout"
    slide: str
    layout: str
    rebind: tuple[tuple[str, str], ...] = ()

    @property
    def label(self) -> str:
        return "Slide layout"

    @property
    def summary(self) -> str:
        return "changed the layout of a slide"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old, before = ctx.model.put_slide_on_layout(self.slide, self.layout, dict(self.rebind))
        ctx.emit(SlideLayoutChanged(self.slide, self.layout))
        if before:
            changed = tuple(ctx.model.objects[object_id] for object_id in before)
            ctx.emit(ctx.model.objects_changed(self.slide, changed=changed))
        return SetSlideLayout(self.slide, old, tuple(before.items()))

    def to_data(self) -> dict:
        data: dict = {"slide": self.slide, "layout": self.layout}
        if self.rebind:
            data["rebind"] = dict(self.rebind)
        return data

    @classmethod
    def from_data(cls, data, registry) -> SetSlideLayout:
        return cls(data["slide"], data["layout"], tuple(data.get("rebind", {}).items()))
