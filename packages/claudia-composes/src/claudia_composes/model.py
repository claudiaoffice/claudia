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
    FILLER,
    MAX_THING_NAME,
    SLOTS,
    Command,
    CommandRegistry,
    Context,
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
    Paragraph,
    Placed,
    Region,
    Requirements,
    Run,
    SchemeBook,
    SetLanguage,
    StyleBook,
    StyleDef,
    TableDef,
    TableLook,
    TableRegion,
    TextStructure,
    ThingRenamed,
    VisualObject,
    builtin_palette,
    clean_name,
    distinct_name,
    fields_before,
    fits,
    insert_runs,
    name_key,
    name_problem,
    new_registry,
    parse_entry_id,
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
    return StyleDef(style_id, name, purpose, parent, css, kind=kind, origin="builtin")


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


def _table_style(look: str, role: str, purpose: str, **css: str) -> StyleDef:
    """The style of one role of a table look (D1206): a paragraph style, so that it holds the words and the box of
    the cells of that role in one bundle (D311), based on body text with no space around it."""
    base = {
        "margin-top": "0",
        "margin-bottom": "0",
        "line-height": "1.45",
        "padding-top": "0.3em",
        "padding-bottom": "0.3em",
        "padding-left": "0.6em",
        "padding-right": "0.6em",
    }
    return _style(f"table-{look}-{role}", f"Table {look} {role}", purpose, **{**base, **css})


_HEAVY = "2px solid @text"
_THIN = "1px solid @text/45"
_HAIR = "1px solid @text/20"
_TINT = "@accent/8"
_TABLE_STYLES: tuple[StyleDef, ...] = (
    # Rules: a heavy rule above the header and below the total, a thin one under the header and above the total.
    _table_style(
        "rules",
        "header",
        "the header of a table with rules",
        **{"font-weight": "600", "border-top": _HEAVY, "border-bottom": _THIN},
    ),
    _table_style("rules", "body", "the body of a table with rules"),
    _table_style("rules", "band", "every second row of a table with rules", **{"background-color": _TINT}),
    _table_style(
        "rules",
        "total",
        "the total row of a table with rules",
        **{"font-weight": "600", "border-top": _THIN, "border-bottom": _HEAVY},
    ),
    # Grid: thin rules all round.
    _table_style(
        "grid",
        "header",
        "the header of a gridded table",
        **{
            "font-weight": "600",
            "background-color": _TINT,
            "border-top": _THIN,
            "border-right": _THIN,
            "border-bottom": _THIN,
            "border-left": _THIN,
        },
    ),
    _table_style(
        "grid",
        "body",
        "the body of a gridded table",
        **{"border-top": _THIN, "border-right": _THIN, "border-bottom": _THIN, "border-left": _THIN},
    ),
    _table_style(
        "grid",
        "band",
        "every second row of a gridded table",
        **{
            "background-color": _TINT,
            "border-top": _THIN,
            "border-right": _THIN,
            "border-bottom": _THIN,
            "border-left": _THIN,
        },
    ),
    _table_style(
        "grid",
        "total",
        "the total row of a gridded table",
        **{
            "font-weight": "600",
            "border-top": _THIN,
            "border-right": _THIN,
            "border-bottom": _THIN,
            "border-left": _THIN,
        },
    ),
    # Plain: no rules; the header and the total are bold, the band is a tint.
    _table_style("plain", "header", "the header of a plain table", **{"font-weight": "600"}),
    _table_style("plain", "body", "the body of a plain table"),
    _table_style("plain", "band", "every second row of a plain table", **{"background-color": _TINT}),
    _table_style("plain", "total", "the total row of a plain table", **{"font-weight": "600"}),
)

#: The looks a text starts with (D1206): three named bundles of four role styles. The first is the default.
TABLE_LOOKS: tuple[TableLook, ...] = tuple(
    TableLook(look, name, *(f"table-{look}-{role}" for role in ("header", "body", "band", "total")))
    for look, name in (("rules", "Rules"), ("grid", "Grid"), ("plain", "Plain"))
)
DEFAULT_LOOK = TABLE_LOOKS[0].id
#: The ids of the styles of the built-in looks. A file format that writes a table says their box properties (padding,
#: borders, shading) with the table's cells, not with a paragraph style, so a style-by-style check leaves them out.
TABLE_STYLE_IDS: frozenset[str] = frozenset(style for look in TABLE_LOOKS for style in look.styles())

#: The frame a table's object has; a table is drawn by its look (D1206), the frame only says how big it is.
TABLE_FRAME_STYLE = "plain-box"
TABLE_OBJECT_WIDTH = 480  # CSS pixels: the nominal width of a new table's object (a flow table takes the line)
TABLE_ROW_HEIGHT = 24  # CSS pixels per row of a new table's object, until a client has measured it


def table_body(object_id: str, definition: TableDef, name: str, *, width: int | None = None) -> ObjectBody:
    """The body of the object that shows ``definition`` in a text: sized for its rows until a client has measured it,
    and named ``name`` (D550). The server's ``add_table`` and the converters that read a file's tables make it so."""
    return ObjectBody(
        object_id,
        "table",
        width or TABLE_OBJECT_WIDTH,
        TABLE_ROW_HEIGHT * len(definition.rows),
        TABLE_FRAME_STYLE,
        ref=definition.id,
        name=name,
    )


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
    # The roles of the looks of a table (D1206).
    *_TABLE_STYLES,
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
    body_text_style: ClassVar[str] = DEFAULT_STYLE
    objects_change_container: ClassVar[bool] = True  # an object can be dragged to another paragraph (D1351)
    # 4: a text also carries objects, images and shapes (E10.16)
    # 5: the text carries its own colour palette (D200)
    # 6: the text says which page it is printed on (D904)
    # 7: the text says which language it is written in (D915)
    # 8: paragraphs may be items of lists, which the text holds in a book of its own (E9.21)
    # 11: paragraphs may have names, by their id (D554)
    # 8: object bodies without a description; 9: no rendered containers; 12: styles carry heading levels (E9.22)
    # 13: the text holds its numbering schemes; styles may name a list that numbers them (E9.22)
    # 14: a paragraph may be generated (a table of contents, E9.31)
    # 15: the text holds tables, shown by objects of the kind table (D1201); an object body has one ``ref`` (see core)
    # 16: paragraphs may have descriptions, by their id (D1317, D1318)
    state_schema: ClassVar[int] = 16
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
        #: The names of the headings as the clients were last told them (``settle``): a heading is called by its words
        #: (D1311), so typing in it or giving it a heading style renames it without a rename command.
        self._told_titles: dict[str, str] | None = None
        #: What was written about a paragraph, by id (see D1317 and D1318). It has the same pattern as the description
        #: of an object, a plain string beside the name. Kept like a name when the paragraph is joined away, for undo.
        self.block_descriptions: dict[str, str] = {}
        #: ``name_key`` of every stored name of a paragraph that is in the text, worked out when first needed and kept
        #: up as paragraphs are made: a paste of two thousand lines would otherwise read every name for each.
        self._stored_keys: set[str] | None = None
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

    def requirements(self) -> Requirements:
        """The fonts the styles ask for by name are what this document needs from the server (E1.9, D1306)."""
        return Requirements(fonts=tuple(FontRequirement(family) for family in self.styles.font_families()))

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
            "tables": self.tables_to_data(),
            "names": dict(self.block_names),
            "descriptions": dict(self.block_descriptions),
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
            state.get("objects", ()),
            state.get("images", ()),
            state.get("shapes", ()),
            (),
            state.get("renderings", ()),
            state.get("tables", ()),  # schema 14 and earlier: no tables
        )
        model.block_names = dict(state.get("names", {}))  # schema 10 and earlier: no paragraph had a name
        model.block_descriptions = dict(state.get("descriptions", {}))  # schema 15 and earlier: nothing was written
        model._last = dict(state.get("last", model._last))
        model.structure = TextStructure(model)  # with the objects in: the clients learn the labels with the document
        return model

    def blank(self, parts: frozenset[str] | None) -> None:
        """Blank the paragraphs and objects named in ``parts`` (all of them for ``None``), for redacting an import
        (D723): every character becomes :data:`~claudia_core.FILLER`, so lengths, places and who wrote what stay; what
        was written about a paragraph goes; the suggestions on a blanked paragraph lose their words and reasons.
        ``ValueError`` for a name that is neither."""
        blocks = {block.id for block in self.blocks}
        if parts is not None and (unknown := sorted(parts - blocks - set(self.objects))):
            raise ValueError(f"the text has no paragraph or object {unknown[0]!r}")
        chosen = blocks if parts is None else blocks & parts
        self.block_descriptions = {k: v for k, v in self.block_descriptions.items() if k not in chosen}
        self.blocks = [
            block.with_text(FILLER * len(block.text), block.runs) if block.id in chosen else block
            for block in self.blocks
        ]
        for key, suggestion in self.suggestions.items():
            if suggestion.anchor.block in chosen:
                self.suggestions[key] = replace(
                    suggestion,
                    original=FILLER * len(suggestion.original),
                    replacement=None if suggestion.replacement is None else FILLER * len(suggestion.replacement),
                    reason="",
                )
        self.blank_objects(None if parts is None else parts & set(self.objects))

    def region_from_data(self, data: dict) -> Region:
        """Read a region a client sent: a stretch of text, or a selection of floating objects."""
        if data.get("kind") == ObjectSet.kind:
            return ObjectSet.from_data(data)
        if data.get("kind") == TableRegion.kind:
            return TableRegion.from_data(data)
        if data.get("kind") != TextRange.kind:
            raise ValueError(
                f"composes knows text regions, table regions and object selections, not {data.get('kind')!r}"
            )
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

    def place_regions(self, anchor: BlockAnchor) -> tuple[TextRange, ...]:
        """The character an object is dropped on in another paragraph (D1351): a colleague writing there holds it."""
        length = len(self.block(anchor.block).text)
        start = min(anchor.offset, max(length - 1, 0))
        return (TextRange(anchor.block, start, start + 1),)

    def room_for_new_object(self, anchor: BlockAnchor | None) -> int | None:  # noqa: ARG002 - the column is one width
        """The text column of the page, in CSS pixels (the units of a text's objects): a new object is no wider
        (D1332). The page is in mpt; 1 pt is 4/3 px."""
        page = self.page
        across = page.height if page.orientation == "landscape" else page.width
        return int((across - page.margin_left - page.margin_right) / 1000 * 4 / 3)

    def check_anchor(self, anchor: BlockAnchor, body: ObjectBody) -> None:
        """An object hangs from a character of its paragraph, so the offset must lie inside that paragraph.

        A text has no edge an object could fall off, unlike a slide: only the offset, how far it floats from there and
        how the text flows round it are checked, never the size."""
        if not 0 <= anchor.offset <= len(self.block(anchor.block).text):
            raise IndexError("an object must hang from a place inside its paragraph")
        anchor.check_floating()
        anchor.check_wrap()

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

    def check_table(self, definition: TableDef) -> None:
        """A table of a text is drawn by one of the looks the text has, and the boxes that have a style of their own
        have one that fits (D1206): a paragraph style, which holds both the words and the box of a cell."""
        super().check_table(definition)
        if definition.look not in {look.id for look in TABLE_LOOKS}:
            raise ValueError(f"the text has no table look {definition.look!r}")
        for style in {p.style for p in definition.all_paragraphs() if p.style}:
            self.check_style(style)

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

    def _title_of(self, block: Block) -> str:
        """What a heading is called by: its words, tidied and cut to the longest name; ``""`` when they make no name
        (a heading with no words yet)."""
        words = clean_name(block.text)[:MAX_THING_NAME].strip()
        return words if words and name_problem(words) is None else ""

    def _names_of_paragraphs(self) -> dict[str, str]:
        """The name each paragraph that has one is called by now, by id. A heading with a title is called by it (D1311),
        worked out here each time, so it cannot go stale; a number in brackets tells apart two with one title and one
        a person named a paragraph by, the earlier in the text keeping the plain words. Every other paragraph has the
        name it was given."""
        names: dict[str, str] = {}
        titled: list[tuple[str, str]] = []
        for block in self.blocks:
            title = self._title_of(block) if self.heading_level(block) is not None else ""
            if title:
                titled.append((block.id, title))
            elif stored := self.block_names.get(block.id):
                names[block.id] = stored
        taken = [name for _kind, _id, name in super().named_things()]
        taken.extend(names.values())
        for block_id, title in titled:
            names[block_id] = distinct_name(title, taken)
            taken.append(names[block_id])
        return names

    def named_things(self):
        """The objects with names, then the paragraphs with names, in the order of the text: one namespace."""
        yield from super().named_things()
        names = self._names_of_paragraphs()
        for block in self.blocks:
            name = names.get(block.id)
            if name:
                yield self.block_kind(block), block.id, name

    def unnamed_things(self):
        """The objects without a name, then the paragraphs without one: what a text from before paragraphs had names
        holds (D1310). A heading with a title has its title for a name, and a table of contents is not a paragraph a
        person points at."""
        yield from super().unnamed_things()
        for block in self.blocks:
            if block.generated is not None or self.block_names.get(block.id):
                continue
            if self.heading_level(block) is not None and self._title_of(block):
                continue
            yield self.block_kind(block), block.id

    def _has_block(self, block_id: str) -> bool:
        return any(block.id == block_id for block in self.blocks)

    def has_thing(self, thing_id: str) -> bool:
        """Is there an object or a paragraph with this id, named or not?"""
        return self._has_block(thing_id) or super().has_thing(thing_id)

    def thing_name(self, thing_id: str) -> str:
        """The name of a paragraph or an object, ``""`` if it has none; ``ValueError`` if there is neither."""
        if self._has_block(thing_id):
            if self.name_is_fixed(thing_id):
                return self._names_of_paragraphs()[thing_id]
            return self.block_names.get(thing_id, "")
        return super().thing_name(thing_id)

    def set_thing_name(self, thing_id: str, name: str) -> str:
        """Name a paragraph or an object (``""``: no name); returns the name it had. A heading keeps the name it is
        given for when it is a paragraph again; it is called by its title meanwhile."""
        if not self._has_block(thing_id):
            return super().set_thing_name(thing_id, name)
        old = self.block_names.get(thing_id, "")
        if name:
            self.block_names[thing_id] = name
        else:
            self.block_names.pop(thing_id, None)
        self._stored_keys = None
        return old

    def name_is_fixed(self, thing_id: str) -> bool:
        """A heading with a title is called by it, and so cannot be renamed (D1311)."""
        if not self._has_block(thing_id):
            return super().name_is_fixed(thing_id)
        block = self.block(thing_id)
        return self.heading_level(block) is not None and bool(self._title_of(block))

    def thing_description(self, thing_id: str) -> str:
        """What is written about a paragraph or an object, ``""`` if nothing; ``ValueError`` if there is neither."""
        if self._has_block(thing_id):
            return self.block_descriptions.get(thing_id, "")
        return super().thing_description(thing_id)

    def set_thing_description(self, thing_id: str, description: str) -> str:
        """Write something about a paragraph (``""``: nothing); returns what was written. An object is described by
        :class:`~claudia_core.DescribeObject`."""
        if not self._has_block(thing_id):
            return super().set_thing_description(thing_id, description)
        old = self.block_descriptions.get(thing_id, "")
        if description:
            self.block_descriptions[thing_id] = description
        else:
            self.block_descriptions.pop(thing_id, None)
        return old

    def _taken_keys(self) -> set[str]:
        """``name_key`` of every name a paragraph of the text was given, and of every object: what a new name must
        differ from. The headings' titles are not in it: a title gives way to a name, not the other way round."""
        if self._stored_keys is None:
            here = {block.id for block in self.blocks}
            self._stored_keys = {name_key(name) for block_id, name in self.block_names.items() if block_id in here}
        objects = {name_key(name) for _kind, _id, name in super().named_things()}
        return self._stored_keys | objects

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

    def restyle_users(self, old: str, new: str) -> list[Command]:
        """The commands that put every paragraph, and every object (itself or its words), that has the style ``old``
        under ``new`` instead (asked by the deletion of a style, D226)."""
        from .commands import SetStyle  # noqa: PLC0415  (commands import this module)

        paragraphs: list[Command] = [SetStyle(b.id, new) for b in self.blocks if b.style == old]
        return [*paragraphs, *ObjectModel.restyle_users(self, old, new)]

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
        if self.is_entry(paragraph_id):
            return self._type_in_entry(paragraph_id, offset, text, runs, fields)
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
        if self.is_entry(paragraph_id):
            return self._cut_from_entry(paragraph_id, start, end)
        text, runs, fields = self.remove(paragraph_id, start, end)
        events: tuple[object, ...] = (TextChanged(paragraph_id, start, end - start, ""),) if end > start else ()
        if fields:
            events = (*events, FieldsPut(paragraph_id, self.block(paragraph_id).fields))
        return text, runs, fields, events

    def _type_in_entry(
        self, paragraph_id: str, offset: int, text: str, runs: list[Run], fields: tuple[Field, ...]
    ) -> tuple[object, ...]:
        """Type into a box of a table (D1210): the words of the box are one paragraph, and it is the ordinary text event
        that tells the clients, with the id of the box."""
        self.check_entry_edit(paragraph_id)
        self.put_entry_words(paragraph_id, self.entry_words(paragraph_id).typed(offset, text, runs, fields))
        if not text:
            return ()
        changed = TextChanged(paragraph_id, offset, 0, text, tuple(runs))
        return (changed, FieldsPut(paragraph_id, self.entry_words(paragraph_id).fields)) if fields else (changed,)

    def _cut_from_entry(
        self, paragraph_id: str, start: int, end: int
    ) -> tuple[str, list[Run], tuple[Field, ...], tuple[object, ...]]:
        """Cut characters out of a box of a table."""
        self.check_entry_edit(paragraph_id)
        kept, text, runs, fields = self.entry_words(paragraph_id).cut(start, end)
        self.put_entry_words(paragraph_id, kept)
        events: tuple[object, ...] = (TextChanged(paragraph_id, start, end - start, ""),) if end > start else ()
        if fields:
            events = (*events, FieldsPut(paragraph_id, kept.fields))
        return text, runs, fields, events

    # -- fields (claudia_core.FieldHost, step H) ----------------------------------------------------------
    def fields_of(self, paragraph_id: str) -> tuple[Field, ...]:
        """The fields of a paragraph of the text, in the words of a floating object or in a box of a table."""
        if paragraph_id in self.objects:
            return self.object_fields(paragraph_id)
        if self.is_entry(paragraph_id):
            return self.entry_words(paragraph_id).fields
        return self.block(paragraph_id).fields

    def put_fields(self, paragraph_id: str, fields: tuple[Field, ...]) -> tuple[object, ...]:
        """Give a paragraph other fields at its U+FFFC; the event that tells the clients."""
        if paragraph_id in self.objects:
            return (self.put_object_fields(paragraph_id, fields),)
        if self.is_entry(paragraph_id):
            self.put_entry_words(paragraph_id, self.entry_words(paragraph_id).with_fields(fields))
            return (FieldsPut(paragraph_id, fields),)
        self._put(self.block(paragraph_id).with_fields(fields))
        return (FieldsPut(paragraph_id, fields),)

    def text_regions(self, paragraph_id: str, start: int, end: int) -> tuple[Region, ...]:
        """A stretch of a paragraph of the text, or the floating object whose words change."""
        if paragraph_id in self.objects:
            return self.selection_of(paragraph_id)
        if (found := parse_entry_id(paragraph_id)) is not None:
            return (TableRegion(found[0], frozenset({found[1]}), frozenset({found[2]})),)
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
        one item may have renumbered a hundred others. And which headings are called by other words now (D1311): a
        paragraph that becomes a heading, a heading that is retyped, a heading that is a paragraph again."""
        self.structure.settle(ctx)
        self._settle_titles(ctx)

    def _settle_titles(self, ctx: Context) -> None:
        titles = {b.id for b in self.blocks if self.heading_level(b) is not None and self._title_of(b)}
        was = self._told_titles or {}
        if not titles and not was:
            self._told_titles = {}
            return
        names = self._names_of_paragraphs()
        now = {block_id: names[block_id] for block_id in titles}
        for block_id, name in now.items():
            if was.get(block_id) != name:
                ctx.emit(ThingRenamed(block_id, name))
        for block_id in was.keys() - now.keys():
            if self._has_block(block_id):  # a heading no longer: it is called what it was given, or nothing
                ctx.emit(ThingRenamed(block_id, self.block_names.get(block_id, "")))
        self._told_titles = now

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

    def split(self, block_id: str, offset: int, new_id: str, style: str, name: str = "") -> None:
        """Cut a paragraph at ``offset``; the rest becomes the paragraph ``new_id`` right behind it, in ``style``
        and, if the paragraph is a list item, an item of the same list at the same level.

        ``name`` is what the new paragraph is called (D1310): the first free "Paragraph N" in the language of its
        maker, made by the server. Another that is called that already (somebody made one at the same moment, or a
        name kept for a paragraph that came back) gives way with a number in brackets. Without a name the paragraph
        has the one it had before, if any."""
        block = self.block(block_id)
        if not 0 <= offset <= len(block.text):
            raise IndexError("split outside the text")
        if any(b.id == new_id for b in self.blocks):
            raise ValueError(f"the paragraph {new_id!r} exists already")
        self.check_style(style)
        wanted = name or self.block_names.get(new_id, "")
        made = distinct_name(wanted, self._taken_keys()) if wanted else ""  # before the paragraph is among them
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
        if made:
            self.block_names[new_id] = made
            if self._stored_keys is not None:
                self._stored_keys.add(name_key(made))

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
        self._stored_keys = None
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
