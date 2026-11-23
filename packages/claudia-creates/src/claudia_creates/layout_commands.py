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
    """Keep a new layout, at the end of the list or at a place, with nothing on it. ``to_name`` marks a provisional one
    that nobody has named yet; the rest is what removing a layout keeps, so that undoing it brings the layout back as
    it was."""

    kind: ClassVar[str] = "creates.DefineLayout"
    id: str
    name: str
    at: int | None = None
    to_name: bool = False
    purpose: str = ""
    origin: str = "document"
    hidden: bool = False

    @property
    def label(self) -> str:
        return "New layout"

    @property
    def summary(self) -> str:
        return f"made the layout {self.name}"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        layout = Layout(self.id, self.name, self.origin, self.purpose, self.hidden, self.to_name)
        ctx.model.define_layout(layout, self.at)
        ctx.emit(LayoutsChanged())
        return RemoveLayout(self.id)

    def to_data(self) -> dict:
        optional = {
            "to_name": (self.to_name, False),
            "purpose": (self.purpose, ""),
            "origin": (self.origin, "document"),
            "hidden": (self.hidden, False),
        }
        data: dict = {"id": self.id, "name": self.name, "at": self.at}
        data |= {key: value for key, (value, default) in optional.items() if value != default}
        return data

    @classmethod
    def from_data(cls, data, registry) -> DefineLayout:
        return cls(
            data["id"],
            data["name"],
            data.get("at"),
            data.get("to_name", False),
            data.get("purpose", ""),
            data.get("origin", "document"),
            data.get("hidden", False),
        )


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
        return DefineLayout(layout.id, layout.name, place, layout.to_name, layout.purpose, layout.origin, layout.hidden)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> RemoveLayout:
        return cls(data["id"])


@register
@dataclass(frozen=True)
class RenameLayout(Command):
    """Give a layout a name. ``to_name`` says whether it still waits for one: a person who names a provisional layout
    ends the waiting, and undoing it brings the waiting back."""

    kind: ClassVar[str] = "creates.RenameLayout"
    id: str
    name: str
    to_name: bool = False

    @property
    def label(self) -> str:
        return "Rename layout"

    @property
    def summary(self) -> str:
        return f"named a layout {self.name}"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old = ctx.model.change_layout(self.id, name=self.name, to_name=self.to_name)
        ctx.emit(LayoutsChanged())
        return RenameLayout(self.id, old.name, old.to_name)

    def to_data(self) -> dict:
        return {"id": self.id, "name": self.name, "to_name": self.to_name}

    @classmethod
    def from_data(cls, data, registry) -> RenameLayout:
        return cls(data["id"], data["name"], data.get("to_name", False))


@register
@dataclass(frozen=True)
class HideLayout(Command):
    """Keep a layout out of the list a slide's layout is chosen from, or put it back. A built-in layout can be hidden
    and never removed."""

    kind: ClassVar[str] = "creates.HideLayout"
    id: str
    hidden: bool

    @property
    def label(self) -> str:
        return "Hide layout" if self.hidden else "Show layout"

    @property
    def summary(self) -> str:
        return "hid a layout" if self.hidden else "showed a layout"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        old = ctx.model.change_layout(self.id, hidden=self.hidden)
        ctx.emit(LayoutsChanged())
        return HideLayout(self.id, old.hidden)

    def to_data(self) -> dict:
        return {"id": self.id, "hidden": self.hidden}

    @classmethod
    def from_data(cls, data, registry) -> HideLayout:
        return cls(data["id"], data["hidden"])


@register
@dataclass(frozen=True)
class MoveLayout(Command):
    """Put a layout at another place in the list; the first one that is not hidden is what a new deck starts on."""

    kind: ClassVar[str] = "creates.MoveLayout"
    id: str
    at: int

    @property
    def label(self) -> str:
        return "Move layout"

    @property
    def summary(self) -> str:
        return "moved a layout"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        place = ctx.model.move_layout(self.id, self.at)
        ctx.emit(LayoutsChanged())
        return MoveLayout(self.id, place)

    def to_data(self) -> dict:
        return {"id": self.id, "at": self.at}

    @classmethod
    def from_data(cls, data, registry) -> MoveLayout:
        return cls(data["id"], data["at"])


@register
@dataclass(frozen=True)
class SetSlideLayout(Command):
    """Let a slide follow another layout. ``rebind`` says, by final values, which placeholder each object of the slide
    is bound to afterwards (``""``: none): the command does not look for matches, so that undo, replay and a colleague's
    view all end the same way (see ``claudia_creates.layout_plans.set_layout_command``, which finds them by
    purpose). ``frames`` is what undoing it adds: the place, size, turn and look (x, y, w, h, rotation, style) that
    objects get back, because an object that takes a placeholder's place has lost its own."""

    kind: ClassVar[str] = "creates.SetSlideLayout"
    slide: str
    layout: str
    rebind: tuple[tuple[str, str], ...] = ()
    frames: tuple[tuple[str, tuple], ...] = ()

    @property
    def label(self) -> str:
        return "Slide layout"

    @property
    def summary(self) -> str:
        return "changed the layout of a slide"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        was = ctx.model.put_slide_on_layout(self.slide, self.layout, dict(self.rebind), dict(self.frames))
        ctx.emit(SlideLayoutChanged(self.slide, self.layout))
        if was.bindings:
            changed = tuple(ctx.model.objects[object_id] for object_id in was.bindings)
            ctx.emit(ctx.model.objects_changed(self.slide, changed=changed))
        return SetSlideLayout(self.slide, was.layout, tuple(was.bindings.items()), tuple(was.frames.items()))

    def to_data(self) -> dict:
        data: dict = {"slide": self.slide, "layout": self.layout}
        if self.rebind:
            data["rebind"] = dict(self.rebind)
        if self.frames:
            data["frames"] = {object_id: list(place) for object_id, place in self.frames}
        return data

    @classmethod
    def from_data(cls, data, registry) -> SetSlideLayout:
        frames = tuple((object_id, tuple(place)) for object_id, place in data.get("frames", {}).items())
        return cls(data["slide"], data["layout"], tuple(data.get("rebind", {}).items()), frames)
