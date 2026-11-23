"""The creates document model: slides holding text boxes, shapes and images (E10.1, E10.8, E10.16).

State: the slides in order, the style book, the shape outlines and image assets the document has taken in (so
that it opens the same on any server), and the objects with their stacking order per slide.

An object is a shared :class:`~claudia_core.ObjectBody` — what it is, how large, which style, its words, its
outline or picture — and a ``SlideAnchor``, the one part that is this app's own: a point in a slide space of
1600 by 900 integer units. A view scales that space; an export (ODP, PPTX) maps it to centimetres or EMU.
Everything else about objects — placing, stacking, moving, resizing, styling — is :class:`~claudia_core.ObjectModel`
and the core object commands, shared with composes and computes.

What is not here yet: templates (E10.4, patch 2), groups, free colours.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import replace
from typing import ClassVar, NamedTuple, Self, TypeIs

from claudia_core import (
    N_,
    Command,
    CommandRegistry,
    DocumentModel,
    Field,
    FontRequirement,
    Generated,
    Label,
    Layout,
    Layouts,
    ListBook,
    ListItem,
    ObjectBody,
    ObjectModel,
    ObjectSet,
    Palette,
    Placed,
    Refusal,
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
)
from claudia_core.slides import (
    Slide,
    SlideAnchor,
    Slides,
    check_on_slide,
    room_on_slide,
    turned_on_slide,
)

from .printing import PrintSetup
from .styles import builtin_styles

FIRST_SLIDE = "s1"  # the slide of a new presentation
#: The layout every presentation has (E10.4, D1530): no placeholder, nothing on it. It can be hidden, never removed.
BASIC_LAYOUT = "basic"
#: The longest speaker notes of a slide, in characters (D342): a page of text, not a manuscript.
MAX_NOTES_LENGTH = 20000
#: The longest planned time of a slide, in seconds: one day (D343).
MAX_SLIDE_SECONDS = 86400


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
        raise Refusal("notes are at most {limit} characters", limit=MAX_NOTES_LENGTH)
    return text


def _check_seconds(seconds: object) -> None:
    """``ValueError`` unless ``seconds`` is a whole number from 1 to a day."""
    if not _is_whole(seconds) or not 1 <= seconds <= MAX_SLIDE_SECONDS:
        raise Refusal(
            "a planned time is a whole number of seconds from 1 to {limit}",
            limit=MAX_SLIDE_SECONDS,
        )


#: One thing on a slide: a text box, a shape or an image. The body is shared with the other two apps; only the
#: anchor is this app's own.
type SlideObject = VisualObject[SlideAnchor]


class _ObjectTable(dict[str, SlideObject]):
    """The objects by id, which also knows what is bound to which placeholder and what was written since the bound
    copies were last settled, so that settling looks only at what a command touched (PERF-12). Only item assignment
    and ``del`` are used on it, and only those keep the two records."""

    def __init__(self) -> None:
        super().__init__()
        #: The ids that were written or removed since the last settling.
        self.touched: set[str] = set()
        #: The ids of the objects bound to a placeholder, by the id of the placeholder.
        self.followers: dict[str, set[str]] = {}

    def __setitem__(self, key: str, obj: SlideObject) -> None:
        self._unbind(key)
        super().__setitem__(key, obj)
        self.touched.add(key)
        if placeholder := obj.anchor.bound_to_placeholder:
            self.followers.setdefault(placeholder, set()).add(key)

    def __delitem__(self, key: str) -> None:
        self._unbind(key)
        super().__delitem__(key)
        self.touched.add(key)

    def _unbind(self, key: str) -> None:
        if (old := self.get(key)) is not None and (placeholder := old.anchor.bound_to_placeholder):
            self.followers[placeholder].discard(key)


def is_empty(obj: SlideObject) -> bool:
    """Is there nothing in this object that a person put there? A box with no words."""
    return obj.body.paragraph is not None and not obj.body.paragraph.text


def _own_place(obj: SlideObject) -> tuple:
    """What a placeholder gives the objects bound to it: place, size, turn and look."""
    return (obj.anchor.x, obj.anchor.y, obj.body.w, obj.body.h, obj.body.rotation, obj.body.style)


def _placed(obj: SlideObject, place: tuple) -> SlideObject:
    """``obj`` at a place, size, turn and look that :func:`_own_place` gave."""
    x, y, w, h, rotation, style = place
    return replace(
        obj, anchor=replace(obj.anchor, x=x, y=y), body=replace(obj.body, w=w, h=h, rotation=rotation, style=style)
    )


class SlideLayoutWas(NamedTuple):
    """What undoing :meth:`SlideModel.put_slide_on_layout` needs (see there)."""

    layout: str
    bindings: dict[str, str]
    frames: dict[str, tuple]


def _bound_to(obj: SlideObject, placeholder: SlideObject) -> SlideObject:
    """``obj`` with the place, size, turn and look of ``placeholder`` (the look only if both are of one kind: a picture
    in a text placeholder keeps its own)."""
    body = replace(obj.body, w=placeholder.body.w, h=placeholder.body.h, rotation=placeholder.body.rotation)
    if body.kind == placeholder.body.kind:
        body = replace(body, style=placeholder.body.style)
    anchor = replace(obj.anchor, x=placeholder.anchor.x, y=placeholder.anchor.y)
    return replace(obj, anchor=anchor, body=body)


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
    # 17: slides may have descriptions, by their id (D1317, D1318)
    # 18: the slides are records (the core's Slide, D1470), in the order of the presentation
    # 19: layouts, and the layout every slide follows (E10.4, D1530)
    state_schema: ClassVar[int] = 19
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(
        self,
        styles: StyleBook | None = None,
        palette: Palette | None = None,
        print_setup: PrintSetup | None = None,
        language: str | None = None,
    ) -> None:
        super().__init__()
        #: The ids of the slides in the order of the presentation; what each slide is, is in ``slides``.
        self.order: list[str] = []
        #: The layouts a slide may follow, in the order a person sees them; the basic one to start with (E10.4).
        self.layouts: Layouts = Layouts()
        self.layouts.add(Layout(BASIC_LAYOUT, "Basic", "builtin"))
        self.open_holder(BASIC_LAYOUT)
        self.objects: _ObjectTable = _ObjectTable()
        #: The slides whose layout was changed since the bound copies were last settled (PERF-12).
        self._slides_on_new_layouts: set[str] = set()
        #: The layout every slide follows, by slide id.
        self.slide_layouts: dict[str, str] = {}
        #: The slides as records, with their names (one namespace with the objects, D550) and descriptions (D1317).
        self.slides: Slides = Slides()
        #: The speaker notes of the slides that have any, as written in Markdown (D342).
        self.notes: dict[str, str] = {}
        #: The planned time of the slides that have one, in whole seconds (D343).
        self.times: dict[str, int] = {}
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
            "slides": self.slides.to_data(self.order),
            "layouts": self.layouts.to_data(),
            "slide_layouts": dict(self.slide_layouts),
            "notes": dict(self.notes),
            "times": dict(self.times),
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
        model.slides, model.order = Slides.from_data(state["slides"])
        for slide in model.order:
            model.open_holder(slide)
        # schema 18 and earlier: no layouts, every slide follows the basic one
        if "layouts" in state:
            model.layouts = Layouts.from_data(state["layouts"])
            for layout in model.layouts.ids():
                model.open_holder(layout)
        model.slide_layouts = {slide: state.get("slide_layouts", {}).get(slide, BASIC_LAYOUT) for slide in model.order}
        # schema 8 and earlier: no notes and no planned times
        model.notes = {k: v for k, v in state.get("notes", {}).items() if k in model.order and v}
        model.times = {k: v for k, v in state.get("times", {}).items() if k in model.order}
        model.restore_objects(state["objects"], state)
        model.lists = ListBook.from_data(state.get("lists", ()))  # schema 12 and earlier: no lists
        model.schemes = SchemeBook.from_data(state.get("schemes"))  # schema 13 and earlier: the built-in ones
        model.structure = TextStructure(model)  # the clients learn the labels with the document
        return model

    def blank(self, parts: frozenset[str] | None) -> None:
        """Blank what ``parts`` names, for redacting an import (D723), or everything for ``None``: a slide's id takes
        its speaker notes and blanks every object on it, a layout's id blanks every object on the layout, an object's id
        blanks that object. Slides, their names, planned times and every place and size stay. ``ValueError`` for a
        part the presentation does not have."""
        slides = set(self.order)
        layouts = set(self.layouts.ids())
        if parts is not None and (unknown := sorted(parts - slides - layouts - set(self.objects))):
            raise ValueError(f"the presentation has no slide, layout or object {unknown[0]!r}")
        chosen = slides if parts is None else slides & parts
        self.notes = {slide: text for slide, text in self.notes.items() if slide not in chosen}
        for slide in chosen:
            self.slides.describe(slide, "")
        if parts is None:
            self.blank_objects(None)
            return
        on_holders = {obj.id for holder in chosen | layouts & parts for obj in self.objects_on(holder)}
        self.blank_objects(frozenset(on_holders | (parts & set(self.objects))))

    def region_from_data(self, data: dict) -> Region:
        return ObjectSet.from_data(data)

    # -- the object seam -------------------------------------------------------
    def holders(self) -> list[str]:
        """The slides objects may sit on, in order."""
        return self.order

    def layout_holders(self) -> list[str]:
        """The layouts, which hold the placeholders and other objects slides follow (E10.4, D1530)."""
        return self.layouts.ids()

    def anchor_from_data(self, data: dict) -> SlideAnchor:
        """Read a slide anchor; ``ValueError`` if the data is not one."""
        return SlideAnchor.from_data(data)

    def placed_at(self, old: SlideAnchor, new: SlideAnchor) -> SlideAnchor:
        """A move or resize says where, not what the object is for or what it is bound to (E10.4)."""
        if new.slide != old.slide:
            return new
        return replace(new, purpose=old.purpose, bound_to_placeholder=old.bound_to_placeholder)

    def room_for_new_object(self, anchor: SlideAnchor | None) -> int | None:
        """The core's rule for every slide (D1470)."""
        return room_on_slide(anchor)

    def check_anchor(self, anchor: SlideAnchor, body: ObjectBody) -> None:
        """An object must stay on its slide (the core's rule for every slide, D1470). A purpose is for a placeholder,
        which is on a layout, and a layout has each purpose once (E10.4, D1532)."""
        check_on_slide(anchor, body)
        if not anchor.purpose:
            return
        if anchor.slide not in self.layouts:
            raise Refusal("only a placeholder on a layout has a purpose")
        if any(o.anchor.purpose == anchor.purpose and o.id != body.id for o in self.objects_on(anchor.slide)):
            raise Refusal("a layout has one placeholder for each purpose: {purpose}", purpose=anchor.purpose)

    def replace_object(self, obj: SlideObject) -> SlideObject:
        """As the kernel's, but what only the layout changes of an object bound to a placeholder (its place, size, turn
        and look) is not changed here: ``Refusal`` (E10.4). Settling does not come this way, and a copy that lags
        behind its placeholder in the middle of a Batch may still be written in."""
        old = self.get_object(obj.id)
        if self.placeholder_of(obj) is not None and _own_place(old) != _own_place(obj):
            raise Refusal("this object has the place, size and look of its placeholder: change the layout instead")
        return super().replace_object(obj)

    def turned_anchor(self, obj: SlideObject, rotation: int) -> SlideAnchor:
        """The nearest place for ``obj`` at which turned to ``rotation`` its outline is on the slide."""
        return turned_on_slide(obj, rotation)

    # -- reading ---------------------------------------------------------------
    def get(self, object_id: str) -> SlideObject:
        """The object with this id; ``ValueError`` if there is none. (``get_object``'s older name.)"""
        return self.get_object(object_id)

    # -- layouts (E10.4) -------------------------------------------------------
    def layout_of(self, slide: str) -> str:
        """The id of the layout a slide follows; ``ValueError`` if there is no such slide."""
        self._require_slide(slide)
        return self.slide_layouts[slide]

    def define_layout(self, layout: Layout, at: int | None = None) -> None:
        """Keep a new layout, at place ``at`` (the end by default); ``ValueError`` if its id is taken."""
        if layout.id in self.slides:
            raise ValueError(f"{layout.id!r} is a slide, not a layout")
        self.layouts.add(layout, at)
        self.open_holder(layout.id)

    def change_layout(self, layout: str, **changes: object) -> Layout:
        """Change what a layout says about itself (its name, whether it is hidden, whether it still waits for a
        name); returns the layout as it was."""
        return self.layouts.change(layout, **changes)

    def move_layout(self, layout: str, at: int) -> int:
        """Put a layout at place ``at`` in the list; returns the place it had."""
        return self.layouts.move(layout, at)

    def objects_drawn_on(self, slide: str) -> list[SlideObject]:
        """Everything that is drawn on a slide, bottom first: what its layout shows beneath it, then its own objects,
        except an empty box in a placeholder, which is only a place to fill (E10.4)."""
        own = [obj for obj in self.objects_on(slide) if not (self.placeholder_of(obj) and is_empty(obj))]
        return [*self.layout_objects_of(slide), *own]

    def layouts_to_choose(self) -> list[Layout]:
        """The layouts a person chooses a slide's layout from, in order: all but the hidden ones."""
        return [layout for layout in self.layouts if not layout.hidden]

    def layout_objects_of(self, slide: str) -> list[SlideObject]:
        """What the layout of a slide shows beneath the slide's own objects, bottom first: everything on the layout but
        its placeholders, which are only places to fill (E10.4)."""
        return [obj for obj in self.objects_on(self.layout_of(slide)) if not obj.anchor.purpose]

    def slides_following(self, layout: str) -> list[str]:
        """The slides that follow a layout, in the order of the deck."""
        return [slide for slide in self.order if self.slide_layouts[slide] == layout]

    def remove_layout(self, layout: str) -> tuple[Layout, int]:
        """Take a layout away that no slide follows; returns it and the place it had. The basic layout stays."""
        if layout == BASIC_LAYOUT:
            raise Refusal("the basic layout stays")
        if layout in self.slide_layouts.values():
            raise Refusal("a slide still follows this layout")
        removed = self.layouts[layout]
        place = self.layouts.ids().index(layout)
        self.close_holder(layout)
        self.layouts.remove(layout)
        return removed, place

    def put_slide_on_layout(
        self,
        slide: str,
        layout: str,
        rebind: Mapping[str, str] | None = None,
        frames: Mapping[str, tuple] | None = None,
    ) -> SlideLayoutWas:
        """Make a slide follow a layout, bind the objects named in ``rebind`` to the placeholders it names (``""``:
        to none), and put the objects named in ``frames`` back to the place, size, turn and look they are given there.
        Returns what undoing it needs: the layout the slide followed, what bound the objects that were bound or are
        named, and the frames of the objects that now take a placeholder's. A placeholder of another layout is allowed:
        the binding is then inert (D1531), and it is what undoing a change from such a binding gives back.
        ``ValueError`` if there is no such slide or layout, an object is not on the slide, or a placeholder is none."""
        old = self.layout_of(slide)
        self.layouts.require(layout)
        rebind = rebind or {}
        on_slide = {obj.id: obj for obj in self.objects_on(slide)}
        for object_id, placeholder in rebind.items():
            if object_id not in on_slide:
                raise ValueError(f"{object_id!r} is not on slide {slide!r}")
            if placeholder and (
                placeholder not in self.objects or self.objects[placeholder].holder not in self.layouts
            ):
                raise ValueError(f"{placeholder!r} is not a placeholder of a layout")
        for object_id in frames or {}:
            if object_id not in on_slide:
                raise ValueError(f"{object_id!r} is not on slide {slide!r}")
        before = {
            object_id: obj.anchor.bound_to_placeholder
            for object_id, obj in on_slide.items()
            if obj.anchor.bound_to_placeholder or object_id in rebind
        }
        taken = {object_id: _own_place(on_slide[object_id]) for object_id, placeholder in rebind.items() if placeholder}
        self.slide_layouts[slide] = layout
        self._slides_on_new_layouts.add(slide)
        for object_id, placeholder in rebind.items():
            obj = on_slide[object_id]
            self.objects[object_id] = replace(obj, anchor=replace(obj.anchor, bound_to_placeholder=placeholder))
        for object_id, place in (frames or {}).items():
            self.objects[object_id] = _placed(self.objects[object_id], place)
        return SlideLayoutWas(old, before, taken)

    # -- slides ----------------------------------------------------------------
    def insert_slide(
        self,
        slide: str,
        at: int | None = None,
        notes: str = "",
        seconds: int | None = None,
        name: str = "",
        description: str = "",
        layout: str = "",
    ) -> None:
        """Add a slide at position ``at`` (the end by default), optionally with its notes, planned time, name,
        description and layout (which is how undoing the removal of a slide gives them back). Without a layout it
        follows the one of the slide before it."""
        self.slides.check_new(slide)
        if slide in self.layouts:
            raise ValueError(f"{slide!r} is a layout, not a slide")
        if at is not None and not 0 <= at <= len(self.order):
            raise ValueError(f"there is no place {at} among {len(self.order)} slides")
        notes = _checked_notes(notes)
        if seconds is not None:
            _check_seconds(seconds)
        self.check_thing_name(slide, name)
        self.slides.add(Slide(slide, name, description))
        place = len(self.order) if at is None else at
        self.slide_layouts[slide] = self._layout_for_new_slide(layout, place)
        self.order.insert(place, slide)
        self.open_holder(slide)
        self._slide_order += 1
        if notes:
            self.notes[slide] = notes
        if seconds is not None:
            self.times[slide] = seconds

    def _layout_for_new_slide(self, layout: str, place: int) -> str:
        """The layout a slide added at ``place`` follows: the one asked for, else the one of the slide before it."""
        if layout:
            self.layouts.require(layout)
            return layout
        return self.slide_layouts[self.order[place - 1]] if place else self.layouts.first_visible().id

    def delete_slide(self, slide: str) -> int:
        """Remove an empty slide; returns the place it had."""
        if slide not in self.order:
            raise ValueError(f"unknown slide {slide!r}")
        if self.stack_of(slide):
            raise ValueError(f"slide {slide!r} still has objects; remove them first")
        place = self.order.index(slide)
        del self.order[place]
        self.close_holder(slide)
        self.slides.remove(slide)
        del self.slide_layouts[slide]
        self._slide_order += 1
        self.notes.pop(slide, None)
        self.times.pop(slide, None)
        return place

    # -- the shared text structure (step C): the presentation as a ParagraphHost ---------
    def reading_order(self) -> Iterator[Placed]:
        """The words of the objects in the order they are read: slide by slide, on each slide in stacking order,
        bottom first (as PowerPoint reads a slide to a screen reader; the owner's decision of 2026-11-16). The place a
        reader finds them at is the slide's number."""
        for number, slide in enumerate(self.order, start=1):
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
        """Keep the copies on slides equal to their layouts (E10.4, D1530), and tell the clients which labels changed:
        a text box taken away may renumber every one after it."""
        self._settle_bound_copies(ctx)
        self.structure.settle(ctx)

    def _settle_bound_copies(self, ctx) -> None:
        """An object bound to a placeholder keeps the place, size, turn and look of that placeholder as its own, so that
        the slide stands alone; the layout is the truth, and what differs here is repaired. A binding to a placeholder
        that is not on the layout of the slide (gone, or of another layout) does nothing and is not touched, so that
        undoing what removed the placeholder binds the object again. It never refuses, and it is derived from the state
        alone, so undo and replay come to the same result."""
        table = self.objects
        to_look_at = {key for key in table.touched if key in table and table[key].anchor.bound_to_placeholder}
        for key in table.touched:  # a placeholder that was written: whatever follows it
            to_look_at |= table.followers.get(key, set())
        for slide in self._slides_on_new_layouts & set(self.order):
            to_look_at |= {obj.id for obj in self.objects_on(slide) if obj.anchor.bound_to_placeholder}
        repaired: dict[str, list[SlideObject]] = {}
        for key in sorted(to_look_at):
            obj = table[key]
            if (placeholder := self.placeholder_of(obj)) is not None and (now := _bound_to(obj, placeholder)) != obj:
                table[key] = now
                repaired.setdefault(obj.holder, []).append(now)
        table.touched.clear()
        self._slides_on_new_layouts.clear()
        for slide, objects in repaired.items():
            ctx.emit(self.objects_changed(slide, changed=tuple(objects)))

    def placeholder_of(self, obj: SlideObject) -> SlideObject | None:
        """The placeholder an object is bound to, if it is one of the layout the slide of the object follows."""
        placeholder = self.objects.get(obj.anchor.bound_to_placeholder)
        if placeholder is None or placeholder.holder != self.slide_layouts.get(obj.holder):
            return None
        return placeholder

    # -- names (D550) ------------------------------------------------------------
    def named_things(self):
        """The objects with names, then the slides with names: one namespace."""
        yield from super().named_things()
        for slide in self.order:
            if name := self.slides[slide].name:
                yield "slide", slide, name

    def unnamed_things(self):
        """The slides without a name, then the objects without one."""
        for slide in self.order:
            if not self.slides[slide].name:
                yield "slide", slide
        yield from super().unnamed_things()

    def thing_name(self, thing_id: str) -> str:
        """The name of an object or a slide, ``""`` if it has none; ``ValueError`` if there is neither."""
        if thing_id in self.order:
            return self.slides[thing_id].name
        return super().thing_name(thing_id)

    def set_thing_name(self, thing_id: str, name: str) -> str:
        """Name an object or a slide; returns the name it had."""
        if thing_id not in self.order:
            return super().set_thing_name(thing_id, name)
        return self.slides.rename(thing_id, name)

    def thing_description(self, thing_id: str) -> str:
        """What is written about an object or a slide, ``""`` if nothing; ``ValueError`` if there is neither."""
        if thing_id not in self.order:
            return super().thing_description(thing_id)
        return self.slides[thing_id].description

    def set_thing_description(self, thing_id: str, description: str) -> str:
        """Write something about a slide (``""``: nothing); returns what was written. An object is described by
        :class:`~claudia_core.DescribeObject`."""
        if thing_id not in self.order:
            return super().set_thing_description(thing_id, description)
        return self.slides.describe(thing_id, description)

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
        if slide not in self.order:
            raise ValueError(f"unknown slide {slide!r}")
