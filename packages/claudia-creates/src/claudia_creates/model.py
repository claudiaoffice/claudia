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
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import ClassVar, Self, TypeIs

from claudia_core import (
    N_,
    Command,
    CommandRegistry,
    DocumentModel,
    Field,
    FontRequirement,
    Generated,
    Label,
    ListBook,
    ListItem,
    ObjectBody,
    ObjectModel,
    ObjectSet,
    Palette,
    Placed,
    Region,
    Requirements,
    Run,
    SchemeBook,
    SetLanguage,
    StyleBook,
    TextCommand,
    TextStructure,
    VisualObject,
    builtin_palette,
    new_registry,
    nudge_into,
    turned_extent,
)

from .printing import PrintSetup
from .styles import builtin_styles

SLIDE_WIDTH = 1600
SLIDE_HEIGHT = 900
FIRST_SLIDE = "s1"  # the slide of a new presentation
#: The longest speaker notes of a slide, in characters (D342): a page of text, not a manuscript.
MAX_NOTES_LENGTH = 20000
#: The longest planned time of a slide, in seconds: one day (D343).
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
    def holder(self) -> str:
        """The slide this object belongs to."""
        return self.slide

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {"kind": self.kind, "holder": self.slide, "x": self.x, "y": self.y}

    @classmethod
    def from_data(cls, data: dict) -> SlideAnchor:
        """Read an anchor sent by a client or stored in the log; ``ValueError`` if it is not one."""
        if data.get("kind") != cls.kind:
            raise ValueError(f"creates knows only slide anchors, not {data.get('kind')!r}")
        slide, x, y = data.get("holder"), data.get("x"), data.get("y")
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
    name_taken: ClassVar[Mapping[str, str]] = {
        **ObjectModel.name_taken,
        "slide": N_("There is already a slide called “{name}”"),
    }
    # 6: the presentation carries its own colour palette (D200)
    # 7: how it is printed, and its language (D917)
    # 8: object bodies carry a description (alternative text)
    # 9: speaker notes (Markdown, D342) and planned times (D343) of the slides
    # 10: containers (D390)
    # 11: slides have names, in one namespace with the objects (D550)
    # 12: styles carry heading levels; a new presentation has a slide title style (E9.22, E10.21)
    # 13: the presentation holds lists, whose items are the words of text boxes and shapes (step C, E10.21)
    # 14: the presentation holds its numbering schemes; styles may name a list that numbers them (step D, E9.22)
    # 15: the words of a text box may be generated (an agenda, step E, E9.31)
    # 16: an object body has one ``ref`` instead of a field per kind
    state_schema: ClassVar[int] = 17  # 17: slides may have descriptions, by their id (D1317, D1318)
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
        #: The speaker notes of the slides that have any, as written in Markdown (D342).
        self.notes: dict[str, str] = {}
        #: The planned time of the slides that have one, in whole seconds (D343).
        self.times: dict[str, int] = {}
        #: The names of the slides that have one (D550); a name is shared with the objects, so see ``named_things``.
        self.slide_names: dict[str, str] = {}
        #: What was written about the slides that have something (D1317, D1318), beside their names.
        self.slide_descriptions: dict[str, str] = {}
        #: How the slides are printed, as a layout and a page (D917).
        self.print_setup: PrintSetup = print_setup if print_setup is not None else PrintSetup()
        #: The language of the presentation, a BCP 47 tag, or ``None`` when it is not known (D915, D917).
        self.language: str | None = language
        self.styles: StyleBook = styles if styles is not None else builtin_styles()
        #: The colours of this presentation, by what they mean. Part of the document, so it looks the same on
        #: whichever server it is opened (D200); the built-in styles are written entirely in terms of it.
        self.palette: Palette = palette if palette is not None else builtin_palette()
        #: The lists the words of the objects may be items of (E10.21). What a list is, not which words are in it.
        self.lists: ListBook = ListBook()
        #: How the lists are drawn (E9.22), part of the presentation; the built-in schemes to start with.
        self.schemes: SchemeBook = SchemeBook()
        #: Changes when a slide comes or goes, and so the order the words are read in (step C).
        #: Objects keep their own count.
        self._slide_order = 0
        #: What is derived from the structure of the words, the same in every app. The presentation is its host.
        self.structure = TextStructure(self)

    @classmethod
    def empty(cls) -> Self:
        """A new presentation: one empty slide, ``s1``, so that there is always something to put things on."""
        model = cls()
        model.insert_slide(FIRST_SLIDE)
        return model

    @classmethod
    def setup_commands(cls, language: str | None) -> tuple[Command, ...]:
        """A new presentation starts in the language of its maker's interface (D915), set by the server when it creates
        the document rather than by her client as her own first step (UX-33)."""
        return () if language is None else (SetLanguage(language),)

    def requirements(self) -> Requirements:
        """The fonts the styles ask for by name are what this document needs from the server (E1.9, D1306)."""
        return Requirements(fonts=tuple(FontRequirement(family) for family in self.styles.font_families()))

    def serialize(self) -> dict:
        return {
            "slides": list(self.slides),
            "notes": dict(self.notes),
            "times": dict(self.times),
            "names": dict(self.slide_names),
            "descriptions": dict(self.slide_descriptions),
            "styles": self.styles.to_data(),
            "palette": self.palette.to_data(),
            **self.assets_to_data(),  # images, shapes, diagrams, containers, tables (D1431)
            "objects": self.objects_to_data(),
            "print_setup": self.print_setup.to_data(),
            "language": self.language,
            "lists": self.lists.to_data(),
            "schemes": self.schemes.to_data(),
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
            model.open_holder(slide)
        # schema 8 and earlier: no notes and no planned times
        model.notes = {k: v for k, v in state.get("notes", {}).items() if k in model.slides and v}
        model.times = {k: v for k, v in state.get("times", {}).items() if k in model.slides}
        # schema 10 and earlier: no names
        model.slide_names = {k: v for k, v in state.get("names", {}).items() if k in model.slides and v}
        # schema 16 and earlier: nothing was written about a slide
        model.slide_descriptions = {k: v for k, v in state.get("descriptions", {}).items() if k in model.slides and v}
        model.restore_objects(state["objects"], state)
        model.lists = ListBook.from_data(state.get("lists", ()))  # schema 12 and earlier: no lists
        model.schemes = SchemeBook.from_data(state.get("schemes"))  # schema 13 and earlier: the built-in ones
        model.structure = TextStructure(model)  # the clients learn the labels with the document
        return model

    def blank(self, parts: frozenset[str] | None) -> None:
        """Blank what ``parts`` names, for redacting an import (D723), or everything for ``None``: a slide's id takes
        its speaker notes and blanks every object on it, an object's id blanks that object. Slides, their names,
        planned times and every place and size stay. ``ValueError`` for a part the presentation does not have."""
        slides = set(self.slides)
        if parts is not None and (unknown := sorted(parts - slides - set(self.objects))):
            raise ValueError(f"the presentation has no slide or object {unknown[0]!r}")
        chosen = slides if parts is None else slides & parts
        self.notes = {slide: text for slide, text in self.notes.items() if slide not in chosen}
        self.slide_descriptions = {k: v for k, v in self.slide_descriptions.items() if k not in chosen}
        if parts is None:
            self.blank_objects(None)
            return
        on_slides = {obj.id for slide in chosen for obj in self.objects_on(slide)}
        self.blank_objects(frozenset(on_slides | (parts & set(self.objects))))

    def region_from_data(self, data: dict) -> Region:
        return ObjectSet.from_data(data)

    # -- the object seam -------------------------------------------------------
    def holders(self) -> list[str]:
        """The slides objects may sit on, in order."""
        return self.slides

    def anchor_from_data(self, data: dict) -> SlideAnchor:
        """Read a slide anchor; ``ValueError`` if the data is not one."""
        return SlideAnchor.from_data(data)

    def room_for_new_object(self, anchor: SlideAnchor | None) -> int | None:
        """What is left of the slide to the right of where a new object starts (D1332): an object stays on its slide."""
        return SLIDE_WIDTH - (anchor.x if anchor is not None else 0)

    def check_anchor(self, anchor: SlideAnchor, body: ObjectBody) -> None:
        """An object must stay on its slide, whole units only. What has to be on the slide is the object's outline: its
        frame when it is upright, and what a turn makes of it otherwise, so the anchor of a turned object may lie
        outside the slide while the object does not."""
        if not _is_whole(anchor.x) or not _is_whole(anchor.y):
            raise ValueError("x and y must be whole numbers")
        if (anchor.x, anchor.y) != nudge_into(
            anchor.x, anchor.y, body.w, body.h, body.rotation, SLIDE_WIDTH, SLIDE_HEIGHT
        ):
            raise ValueError(f"the object must stay on the slide ({SLIDE_WIDTH} by {SLIDE_HEIGHT} units)")

    def turned_anchor(self, obj: SlideObject, rotation: int) -> SlideAnchor:
        """The nearest place for ``obj`` at which turned to ``rotation`` its outline is on the slide."""
        body = obj.body
        place = nudge_into(obj.anchor.x, obj.anchor.y, body.w, body.h, rotation, SLIDE_WIDTH, SLIDE_HEIGHT)
        if place is None:
            out_w, out_h = turned_extent(body.w, body.h, rotation)
            raise ValueError(
                f"this object is too large to turn that way: it would be {out_w} by {out_h} units on a slide of "
                f"{SLIDE_WIDTH} by {SLIDE_HEIGHT}"
            )
        return SlideAnchor(obj.anchor.slide, *place)

    # -- reading ---------------------------------------------------------------
    def get(self, object_id: str) -> SlideObject:
        """The object with this id; ``ValueError`` if there is none. (``get_object``'s older name.)"""
        return self.get_object(object_id)

    # -- slides ----------------------------------------------------------------
    def insert_slide(
        self,
        slide: str,
        at: int | None = None,
        notes: str = "",
        seconds: int | None = None,
        name: str = "",
        description: str = "",
    ) -> None:
        """Add a slide at position ``at`` (the end by default), optionally with its notes, planned time, name and
        description (which is how undoing the removal of a slide gives them back)."""
        if not _ID.fullmatch(slide):
            raise ValueError(f"slide id {slide!r}: lower-case letters, digits, '-' and '_', starting with a letter")
        if slide in self.slides:
            raise ValueError(f"slide {slide!r} exists already")
        if at is not None and not 0 <= at <= len(self.slides):
            raise ValueError(f"there is no place {at} among {len(self.slides)} slides")
        notes = _checked_notes(notes)
        if seconds is not None:
            _check_seconds(seconds)
        self.check_thing_name(slide, name)
        self.slides.insert(len(self.slides) if at is None else at, slide)
        self.open_holder(slide)
        self._slide_order += 1
        if notes:
            self.notes[slide] = notes
        if seconds is not None:
            self.times[slide] = seconds
        if description:
            self.slide_descriptions[slide] = description
        if name:
            self.slide_names[slide] = name

    def delete_slide(self, slide: str) -> int:
        """Remove an empty slide; returns the place it had."""
        if slide not in self.slides:
            raise ValueError(f"unknown slide {slide!r}")
        if self.stack_of(slide):
            raise ValueError(f"slide {slide!r} still has objects; remove them first")
        place = self.slides.index(slide)
        del self.slides[place]
        self.close_holder(slide)
        self._slide_order += 1
        self.notes.pop(slide, None)
        self.times.pop(slide, None)
        self.slide_names.pop(slide, None)
        self.slide_descriptions.pop(slide, None)
        return place

    # -- the shared text structure (step C): the presentation as a ParagraphHost ---------
    def reading_order(self) -> Iterator[Placed]:
        """The words of the objects in the order they are read: slide by slide, on each slide in stacking order,
        bottom first (as PowerPoint reads a slide to a screen reader; the owner's decision of 2026-11-16). The place a
        reader finds them at is the slide's number."""
        for number, slide in enumerate(self.slides, start=1):
            for obj in self.objects_on(slide):
                if obj.body.paragraph is not None:
                    yield Placed(obj.body.paragraph, slide, True, str(number))

    @property
    def structure_version(self) -> tuple[int, int]:
        """Changes when a slide or an object came or went, or the words of an object became another list item."""
        return (self._slide_order, self.paragraph_order)

    def labels(self) -> dict[str, Label]:
        """The marker of every list item among the objects' words, by object id (:class:`claudia_core.TextStructure`).
        Shared with the structure, so callers must not change it."""
        return self.structure.labels()

    def list_in_use(self, list_id: str) -> bool:
        """Are the words of any object an item of this list? (Asked by the list commands before they take one back.)"""
        return self.object_list_in_use(list_id)

    # -- list items of the objects' words (claudia_core.ItemHost) ---------------------------------
    def item_of(self, paragraph_id: str) -> ListItem | None:
        """The item the words of an object are; an object's paragraph has the object's id."""
        return self.object_item(paragraph_id)

    def put_item(self, paragraph_id: str, item: ListItem | None) -> object:
        """Make the words of an object an item; the event that tells the clients."""
        return self.put_object_item(paragraph_id, item)

    def generated_of(self, paragraph_id: str) -> Generated | None:
        """The options of the agenda the words of an object are, or ``None``."""
        return self.object_generated(paragraph_id)

    def put_generated(self, paragraph_id: str, generated: Generated | None) -> object:
        """Make the words of an empty text box an agenda, or plain again; the event that tells the clients."""
        return self.put_object_generated(paragraph_id, generated)

    def item_regions(self, paragraph_id: str) -> tuple[Region, ...]:
        """The object whose words they are."""
        return self.selection_of(paragraph_id)

    # -- typing (claudia_core.TypingHost): the words of an object, character by character (step G) ----------------
    def insert_text(
        self, paragraph_id: str, offset: int, text: str, runs: list[Run], fields: tuple[Field, ...] = ()
    ) -> tuple[object, ...]:
        """Type into the words of an object; the event that tells the clients."""
        return (self.insert_object_text(paragraph_id, offset, text, runs, fields),)

    def remove_text(
        self, paragraph_id: str, start: int, end: int
    ) -> tuple[str, list[Run], tuple[Field, ...], tuple[object, ...]]:
        """Cut characters out of the words of an object."""
        text, runs, fields, event = self.remove_object_text(paragraph_id, start, end)
        return text, runs, fields, (event,)

    def fields_of(self, paragraph_id: str) -> tuple[Field, ...]:
        """The fields in the words of an object (step H)."""
        return self.object_fields(paragraph_id)

    def put_fields(self, paragraph_id: str, fields: tuple[Field, ...]) -> tuple[object, ...]:
        """Give the words of an object other fields; the event that tells the clients."""
        return (self.put_object_fields(paragraph_id, fields),)

    def text_regions(self, paragraph_id: str, start: int, end: int) -> tuple[Region, ...]:
        """The object whose words change."""
        return self.selection_of(paragraph_id)

    def text_moved(self, command: TextCommand) -> tuple[object, ...]:
        """Nothing on a slide hangs from words: nothing follows."""
        return ()

    def settle(self, ctx) -> None:
        """Tell the clients which labels changed: a text box taken away may renumber every one after it."""
        self.structure.settle(ctx)

    # -- names (D550) ------------------------------------------------------------
    def named_things(self):
        """The objects with names, then the slides with names: one namespace."""
        yield from super().named_things()
        for slide in self.slides:
            if slide in self.slide_names:
                yield "slide", slide, self.slide_names[slide]

    def unnamed_things(self):
        """The slides without a name, then the objects without one."""
        for slide in self.slides:
            if slide not in self.slide_names:
                yield "slide", slide
        yield from super().unnamed_things()

    def thing_name(self, thing_id: str) -> str:
        """The name of an object or a slide, ``""`` if it has none; ``ValueError`` if there is neither."""
        if thing_id in self.slides:
            return self.slide_names.get(thing_id, "")
        return super().thing_name(thing_id)

    def set_thing_name(self, thing_id: str, name: str) -> str:
        """Name an object or a slide; returns the name it had."""
        if thing_id not in self.slides:
            return super().set_thing_name(thing_id, name)
        old = self.slide_names.get(thing_id, "")
        if name:
            self.slide_names[thing_id] = name
        else:
            self.slide_names.pop(thing_id, None)
        return old

    def thing_description(self, thing_id: str) -> str:
        """What is written about an object or a slide, ``""`` if nothing; ``ValueError`` if there is neither."""
        if thing_id not in self.slides:
            return super().thing_description(thing_id)
        return self.slide_descriptions.get(thing_id, "")

    def set_thing_description(self, thing_id: str, description: str) -> str:
        """Write something about a slide (``""``: nothing); returns what was written. An object is described by
        :class:`~claudia_core.DescribeObject`."""
        if thing_id not in self.slides:
            return super().set_thing_description(thing_id, description)
        old = self.slide_descriptions.get(thing_id, "")
        if description:
            self.slide_descriptions[thing_id] = description
        else:
            self.slide_descriptions.pop(thing_id, None)
        return old

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
