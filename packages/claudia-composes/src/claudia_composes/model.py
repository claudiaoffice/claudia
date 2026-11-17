"""The text model: named paragraphs, who wrote each stretch, and the AI's open suggestions (E9.1, D62, D63).

A document is a list of paragraphs. Each has an id that is never reused, a style (by name: you mark text by what it is
for, D62), its text and the runs that say who wrote what. Suggestions are proposals anchored to a stretch of text; they
are state of the document like the paragraphs, but they change no text until somebody accepts them.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import ClassVar, Self

from claudia_core import (
    SLOTS,
    Command,
    CommandRegistry,
    Context,
    DocumentModel,
    Field,
    Generated,
    Label,
    ListBook,
    ListItem,
    ObjectBody,
    ObjectModel,
    ObjectSet,
    Palette,
    Paragraph,
    Placed,
    Region,
    Run,
    SchemeBook,
    SetLanguage,
    StyleBook,
    StyleDef,
    TextStructure,
    VisualObject,
    builtin_palette,
    fields_before,
    fits,
    insert_runs,
    new_registry,
    slice_runs,
)

from .anchors import BlockAnchor
from .events import BlockGenerated, FieldsPut, ItemChanged, SuggestionsChanged, TextChanged
from .page import PageSetup
from .region import TextRange
from .spans import TextCommand

DEFAULT_STYLE = "body"
FIRST_BLOCK = "b1"
_NUMBERED = re.compile(r"[bs](\d+)")


_SANS = "Inter, system-ui, 'Segoe UI', sans-serif"
_SERIF = "Fraunces, Georgia, serif"
# Colours are roles of the document's palette, never literals (D200): a document holds no hex of its own,
# so replacing its palette really does recolour it. ``@text/82`` is that role at 82% opacity, which is how
# the softer inks of a quote or a remark keep following the ink they are a shade of.
_INK = "@text"


def _style(style_id: str, name: str, purpose: str, *, kind: str = "paragraph", **css: str) -> StyleDef:
    # A paragraph style is based on Body text, so a change to Body text reaches it (D73); a box or outline style is
    # a root of its own, because a style and its parent are always of the same kind (D305).
    parent = DEFAULT_STYLE if kind == "paragraph" and style_id != DEFAULT_STYLE else None
    return StyleDef(style_id, name, purpose, parent, css, kind=kind)


def _at_level(level: int, style: StyleDef) -> StyleDef:
    """``style`` giving the heading level ``level`` (E9.22): 0 the title, 1 to 6 the sections."""
    return replace(style, heading_level=level)


def _heading(level: int, purpose: str, size: str, line_height: str, top: str, bottom: str, **extra: str) -> StyleDef:
    """Heading ``level``: the serif of the headings, a size that falls with the level, space above and below."""
    css = {
        "font-family": _SERIF,
        "font-size": size,
        "font-weight": "500",
        "line-height": line_height,
        "margin-top": top,
        "margin-bottom": bottom,
        "hyphens": "manual",
        **extra,
    }
    return _at_level(level, _style(f"heading-{level}", f"Heading {level}", purpose, **css))


def _contents(level: int) -> StyleDef:
    """Contents ``level``: an entry of a table of contents for a heading of that level, moved in by its level."""
    css = {"margin-bottom": "0.2em", "hyphens": "manual", "margin-left": f"{(level - 1) * 1.5:g}em"}
    if level == 1:
        css["font-weight"] = "600"
    return _style(f"contents-{level}", f"Contents {level}", f"an entry of a table of contents at level {level}", **css)


#: The styles every text starts with. The paragraph styles are all based on Body text (D73): a change to Body text
#: reaches the others where they have not set the property themselves. The outline and the picture's box are styles
#: of their own kinds (D305). They are made by the model, not by commands, so they are in every log's past.
BUILTIN_STYLES: tuple[StyleDef, ...] = (
    _style(
        "body",
        "Body text",
        "running text",
        **{
            "font-family": _SANS,
            "font-size": "12pt",
            "line-height": "1.75",
            "color": _INK,
            "text-align": "left",
            "margin-top": "0",
            "margin-bottom": "0.9em",
            "hyphens": "auto",
        },
    ),
    _at_level(
        0,
        _style(
            "title",
            "Title",
            "names the document",
            **{
                "font-family": _SERIF,
                "font-size": "30pt",
                "font-weight": "500",
                "line-height": "1.15",
                "letter-spacing": "-0.01em",
                "margin-bottom": "0.5em",
                "hyphens": "manual",
            },
        ),
    ),
    _heading(1, "a section", "19pt", "1.25", "1.6em", "0.5em"),
    _heading(2, "a subsection", "14.5pt", "1.3", "1.3em", "0.4em"),
    _heading(3, "a part of a subsection", "13pt", "1.35", "1.2em", "0.35em"),
    _heading(4, "a heading at the fourth level", "12.5pt", "1.4", "1.1em", "0.3em", **{"font-weight": "600"}),
    _heading(5, "a heading at the fifth level", "12pt", "1.45", "1em", "0.3em", **{"font-weight": "600"}),
    _heading(6, "a heading at the sixth level", "12pt", "1.45", "1em", "0.3em", **{"font-style": "italic"}),
    _style(
        "quote",
        "Quote",
        "words of someone else",
        **{
            "font-family": _SERIF,
            "font-style": "italic",
            "font-size": "14pt",
            "line-height": "1.7",
            "color": "@text/82",
            "border-left": "3px solid @highlight",
            "padding-left": "1.1em",
        },
    ),
    _style(
        "remark",
        "Remark",
        "a note to the reader or co-author",
        **{
            "font-size": "11pt",
            "line-height": "1.6",
            "color": "@text/78",
            "background-color": "@attention/7",
            "border-left": "3px solid @attention",
            "padding-top": "0.55em",
            "padding-bottom": "0.55em",
            "padding-left": "0.9em",
            "padding-right": "0.9em",
        },
    ),
    # A table of contents (E9.31): the heading above it is the author's words, in Contents Title, which has no heading
    # level, so the table does not list itself; each entry is drawn in Contents <n>, by its heading's level (D306).
    _style(
        "contents-title",
        "Contents Title",
        "the heading above a table of contents; it is not listed in it",
        **{
            "font-family": _SERIF,
            "font-size": "19pt",
            "font-weight": "500",
            "line-height": "1.25",
            "margin-top": "1.6em",
            "margin-bottom": "0.5em",
            "hyphens": "manual",
        },
    ),
    *(_contents(level) for level in range(1, 10)),
    # The object styles, with the same ids in all three apps (E10.16), so that a shape or a picture carried
    # from a slide or a sheet into a text keeps a style that exists here. A shape's background and border are
    # ``fill``/``stroke``/``stroke-width``, not ``background-color``/``border-*`` (D178): a shape is an outline in
    # a 100 by 100 box, not a rectangle, so only the SVG vocabulary can give a circle or a triangle a border. Its
    # outline and its words are two slots, each with a style of its own kind (D304, D310).
    _style(
        "shape-label",
        "Shape label",
        "the words inside a shape floating over the text",
        **{"text-align": "center"},
    ),
    _style(
        "plain-shape",
        "Plain shape",
        "a shape floating over the text, carrying a thought or marking a passage",
        kind="outline",
        **{
            "fill": "@accent/8",
            "stroke": "@accent",
            "stroke-width": "2px",
        },
    ),
    _style(
        "plain-box",
        "Plain box",
        "the box of a text box floating over the text: no background and no border, so only its words show",
        kind="box",
    ),
    _style(
        "plain-image",
        "Plain image",
        "a picture floating over the text; it carries its own colours, so no style properties apply to it",
        kind="box",
    ),
    _style(
        "definition",
        "Definition",
        "says what a term means",
        **{
            "background-color": "@accent/8",
            "border-left": "3px solid @accent",
            "padding-top": "0.5em",
            "padding-bottom": "0.5em",
            "padding-left": "0.9em",
            "padding-right": "0.9em",
        },
    ),
)
_BUILTIN_IDS = frozenset(s.id for s in BUILTIN_STYLES)


def builtin_styles() -> StyleBook:
    """A new style book with the built-in styles."""
    return StyleBook(BUILTIN_STYLES)


def next_style(styles: StyleBook, style_id: str) -> str:
    """The style of the paragraph that starts when a writer ends one in ``style_id`` (Enter at its end): body text
    after a heading, a quote or a remark, and more of the same after body text. A style made by deviating follows the
    built-in style it comes from."""
    root = next(s for s in reversed(styles.chain(style_id)) if s.id in _BUILTIN_IDS)
    return style_id if root.id == DEFAULT_STYLE else DEFAULT_STYLE


#: One paragraph of a document. Since E10.17 this is ``claudia_core``'s :class:`~claudia_core.Paragraph`, the
#: same entity a creates text box and a shape's label carry (D181) — the name ``Block`` stays because that is
#: what this app has always called it, and because a paragraph in a flowing document is a block in a way one
#: inside a shape is not: only these can be split and joined.
#:
#: It is immutable, so the model replaces a paragraph in :attr:`TextModel.blocks` rather than editing it in
#: place (``_put``, below). The reason is undo: a command builds its own inverse from the state it found, and a
#: paragraph changed under it would hand that inverse the new text.
#: (a plain alias, not a `type` statement: Block(...) is called as a constructor)
Block = Paragraph


@dataclass(frozen=True)
class Suggestion:
    """A proposal: replace ``original`` (the text at ``anchor`` when it was made) by ``replacement``.

    ``replacement`` is ``None`` for a remark, which suggests no change. ``state`` is ``open``, ``accepted``,
    ``rejected``, ``dismissed`` (a remark) or ``withdrawn`` (the proposal was undone and does not exist any more)."""

    id: str
    author: str | None
    anchor: TextRange
    original: str
    replacement: str | None
    reason: str
    state: str = "open"


#: One floating thing in a text: a text box, a shape or an image, hanging from a place in a paragraph.
type TextObject = VisualObject[BlockAnchor]


class TextModel(DocumentModel, ObjectModel[BlockAnchor]):
    """The paragraphs of a document, its suggestions and the objects floating over it."""

    app: ClassVar[str] = "composes"
    # 4: a text also carries objects, images and shapes (E10.16)
    # 5: the text carries its own colour palette (D200)
    # 6: the text says which page it is printed on (D904)
    # 7: the text says which language it is written in (D915)
    # 8: paragraphs may be items of lists, which the text holds in a book of its own (E9.21)
    # 11: paragraphs may have names, by their id (D554)
    # 8: object bodies without a description; 9: no rendered containers; 12: styles carry heading levels (E9.22)
    # 13: the text holds its numbering schemes; styles may name a list that numbers them (E9.22)
    # 14: a paragraph may be generated (a table of contents, E9.31)
    state_schema: ClassVar[int] = 14
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(
        self,
        blocks: list[Block] | None = None,
        styles: StyleBook | None = None,
        palette: Palette | None = None,
        page: PageSetup | None = None,
        language: str | None = None,
        lists: ListBook | None = None,
        schemes: SchemeBook | None = None,
    ):
        super().__init__()
        self.blocks: list[Block] = blocks if blocks is not None else [Block(FIRST_BLOCK, DEFAULT_STYLE)]
        self.styles: StyleBook = styles if styles is not None else builtin_styles()
        #: The colours of this document, by what they mean. Part of the document, so it looks the same on
        #: whichever server it is opened (D200); the built-in styles are written entirely in terms of it.
        self.palette: Palette = palette if palette is not None else builtin_palette()
        #: The page the text is laid out on for the print preview and PDF (D904); laid out in the client (D901).
        self.page: PageSetup = page if page is not None else PageSetup()
        #: The language of the text, a BCP 47 tag, or ``None`` when it is not known (D915): what it is hyphenated by.
        self.language: str | None = language
        #: The lists the items of the text belong to (E9.21); what a list is, not which paragraphs are in it.
        self.lists: ListBook = lists if lists is not None else ListBook()
        #: How the lists are drawn (E9.22), part of the document; the built-in schemes to start with.
        self.schemes: SchemeBook = schemes if schemes is not None else SchemeBook()
        self.suggestions: dict[str, Suggestion] = {}
        #: The names of paragraphs, by id (D554). A paragraph id is never given twice, so a name stays with its
        #: paragraph through every edit; one whose paragraph was joined away is kept, unused, until undo brings the
        #: paragraph back.
        self.block_names: dict[str, str] = {}
        self._last = {"b": _highest(b.id for b in self.blocks), "s": 0}
        for block in self.blocks:
            self.open_container(block.id)
        #: Changes of the structure that numbering depends on (an item set, a paragraph split or joined). Typing
        #: does not count, so it never makes the labels be worked out again.
        self._structure = 0
        #: What is derived from the paragraphs' structure, the same in every app (step C). The text is its host.
        self.structure = TextStructure(self)

    # -- lifecycle ---------------------------------------------------------------
    @classmethod
    def empty(cls) -> Self:
        """A document with one empty body paragraph."""
        return cls()

    @classmethod
    def setup_commands(cls, language: str | None) -> tuple[Command, ...]:
        """A new text starts in the language of its maker's interface (D915), set by the server when it creates
        the document rather than by her client as her own first step (UX-33)."""
        return () if language is None else (SetLanguage(language),)

    def serialize(self) -> dict:
        """The state as plain data (a snapshot is a cache of it)."""
        return {
            "blocks": [b.to_data() for b in self.blocks],
            "styles": self.styles.to_data(),
            "palette": self.palette.to_data(),
            "page": self.page.to_data(),
            "language": self.language,
            "lists": self.lists.to_data(),
            "schemes": self.schemes.to_data(),
            "suggestions": [self.suggestion_data(s, with_state=True) for s in self.suggestions.values()],
            "shapes": self.shapes_to_data(),
            "images": self.images_to_data(),
            "objects": self.objects_to_data(),
            "renderings": self.renderings_to_data(),
            "names": dict(self.block_names),
            "last": dict(self._last),
        }

    @classmethod
    def restore(cls, state: dict) -> Self:
        """Build a model from ``serialize()``'s output; the older shape (a list of strings) is understood too."""
        raw = state["blocks"]
        if raw and isinstance(raw[0], str):  # state schema 1: the stub, which could not hold more than strings
            blocks = [Block(f"b{i}", DEFAULT_STYLE, t, (Run(len(t), None),) if t else ()) for i, t in enumerate(raw, 1)]
            return cls(blocks)
        styles = StyleBook.from_data(state["styles"]) if "styles" in state else None  # schema 2 had the built-in ones
        blocks = [Block.from_data(b) for b in raw]
        palette = Palette.from_data(state["palette"]) if "palette" in state else None  # schema 4 and earlier
        page = PageSetup.from_data(state["page"]) if "page" in state else None  # schema 5 and earlier: A4
        lists = ListBook.from_data(state["lists"]) if "lists" in state else None  # schema 7 and earlier
        schemes = SchemeBook.from_data(state.get("schemes"))  # schema 12 and earlier: the built-in ones
        # schema 6 and earlier: no language
        model = cls(blocks, styles, palette, page, state.get("language"), lists, schemes)
        for item in state.get("suggestions", []):
            model.suggestions[item["id"]] = _suggestion_from_data(item)
        model.restore_objects(  # schema 3 and earlier had no objects
            state.get("objects", ()), state.get("images", ()), state.get("shapes", ()), (), state.get("renderings", ())
        )
        model.block_names = dict(state.get("names", {}))  # schema 10 and earlier: no paragraph had a name
        model._last = dict(state.get("last", model._last))
        model.structure = TextStructure(model)  # with the objects in: the clients learn the labels with the document
        return model

    def region_from_data(self, data: dict) -> Region:
        """Read a region a client sent: a stretch of text, or a selection of floating objects."""
        if data.get("kind") == ObjectSet.kind:
            return ObjectSet.from_data(data)
        if data.get("kind") != TextRange.kind:
            raise ValueError(f"composes knows text regions and object selections, not {data.get('kind')!r}")
        block, start, end = data["block"], data["start"], data["end"]
        if not (isinstance(block, str) and isinstance(start, int) and isinstance(end, int) and 0 <= start <= end):
            raise ValueError("a text region names a paragraph and 0 <= start <= end")
        return TextRange(block, start, end)

    # -- the object seam ---------------------------------------------------------
    def containers(self) -> list[str]:
        """The paragraphs objects may hang from, in order."""
        return [block.id for block in self.blocks]

    def anchor_from_data(self, data: dict) -> BlockAnchor:
        """Read a block anchor; ``ValueError`` if the data is not one."""
        return BlockAnchor.from_data(data)

    def check_anchor(self, anchor: BlockAnchor, body: ObjectBody) -> None:
        """An object hangs from a character of its paragraph, so the offset must lie inside that paragraph.

        A text has no edge an object could fall off, unlike a slide: only the offset and how far it floats from there
        are checked, never the size."""
        if not 0 <= anchor.offset <= len(self.block(anchor.block).text):
            raise IndexError("an object must hang from a place inside its paragraph")
        anchor.check_floating()

    def move_objects(self, command: TextCommand) -> list[dict]:
        """Let the objects follow ``command`` (see ``claudia_composes.anchors``); returns the ones that moved,
        as sent to clients. A paragraph that was joined away takes its objects with it to the surviving one."""
        moved: list[dict] = []
        for obj in list(self.objects.values()):
            span = command.follow(obj.anchor.span)
            if span == obj.anchor.span:
                continue
            placed = obj.anchor.followed(span)
            was, now = obj.container, placed.container
            self.objects[obj.id] = replace(obj, anchor=placed)
            if was != now:  # the paragraph went away, or the anchor crossed into another one
                self._stack.setdefault(now, []).append(obj.id)
                if obj.id in self._stack.get(was, []):
                    self._stack[was].remove(obj.id)
                self.paragraph_order += 1
            moved.append(self.objects[obj.id].to_data())
        return moved

    # -- names (D550, D554) ---------------------------------------------------------
    def heading_level(self, block: Block) -> int | None:
        """The heading level of a paragraph (E9.22): 0 the title, 1 to 9 a section, ``None`` no heading. Its style
        decides, through :meth:`~claudia_core.StyleBook.heading_level`; a style the text lacks gives none."""
        try:
            return self.styles.heading_level(block.style)
        except (KeyError, ValueError):
            return None

    def block_kind(self, block: Block) -> str:
        """What a paragraph is, as a thing: ``heading`` (its style has a heading level), ``item`` (of a list), or
        ``paragraph``."""
        if self.heading_level(block) is not None:
            return "heading"
        return "item" if block.item is not None else "paragraph"

    def named_things(self):
        """The objects with names, then the paragraphs with names, in the order of the text: one namespace."""
        yield from super().named_things()
        for block in self.blocks:
            name = self.block_names.get(block.id)
            if name:
                yield self.block_kind(block), block.id, name

    # (``unnamed_things`` stays the objects': paragraphs are named one at a time, when somebody points at one.)

    def _has_block(self, block_id: str) -> bool:
        return any(block.id == block_id for block in self.blocks)

    def has_thing(self, thing_id: str) -> bool:
        """Is there an object or a paragraph with this id, named or not?"""
        return self._has_block(thing_id) or super().has_thing(thing_id)

    def thing_name(self, thing_id: str) -> str:
        """The name of a paragraph or an object, ``""`` if it has none; ``ValueError`` if there is neither."""
        if self._has_block(thing_id):
            return self.block_names.get(thing_id, "")
        return super().thing_name(thing_id)

    def set_thing_name(self, thing_id: str, name: str) -> str:
        """Name a paragraph or an object (``""``: no name); returns the name it had."""
        if not self._has_block(thing_id):
            return super().set_thing_name(thing_id, name)
        old = self.block_names.get(thing_id, "")
        if name:
            self.block_names[thing_id] = name
        else:
            self.block_names.pop(thing_id, None)
        return old

    # -- reading -----------------------------------------------------------------
    def block(self, block_id: str) -> Block:
        """The paragraph with this id; ``KeyError`` if there is none."""
        for block in self.blocks:
            if block.id == block_id:
                return block
        raise KeyError(f"no paragraph {block_id!r}")

    def index_of(self, block_id: str) -> int:
        """The place of the paragraph in the document; ``KeyError`` if there is none."""
        self.block(block_id)
        return next(i for i, b in enumerate(self.blocks) if b.id == block_id)

    def fresh_ids(self, count: int) -> list[str]:
        """``count`` ids for new paragraphs. Ids are never used twice, not even after a join, so undo can bring one
        back."""
        return [f"b{self._last['b'] + n}" for n in range(1, count + 1)]

    def fresh_id(self) -> str:
        """An id for a new paragraph (see ``fresh_ids``)."""
        return self.fresh_ids(1)[0]

    def style_in_use(self, style_id: str) -> bool:
        """Does any paragraph, or any object in the text (itself or its words), have this style? (Asked by the
        style commands before they take a style back.)"""
        return any(b.style == style_id for b in self.blocks) or ObjectModel.style_in_use(self, style_id)

    def list_in_use(self, list_id: str) -> bool:
        """Is any paragraph, or the words of any object, an item of this list? (Asked by the list commands before
        they take a list back.)"""
        return any(b.item is not None and b.item.list == list_id for b in self.blocks) or self.object_list_in_use(
            list_id
        )

    # -- list items of any paragraph (claudia_core.ItemHost) ------------------------------------
    def item_of(self, paragraph_id: str) -> ListItem | None:
        """The item of a paragraph of the text or of the words of an object."""
        if paragraph_id in self.objects:
            return self.object_item(paragraph_id)
        return self.block(paragraph_id).item

    def put_item(self, paragraph_id: str, item: ListItem | None) -> object:
        """Make a paragraph, or an object's words, an item; the event that tells the clients."""
        if paragraph_id in self.objects:
            return self.put_object_item(paragraph_id, item)
        self.set_item(paragraph_id, item)
        return ItemChanged(paragraph_id, item)

    # -- typing (claudia_core.TypingHost) -----------------------------------------------------------
    def insert_text(
        self, paragraph_id: str, offset: int, text: str, runs: list[Run], fields: tuple[Field, ...] = ()
    ) -> tuple[object, ...]:
        """Type into a paragraph of the text or the words of a floating object; the events that tell the clients."""
        if paragraph_id in self.objects:
            return (self.insert_object_text(paragraph_id, offset, text, runs, fields),)
        self.insert(paragraph_id, offset, text, runs, fields)
        if not text:
            return ()
        changed = TextChanged(paragraph_id, offset, 0, text, tuple(runs))
        return (changed, FieldsPut(paragraph_id, self.block(paragraph_id).fields)) if fields else (changed,)

    def remove_text(
        self, paragraph_id: str, start: int, end: int
    ) -> tuple[str, list[Run], tuple[Field, ...], tuple[object, ...]]:
        """Cut characters out of a paragraph of the text or the words of a floating object."""
        if paragraph_id in self.objects:
            text, runs, fields, event = self.remove_object_text(paragraph_id, start, end)
            return text, runs, fields, (event,)
        text, runs, fields = self.remove(paragraph_id, start, end)
        events: tuple[object, ...] = (TextChanged(paragraph_id, start, end - start, ""),) if end > start else ()
        if fields:
            events = (*events, FieldsPut(paragraph_id, self.block(paragraph_id).fields))
        return text, runs, fields, events

    # -- fields (claudia_core.FieldHost, step H) ----------------------------------------------------------
    def fields_of(self, paragraph_id: str) -> tuple[Field, ...]:
        """The fields of a paragraph of the text or in the words of a floating object."""
        if paragraph_id in self.objects:
            return self.object_fields(paragraph_id)
        return self.block(paragraph_id).fields

    def put_fields(self, paragraph_id: str, fields: tuple[Field, ...]) -> tuple[object, ...]:
        """Give a paragraph other fields at its U+FFFC; the event that tells the clients."""
        if paragraph_id in self.objects:
            return (self.put_object_fields(paragraph_id, fields),)
        self._put(self.block(paragraph_id).with_fields(fields))
        return (FieldsPut(paragraph_id, fields),)

    def text_regions(self, paragraph_id: str, start: int, end: int) -> tuple[Region, ...]:
        """A stretch of a paragraph of the text, or the floating object whose words change."""
        if paragraph_id in self.objects:
            return self.selection_of(paragraph_id)
        return (TextRange(paragraph_id, start, end),)

    def text_moved(self, command: TextCommand) -> tuple[object, ...]:
        """Let the open suggestions and the floating objects follow a text command (see
        :mod:`claudia_composes.anchors` for why an object's anchor follows the text here, where a sheet's is
        deliberately frozen); the events for those that moved."""
        events: list[object] = []
        moved = self.move_suggestions(command)
        if moved:
            events.append(SuggestionsChanged(tuple(moved)))
        containers = dict.fromkeys(obj["anchor"]["container"] for obj in self.move_objects(command))
        events.extend(self.objects_changed(c, changed=tuple(self.objects_on(c))) for c in containers)
        return tuple(events)

    # -- generated paragraphs (claudia_core.GeneratedHost) ----------------------------------------
    def generated_of(self, paragraph_id: str) -> Generated | None:
        """The options of a table of contents, a paragraph of the text or the words of an object."""
        if paragraph_id in self.objects:
            return self.object_generated(paragraph_id)
        return self.block(paragraph_id).generated

    def put_generated(self, paragraph_id: str, generated: Generated | None) -> object:
        """Make an empty paragraph (or an object's words) a table of contents, or plain again; the event that tells
        the clients."""
        if paragraph_id in self.objects:
            return self.put_object_generated(paragraph_id, generated)
        self._put(self.block(paragraph_id).with_generated(generated))
        self._structure += 1
        return BlockGenerated(paragraph_id, generated)

    def item_regions(self, paragraph_id: str) -> tuple[Region, ...]:
        """A paragraph's whole text, or the object; a paragraph that is not (yet) there holds its first character
        (the inverse of a join sets the item of the paragraph it splits off)."""
        if paragraph_id in self.objects:
            return self.selection_of(paragraph_id)
        block = next((b for b in self.blocks if b.id == paragraph_id), None)
        return (TextRange(paragraph_id, 0, max(1, 0 if block is None else len(block.text))),)

    # -- the shared text structure (step C): the text as a ParagraphHost ---------------------
    def reading_order(self) -> Iterator[Placed]:
        """The paragraphs in the order they are read: each paragraph of the text, then the words of the objects that
        hang from it, in stacking order. Only the text's own paragraphs are its main text."""
        for block in self.blocks:
            yield Placed(block, block.id, True, None)
            for obj in self.objects_on(block.id):
                if obj.body.paragraph is not None:
                    yield Placed(obj.body.paragraph, block.id, False, None)

    @property
    def structure_version(self) -> tuple[int, int]:
        """Changes when a paragraph was split, joined or made an item, or an object came, went or moved."""
        return (self._structure, self.paragraph_order)

    def labels(self) -> dict[str, Label]:
        """The marker of every list item, by paragraph id: the text's own paragraphs and the words of its objects
        (:class:`claudia_core.TextStructure`). Shared with the structure, so callers must not change it."""
        return self.structure.labels()

    def settle(self, ctx: Context) -> None:
        """Tell the clients which labels changed: the numbering of a list is derived, so a command that only set
        one item may have renumbered a hundred others."""
        self.structure.settle(ctx)

    def style_uses(self) -> dict[str, int]:
        """How many paragraphs have each style that is in use."""
        return dict(Counter(b.style for b in self.blocks))

    def fresh_suggestion_id(self) -> str:
        """An id for a new suggestion."""
        return f"s{self._last['s'] + 1}"

    def suggestion(self, suggestion_id: str) -> Suggestion:
        """The suggestion with this id; ``KeyError`` if there is none."""
        try:
            return self.suggestions[suggestion_id]
        except KeyError:
            raise KeyError(f"no suggestion {suggestion_id!r}") from None

    def is_outdated(self, suggestion: Suggestion) -> bool:
        """Has the text under a suggestion changed since it was made? It then cannot be accepted any more."""
        a = suggestion.anchor
        try:
            current = self.block(a.block).text[a.start : a.end]
        except KeyError:
            return True
        return current != suggestion.original

    def suggestion_data(self, suggestion: Suggestion, *, with_state: bool = False) -> dict:
        """A suggestion as sent to clients (``with_state`` also keeps the ones that are over, for snapshots)."""
        a = suggestion.anchor
        data = {
            "id": suggestion.id,
            "author": suggestion.author,
            "block": a.block,
            "start": a.start,
            "end": a.end,
            "original": suggestion.original,
            "replacement": suggestion.replacement,
            "reason": suggestion.reason,
            "state": suggestion.state,
        }
        if not with_state:
            data["outdated"] = self.is_outdated(suggestion)
        return data

    def visible_suggestions(self) -> list[dict]:
        """The suggestions people may still act on, in the order they were made."""
        return [self.suggestion_data(s) for s in self.suggestions.values() if s.state == "open"]

    # -- changing text (used by the commands) ------------------------------------
    def restyle(self, block_id: str, style: str) -> None:
        """Put a paragraph under another style (a paragraph is immutable, so this replaces it)."""
        self._put(self.block(block_id).with_style(style))

    def set_item(self, block_id: str, item: ListItem | None) -> None:
        """Make a paragraph an item of a list, or (``None``) take it out of its list. The list must exist."""
        if item is not None:
            item.check()
            if item.list not in self.lists:
                raise ValueError(f"no list {item.list!r}")
        self._put(self.block(block_id).with_item(item))
        self._structure += 1

    def _put(self, block: Block) -> None:
        """Swap a changed paragraph into place. A paragraph is immutable (D181), so every edit below builds a new
        one and puts it where the old one was."""
        self.blocks[self.index_of(block.id)] = block

    def insert(self, block_id: str, offset: int, text: str, runs: list[Run], fields: tuple[Field, ...] = ()) -> None:
        """Put ``text`` into a paragraph at ``offset``; ``runs`` say who wrote it, ``fields`` are its U+FFFC's."""
        block = self.block(block_id)
        if block.generated is not None:
            raise ValueError("a table of contents takes no typing: its entries come from the headings")
        self._put(block.typed(offset, text, runs, fields))

    def remove(self, block_id: str, start: int, end: int) -> tuple[str, list[Run], tuple[Field, ...]]:
        """Cut ``start <= i < end`` out of a paragraph; returns what was cut, with its runs and fields."""
        kept, text, runs, fields = self.block(block_id).cut(start, end)
        self._put(kept)
        return text, runs, fields

    def split(self, block_id: str, offset: int, new_id: str, style: str) -> None:
        """Cut a paragraph at ``offset``; the rest becomes the paragraph ``new_id`` right behind it, in ``style``
        and, if the paragraph is a list item, an item of the same list at the same level."""
        block = self.block(block_id)
        if not 0 <= offset <= len(block.text):
            raise IndexError("split outside the text")
        if any(b.id == new_id for b in self.blocks):
            raise ValueError(f"the paragraph {new_id!r} exists already")
        self.check_style(style)
        at = fields_before(block.text, offset)
        rest = Block(
            new_id,
            style,
            block.text[offset:],
            tuple(slice_runs(block.runs, offset, len(block.text))),
            block.item,
            fields=block.fields[at:],
        )
        self._put(
            replace(block.with_text(block.text[:offset], slice_runs(block.runs, 0, offset)), fields=block.fields[:at])
        )
        self.blocks.insert(self.index_of(block_id) + 1, rest)
        self.open_container(new_id)
        self._note_id(new_id)
        self._structure += 1

    def join(self, block_id: str, into: str, at: int) -> Block:
        """Put paragraph ``block_id`` at the end of ``into`` (the one right before it, ``at`` characters long).
        The joined paragraph is the first one's: its style and its place in a list win.

        Returns the paragraph that went away, as it was."""
        first, second = self.block(into), self.block(block_id)
        if self.index_of(block_id) != self.index_of(into) + 1:
            raise ValueError("a paragraph can only be joined to the one right before it")
        if second.generated is not None:
            raise ValueError("a table of contents cannot be joined to a paragraph; remove it instead")
        if first.generated is not None and second.text:
            raise ValueError("text cannot be joined into a table of contents")
        if len(first.text) != at:
            raise ValueError("the paragraph before it is not as long as the command says")
        joined = first.with_text(first.text + second.text, insert_runs(first.runs, at, second.runs))
        self._put(replace(joined, fields=first.fields + second.fields))
        self.carry_objects(block_id, into, shift=at)
        self.blocks.remove(second)
        self.close_container(block_id)
        self._structure += 1
        return second

    def carry_objects(self, source: str, target: str, *, shift: int) -> None:
        """Move every object of the paragraph ``source`` to ``target``, ``shift`` characters further along.

        Used by :meth:`join`: a paragraph that is joined into the one before it takes its objects with it rather
        than leaving them anchored to something that no longer exists."""
        for object_id in list(self._stack.get(source, ())):
            obj = self.objects[object_id]
            self.objects[object_id] = replace(obj, anchor=obj.anchor.carried_to(target, shift))
            self._stack.setdefault(target, []).append(object_id)
            self._stack[source].remove(object_id)
            self.paragraph_order += 1

    def check_style(self, style: str) -> None:
        """``ValueError`` unless the document has a style with this id that fits a paragraph: a composes paragraph
        is one slot that reads text, paragraph and box, so only a paragraph style fits it (D304, D316)."""
        if style not in self.styles:
            raise ValueError(f"no style {style!r}")
        found = self.styles.get(style)
        if not fits(found.kind, SLOTS.slot("paragraph", "paragraph")):
            raise ValueError(f"“{found.name}” is a {found.kind} style and cannot be put on a paragraph")

    # -- suggestions (used by the commands) --------------------------------------
    def add_suggestion(self, suggestion: Suggestion) -> None:
        """Add a new suggestion."""
        if suggestion.id in self.suggestions:
            raise ValueError(f"the suggestion {suggestion.id!r} exists already")
        a = suggestion.anchor
        if not 0 <= a.start <= a.end <= len(self.block(a.block).text):
            raise IndexError("a suggestion must lie inside the text")
        self.suggestions[suggestion.id] = suggestion
        self._note_id(suggestion.id)

    def put_suggestion(self, suggestion: Suggestion) -> None:
        """Replace a suggestion by a changed version of it."""
        self.suggestions[suggestion.id] = suggestion

    def move_suggestions(self, command: TextCommand) -> list[dict]:
        """Let the open suggestions follow ``command``; returns the ones that moved, as sent to clients."""
        moved = []
        for suggestion in list(self.suggestions.values()):
            if suggestion.state != "open":
                continue
            span = command.follow(suggestion.anchor.span)
            if span != suggestion.anchor.span:
                updated = replace(suggestion, anchor=TextRange(*span))
                self.suggestions[suggestion.id] = updated
                moved.append(self.suggestion_data(updated))
        return moved

    def _note_id(self, ident: str) -> None:
        """Remember numbered ids that were used so that ``fresh_id`` never hands one out twice."""
        found = _NUMBERED.fullmatch(ident)
        if found:
            self._last[ident[0]] = max(self._last[ident[0]], int(found.group(1)))


def _highest(ids) -> int:
    return max((int(m.group(1)) for i in ids if i.startswith("b") and (m := _NUMBERED.fullmatch(i))), default=0)


def _suggestion_from_data(item: dict) -> Suggestion:
    anchor = TextRange(item["block"], item["start"], item["end"])
    return Suggestion(
        item["id"], item["author"], anchor, item["original"], item["replacement"], item["reason"], item["state"]
    )
