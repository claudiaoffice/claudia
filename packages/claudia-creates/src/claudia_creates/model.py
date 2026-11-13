"""The creates document model: slides holding text boxes, shapes and images (E10.1, E10.8, E10.16).

State: the slides in order, the style book, the shape outlines and image assets the document has taken in (so
that it opens the same on any server), and the objects with their stacking order per slide.

An object is a shared :class:`~claudia_core.ObjectBody` — what it is, how large, which style, its words, its
outline or picture — and a ``SlideAnchor``, the one part that is this app's own: a point in a slide space of
1600 by 900 integer units. A view scales that space; an export (ODP, PPTX) maps it to centimetres or EMU.
Everything else about objects — placing, stacking, moving, resizing, styling — is :class:`~claudia_core.ObjectModel`
and the core object commands, shared with composes and computes.

What is not here yet: templates and layouts (E10.4), groups, free colours.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar, Self, TypeIs

from claudia_core import (
    CommandRegistry,
    DocumentModel,
    ObjectBody,
    ObjectModel,
    ObjectSet,
    Palette,
    Region,
    StyleBook,
    VisualObject,
    builtin_palette,
    new_registry,
)

from .printing import PrintSetup
from .styles import builtin_styles

SLIDE_WIDTH = 1600
SLIDE_HEIGHT = 900
FIRST_SLIDE = "s1"  # the slide of a new presentation

_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}")


def _is_whole(value: object) -> TypeIs[int]:
    """``True`` for a plain ``int`` (not a ``bool``), narrowing the type for the caller."""
    return type(value) is int


@dataclass(frozen=True)
class SlideAnchor:
    """Where an object sits on a slide: the top-left corner, in whole units of the 1600 by 900 slide space.

    This is the only thing about a creates object that computes and composes do not share. A slide has absolute
    coordinates and a fixed size, so an anchor is a point and nothing on the slide ever moves it by itself."""

    kind: ClassVar[str] = "slide"
    slide: str
    x: int
    y: int

    @property
    def container(self) -> str:
        """The slide this object belongs to."""
        return self.slide

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {"kind": self.kind, "container": self.slide, "x": self.x, "y": self.y}

    @classmethod
    def from_data(cls, data: dict) -> SlideAnchor:
        """Read an anchor sent by a client or stored in the log; ``ValueError`` if it is not one."""
        if data.get("kind") != cls.kind:
            raise ValueError(f"creates knows only slide anchors, not {data.get('kind')!r}")
        slide, x, y = data.get("container"), data.get("x"), data.get("y")
        if not isinstance(slide, str) or not _is_whole(x) or not _is_whole(y):
            raise ValueError("a slide anchor names a slide and whole x and y")
        return cls(slide, x, y)


#: One thing on a slide: a text box, a shape or an image. The body is shared with the other two apps; only the
#: anchor is this app's own.
type SlideObject = VisualObject[SlideAnchor]


class SlideModel(DocumentModel, ObjectModel[SlideAnchor]):
    """A presentation: slides, its styles, the shapes and images it knows, and the objects on its slides.

    See the module description. Everything about objects that is not the slide space itself comes from
    :class:`~claudia_core.ObjectModel`."""

    app: ClassVar[str] = "creates"
    # 6: the presentation carries its own colour palette (D200)
    # 7: how it is printed, and its language (D917)
    state_schema: ClassVar[int] = 9  # 7: object bodies without a description; 8: no rendered containers
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(
        self,
        styles: StyleBook | None = None,
        palette: Palette | None = None,
        print_setup: PrintSetup | None = None,
        language: str | None = None,
    ) -> None:
        super().__init__()
        self.slides: list[str] = []
        #: How the slides are printed, as a layout and a page (D917).
        self.print_setup: PrintSetup = print_setup if print_setup is not None else PrintSetup()
        #: The language of the presentation, a BCP 47 tag, or ``None`` when it is not known (D915, D917).
        self.language: str | None = language
        self.styles: StyleBook = styles if styles is not None else builtin_styles()
        #: The colours of this presentation, by what they mean. Part of the document, so it looks the same on
        #: whichever server it is opened (D200); the built-in styles are written entirely in terms of it.
        self.palette: Palette = palette if palette is not None else builtin_palette()

    @classmethod
    def empty(cls) -> Self:
        """A new presentation: one empty slide, ``s1``, so that there is always something to put things on."""
        model = cls()
        model.insert_slide(FIRST_SLIDE)
        return model

    def serialize(self) -> dict:
        return {
            "slides": list(self.slides),
            "styles": self.styles.to_data(),
            "palette": self.palette.to_data(),
            "shapes": self.shapes_to_data(),
            "images": self.images_to_data(),
            "objects": self.objects_to_data(),
            "renderings": self.renderings_to_data(),
            "print_setup": self.print_setup.to_data(),
            "language": self.language,
        }

    @classmethod
    def restore(cls, state: dict) -> Self:
        # schema 6 and earlier: printed slide-sized, no language
        setup = PrintSetup.from_data(state["print_setup"]) if "print_setup" in state else None
        model = cls(
            StyleBook.from_data(state["styles"]), Palette.from_data(state["palette"]), setup, state.get("language")
        )
        model.slides = list(state["slides"])
        for slide in model.slides:
            model.open_container(slide)
        model.restore_objects(
            state["objects"], state["images"], state["shapes"], renderings=state.get("renderings", ())
        )
        return model

    def region_from_data(self, data: dict) -> Region:
        return ObjectSet.from_data(data)

    # -- the object seam -------------------------------------------------------
    def containers(self) -> list[str]:
        """The slides objects may sit on, in order."""
        return self.slides

    def anchor_from_data(self, data: dict) -> SlideAnchor:
        """Read a slide anchor; ``ValueError`` if the data is not one."""
        return SlideAnchor.from_data(data)

    def check_anchor(self, anchor: SlideAnchor, body: ObjectBody) -> None:
        """An object must stay on its slide, whole units only."""
        if not _is_whole(anchor.x) or not _is_whole(anchor.y):
            raise ValueError("x and y must be whole numbers")
        if anchor.x < 0 or anchor.y < 0 or anchor.x + body.w > SLIDE_WIDTH or anchor.y + body.h > SLIDE_HEIGHT:
            raise ValueError(f"the object must stay on the slide ({SLIDE_WIDTH} by {SLIDE_HEIGHT} units)")

    # -- reading ---------------------------------------------------------------
    def get(self, object_id: str) -> SlideObject:
        """The object with this id; ``ValueError`` if there is none. (``get_object``'s older name.)"""
        return self.get_object(object_id)

    # -- slides ----------------------------------------------------------------
    def insert_slide(self, slide: str, at: int | None = None) -> None:
        """Add a slide at position ``at`` (the end by default)."""
        if not _ID.fullmatch(slide):
            raise ValueError(f"slide id {slide!r}: lower-case letters, digits, '-' and '_', starting with a letter")
        if slide in self.slides:
            raise ValueError(f"slide {slide!r} exists already")
        if at is not None and not 0 <= at <= len(self.slides):
            raise ValueError(f"there is no place {at} among {len(self.slides)} slides")
        self.slides.insert(len(self.slides) if at is None else at, slide)
        self.open_container(slide)

    def delete_slide(self, slide: str) -> int:
        """Remove an empty slide; returns the place it had."""
        if slide not in self.slides:
            raise ValueError(f"unknown slide {slide!r}")
        if self.stack_of(slide):
            raise ValueError(f"slide {slide!r} still has objects; remove them first")
        place = self.slides.index(slide)
        del self.slides[place]
        self.close_container(slide)
        return place
