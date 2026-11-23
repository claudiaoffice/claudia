"""The slide, shared by creates and computes (E6.31, D1470): a page of objects in a fixed 16:9 frame.

What both apps use is here: the frame (``SLIDE_WIDTH`` by ``SLIDE_HEIGHT`` whole units), the anchor of an object on a
slide, the rule that keeps an object on its slide, and the slides of a document as records (:class:`Slide`) kept by id
(:class:`Slides`). What is an app's own stays there: the order of its slides (creates: the presentation; computes: its
tabs, D1471), its commands, and what only it has (creates: speaker notes and planned times). A slide is a holder of
the object layer like any other; :meth:`~claudia_core.ObjectModel.close_holder` refuses to take one away that still has
objects, as it does for every holder.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar

from .errors import Refusal
from .objects import _ID, ObjectBody, VisualObject, _is_whole
from .turning import nudge_into, turned_extent

#: The frame of a slide, in whole units: an anchor and an object body are measured in it; a view scales it and a file
#: maps it to centimetres or EMU.
SLIDE_WIDTH = 1600
SLIDE_HEIGHT = 900


@dataclass(frozen=True)
class SlideAnchor:
    """Where an object sits on a slide: the top-left corner of its frame, in whole units of the slide.

    A slide has absolute coordinates and a fixed size, so an anchor is a point, and nothing on the slide ever moves it
    by itself."""

    kind: ClassVar[str] = "slide"
    slide: str
    x: int
    y: int

    @property
    def holder(self) -> str:
        """The slide this object belongs to."""
        return self.slide

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {"kind": self.kind, "holder": self.slide, "x": self.x, "y": self.y}

    @classmethod
    def from_data(cls, data: dict) -> SlideAnchor:
        """Read an anchor sent by a client or stored in the log; ``ValueError`` if it is not a slide anchor."""
        if data.get("kind") != cls.kind:
            raise ValueError(f"not a slide anchor: the kind is {data.get('kind')!r}")
        slide, x, y = data.get("holder"), data.get("x"), data.get("y")
        if not isinstance(slide, str) or not _is_whole(x) or not _is_whole(y):
            raise ValueError("a slide anchor names a slide and whole x and y")
        return cls(slide, x, y)


def check_on_slide(anchor: SlideAnchor, body: ObjectBody) -> None:
    """An object must stay on its slide, in whole units. What has to be on the slide is the object's outline: its frame
    when it is upright, and what a turn makes of it otherwise, so the anchor of a turned object may lie outside."""
    if not _is_whole(anchor.x) or not _is_whole(anchor.y):
        raise ValueError("x and y must be whole numbers")
    if (anchor.x, anchor.y) != nudge_into(anchor.x, anchor.y, body.w, body.h, body.rotation, SLIDE_WIDTH, SLIDE_HEIGHT):
        raise Refusal(
            "the object must stay on the slide ({slide_width} by {slide_height} units)",
            slide_width=SLIDE_WIDTH,
            slide_height=SLIDE_HEIGHT,
        )


def turned_on_slide(obj: VisualObject[SlideAnchor], rotation: int) -> SlideAnchor:
    """The nearest place for ``obj`` at which, turned to ``rotation``, its outline is on the slide; ``ValueError`` if
    it is too large to be on the slide turned that way."""
    body = obj.body
    place = nudge_into(obj.anchor.x, obj.anchor.y, body.w, body.h, rotation, SLIDE_WIDTH, SLIDE_HEIGHT)
    if place is None:
        out_w, out_h = turned_extent(body.w, body.h, rotation)
        raise Refusal(
            "this object is too large to turn that way: it would be {width} by {height} units on a slide of "
            "{slide_width} by {slide_height}",
            width=out_w,
            height=out_h,
            slide_width=SLIDE_WIDTH,
            slide_height=SLIDE_HEIGHT,
        )
    return SlideAnchor(obj.anchor.slide, *place)


def room_on_slide(anchor: SlideAnchor | None) -> int:
    """What is left of the slide to the right of where a new object starts (D1332): an object stays on its slide."""
    return SLIDE_WIDTH - (anchor.x if anchor is not None else 0)


@dataclass(frozen=True)
class Slide:
    """A slide as a record: its id, its name (one namespace with every other thing of the document, D550) and what is
    written about it (D1317). ``""``: none."""

    id: str
    name: str = ""
    description: str = ""

    def to_data(self) -> dict:
        """The plain-data form; a name or a description that is empty is not written."""
        data: dict = {"id": self.id}
        if self.name:
            data["name"] = self.name
        if self.description:
            data["description"] = self.description
        return data

    @classmethod
    def from_data(cls, data: dict) -> Slide:
        """Inverse of :meth:`to_data`; ``ValueError`` if it is not a slide."""
        if not isinstance(data, dict):
            raise ValueError("a slide has an id, and a name and a description that are text")
        slide_id, name, description = data.get("id"), data.get("name", ""), data.get("description", "")
        if not isinstance(slide_id, str) or not isinstance(name, str) or not isinstance(description, str):
            raise ValueError("a slide has an id, and a name and a description that are text")
        return cls(slide_id, name, description)


class Slides:
    """The slides of a document by id. They have no order here: the app keeps it (D1470, D1471)."""

    def __init__(self) -> None:
        self._by_id: dict[str, Slide] = {}

    def __contains__(self, slide_id: object) -> bool:
        return slide_id in self._by_id

    def __getitem__(self, slide_id: str) -> Slide:
        try:
            return self._by_id[slide_id]
        except KeyError:
            raise ValueError(f"unknown slide {slide_id!r}") from None

    def check_new(self, slide_id: str) -> None:
        """``ValueError`` if ``slide_id`` is not a slide id or is taken: what an app checks before it adds a slide,
        so that nothing of the slide is kept when another of its checks refuses."""
        if not _ID.fullmatch(slide_id):
            raise ValueError(f"slide id {slide_id!r}: lower-case letters, digits, '-' and '_', starting with a letter")
        if slide_id in self._by_id:
            raise ValueError(f"slide {slide_id!r} exists already")

    def add(self, slide: Slide) -> None:
        """Keep a new slide; ``ValueError`` if its id is not a slide id or is taken."""
        self.check_new(slide.id)
        self._by_id[slide.id] = slide

    def remove(self, slide_id: str) -> Slide:
        """Forget a slide; returns it whole, which is how undo gives it back."""
        slide = self[slide_id]
        del self._by_id[slide_id]
        return slide

    def rename(self, slide_id: str, name: str) -> str:
        """Give a slide another name (``""``: none); returns the name it had. Whether the name is free is the document's
        to say (D550)."""
        old = self[slide_id]
        self._by_id[slide_id] = Slide(slide_id, name, old.description)
        return old.name

    def describe(self, slide_id: str, description: str) -> str:
        """Write something about a slide (``""``: nothing); returns what was written before."""
        old = self[slide_id]
        self._by_id[slide_id] = Slide(slide_id, old.name, description)
        return old.description

    def to_data(self, order: Iterable[str]) -> list[dict]:
        """The slides as plain data, in the app's ``order``, which must name every slide once."""
        ids = list(order)
        if sorted(ids) != sorted(self._by_id):
            raise ValueError("the order must name every slide exactly once")
        return [self._by_id[slide_id].to_data() for slide_id in ids]

    @classmethod
    def from_data(cls, data: Iterable[dict]) -> tuple[Slides, list[str]]:
        """Inverse of :meth:`to_data`: the slides, and the order they were written in, which is the app's to keep."""
        slides, order = cls(), []
        for item in data:
            slide = Slide.from_data(item)
            slides.add(slide)
            order.append(slide.id)
        return slides, order
