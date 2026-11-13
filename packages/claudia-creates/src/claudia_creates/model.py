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
#: The longest speaker notes of a slide, in characters (D293): a page of text, not a manuscript.
MAX_NOTES_LENGTH = 20000
#: The longest planned time of a slide, in seconds: one day (D294).
MAX_SLIDE_SECONDS = 86400

_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}")


def _is_whole(value: object) -> TypeIs[int]:
    """``True`` for a plain ``int`` (not a ``bool``), narrowing the type for the caller."""
    return type(value) is int


def _checked_notes(text: object) -> str:
    """The notes as they are kept: line ends as ``\\n``; ``ValueError`` if they are not text we keep."""
    if not isinstance(text, str):
        raise ValueError("notes are text")
    if "\x00" in text:
        raise ValueError("notes must not contain a null character")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > MAX_NOTES_LENGTH:
        raise ValueError(f"notes are at most {MAX_NOTES_LENGTH} characters")
    return text


def _check_seconds(seconds: object) -> None:
    """``ValueError`` unless ``seconds`` is a whole number from 1 to a day."""
    if not _is_whole(seconds) or not 1 <= seconds <= MAX_SLIDE_SECONDS:
        raise ValueError(f"a planned time is a whole number of seconds from 1 to {MAX_SLIDE_SECONDS}")


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
    # 8: speaker notes (Markdown, D293) and planned times (D294) of the slides
    state_schema: ClassVar[int] = 8
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
        #: The speaker notes of the slides that have any, as written in Markdown (D293).
        self.notes: dict[str, str] = {}
        #: The planned time of the slides that have one, in whole seconds (D294).
        self.times: dict[str, int] = {}
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
            "notes": dict(self.notes),
            "times": dict(self.times),
            "styles": self.styles.to_data(),
            "palette": self.palette.to_data(),
            "shapes": self.shapes_to_data(),
            "images": self.images_to_data(),
            "objects": self.objects_to_data(),
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
        # schema 7 and earlier: no notes and no planned times
        model.notes = {k: v for k, v in state.get("notes", {}).items() if k in model.slides and v}
        model.times = {k: v for k, v in state.get("times", {}).items() if k in model.slides}
        model.restore_objects(state["objects"], state["images"], state["shapes"])
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
    def insert_slide(self, slide: str, at: int | None = None, notes: str = "", seconds: int | None = None) -> None:
        """Add a slide at position ``at`` (the end by default), optionally with its notes and planned time (which is
        how undoing the removal of a slide gives them back)."""
        if not _ID.fullmatch(slide):
            raise ValueError(f"slide id {slide!r}: lower-case letters, digits, '-' and '_', starting with a letter")
        if slide in self.slides:
            raise ValueError(f"slide {slide!r} exists already")
        if at is not None and not 0 <= at <= len(self.slides):
            raise ValueError(f"there is no place {at} among {len(self.slides)} slides")
        notes = _checked_notes(notes)
        if seconds is not None:
            _check_seconds(seconds)
        self.slides.insert(len(self.slides) if at is None else at, slide)
        self.open_container(slide)
        if notes:
            self.notes[slide] = notes
        if seconds is not None:
            self.times[slide] = seconds

    def delete_slide(self, slide: str) -> int:
        """Remove an empty slide; returns the place it had."""
        if slide not in self.slides:
            raise ValueError(f"unknown slide {slide!r}")
        if self.stack_of(slide):
            raise ValueError(f"slide {slide!r} still has objects; remove them first")
        place = self.slides.index(slide)
        del self.slides[place]
        self.close_container(slide)
        self.notes.pop(slide, None)
        self.times.pop(slide, None)
        return place

    # -- notes and planned times (E10.2) -----------------------------------------
    def notes_of(self, slide: str) -> str:
        """The speaker notes of a slide, ``""`` if it has none; ``ValueError`` for an unknown slide."""
        self._require_slide(slide)
        return self.notes.get(slide, "")

    def set_notes(self, slide: str, text: str) -> str:
        """Set the notes of a slide (``""`` clears them); returns the notes it had."""
        self._require_slide(slide)
        old = self.notes.get(slide, "")
        text = _checked_notes(text)
        if text:
            self.notes[slide] = text
        else:
            self.notes.pop(slide, None)
        return old

    def time_of(self, slide: str) -> int | None:
        """The planned time of a slide in seconds, ``None`` if it has none; ``ValueError`` for an unknown slide."""
        self._require_slide(slide)
        return self.times.get(slide)

    def set_time(self, slide: str, seconds: int | None) -> int | None:
        """Set the planned time of a slide (``None`` clears it); returns the time it had."""
        self._require_slide(slide)
        old = self.times.get(slide)
        if seconds is None:
            self.times.pop(slide, None)
        else:
            _check_seconds(seconds)
            self.times[slide] = seconds
        return old

    def total_time(self) -> int:
        """The planned times of all slides added up, in seconds; a slide without one counts as nothing."""
        return sum(self.times.values())

    def _require_slide(self, slide: str) -> None:
        if slide not in self.slides:
            raise ValueError(f"unknown slide {slide!r}")
