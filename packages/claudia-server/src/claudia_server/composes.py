"""The methods of the text app: what a text view needs to show paragraphs, take what people type, follow cursors (E9).

``composes_methods`` is ``core_methods`` plus

* ``paragraphs`` and ``suggestions``: the document, to load it;
* ``replace_text``: the one way people write. It replaces a range (it may span paragraphs) by some text, and a line
  break in the text starts a new paragraph. A single request is a single step to undo. With the id of a box of a
  table (``<table>/<row>/<column>``) it types in the box, which is one paragraph: a line break is a space (D1212);
* ``set_style``: give a paragraph a named style (D62);
* ``page`` and ``set_page``: the page the text is printed on (paper, orientation, margins, page numbers; D904). The
  pages themselves are laid out in the client (D901);
* ``objects``, ``images`` and ``shapes``: the floating objects of the text and what they are drawn with, for the
  print preview, which draws them where they hang (D907); ``shapes`` also says which outlines the server offers;
* ``add_image`` and ``add_object`` (a text box or a shape, :mod:`claudia_server.shape_methods`) and ``set_wrap``: put an
  object where it hangs, and say how the text flows round it (D1061, D1064);
* ``lists``, ``make_list``, ``indent_item``, ``continue_list``, ``list_start``, ``number_headings`` and the scheme
  methods: bullets, numbers, their levels, numbered headings and the numbering manager, the same as in creates
  (:mod:`claudia_server.structure_methods`, E9.21, E9.22);
* ``styles``, ``change_style``, ``deviate_style``, ``rename_style`` and ``check_css``: the styles are CSS in the
  document (E1.10, D73). Changing a style changes every paragraph that has it; deviating makes a new style, with a
  provisional name, from an old one and applies it, in one step (D75); naming ends the invitation to name it;
* ``tables``, ``add_table``, ``set_entries``, ``insert_rows``, ``merge_cells`` and the rest: tables, by the ids of
  their rows and columns (:mod:`claudia_server.tables`, E9.32);
* ``search_find``, ``search_preview`` and ``search_replace``: search and replace in the text, its headings, remarks,
  the objects floating over it and the boxes of its tables (:mod:`claudia_server.composes_search`, E9.28, E9.32);
* ``look`` and ``hold``: where my cursor is. ``hold`` also locks the ± n words around it for everybody else (D11);
* ``move_object``, ``resize_object``, ``rotate_object`` and ``remove_object``: the floating objects. An object hangs
  from a character, floats at an offset from it and turns about its centre (rotation-ui);
* ``suggest`` (the assistant only), ``accept_suggestion`` and ``reject_suggestion``: composes' suggest mode (D262);
* ``read_paragraphs``, ``outline``, ``replace_words``, ``add_paragraphs`` and ``suggest_words``: the text by what it
  says rather than by offsets, which is how a language model can work in it (:mod:`claudia_server.composes_words`,
  D681).

The assistant writes a text as it writes a sheet or a slide (D640): in *act* through the methods its allow-list names
(``apps.MODEL_METHODS``, SEC-10), in *suggest* only through ``suggest`` or ``suggest_words``, and people accept. How
the page is set up is people's, as in the other apps (:func:`claudia_server.printing.people_only`).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from claudia_composes_io import (
    apply_edits_to_docx,
    apply_edits_to_odt,
    docx_export_losses,
    docx_unwritten_changes,
    export_info,
    odt_export_losses,
    odt_unwritten_changes,
    text_to_docx,
    text_to_odt,
)

from claudia_composes import (
    DEFAULT_STYLE,
    AcceptSuggestion,
    DeleteText,
    InsertText,
    JoinParagraphs,
    PageSetup,
    PageSetupError,
    ParagraphAnchor,
    ProposeSuggestion,
    ResolveSuggestion,
    SetObjectWrap,
    SetPageSetup,
    SetStyle,
    SplitParagraph,
    TextModel,
    TextRange,
    next_style,
    word_window,
)
from claudia_core import (
    Batch,
    Command,
    CreateStyle,
    StyleDef,
    free_names,
    plain,
    validate_css,
)
from claudia_creates import ShapeLibrary

from .audience import HISTORY
from .composes_annotations import export_annotations
from .composes_contents import add_contents_methods
from .composes_search import add_search_methods
from .composes_words import add_word_methods
from .containers import add_container_methods
from .font_report import add_font_report_method
from .i18n import message_of, msg
from .object_methods import Placement, add_object_methods
from .office_export import export_with_original, office_export
from .printing import add_language_methods, people_only
from .protocol import Context, MethodTable, RequestError, core_methods
from .replay import add_replay_methods
from .shape_methods import add_shape_methods
from .structure_methods import add_structure_methods
from .style_targets import OBJECTS
from .styles import add_style_methods, own_css
from .tables import add_table_methods, one_line
from .thing_names import add_name_methods, paragraph_label
from .what_if import add_what_if_methods
from .wire import current_revision, done

MAX_ZONE_WORDS = 10  # the widest ± n words zone a cursor may ask for
ZONE_SECONDS = 15.0  # a held zone lapses this long after its owner was last active
MAX_NEW_PARAGRAPHS = 2_000  # line breaks in one piece of typed or pasted text
MAX_PARAGRAPHS = 50_000  # paragraphs in a document
MAX_STYLED_PARAGRAPHS = 2_000  # paragraphs one deviation may apply its new style to

composes_methods = core_methods.extended()
add_search_methods(composes_methods)


def _text(ctx: Context) -> TextModel:
    model = ctx.document.model
    if not isinstance(model, TextModel):
        raise RequestError("command_error", msg("this document is not a text"))
    return model


class _ParagraphTargets:
    """A paragraph of the text as a style target, ``{"paragraph": id}``: one slot that reads text, paragraph and box
    (D304), for the shared ``apply_style`` and ``deviate`` (:mod:`claudia_server.style_targets`)."""

    key = "paragraph"

    def thing(self, model: TextModel, target: dict) -> str:
        paragraph = target.get("paragraph")
        if not isinstance(paragraph, str):
            raise ValueError("a target names its paragraph by id")
        model.paragraph(paragraph)  # KeyError: no such paragraph
        return "paragraph"

    def style_in(self, model: TextModel, target: dict, slot: str) -> str | None:
        return model.paragraph(target["paragraph"]).style

    def command(self, model: TextModel, target: dict, slot: str, style: str) -> Command:
        return SetStyle(target["paragraph"], style)

    def uses(self, model: TextModel) -> Counter[str]:
        return Counter(paragraph.style for paragraph in model.paragraphs)


add_style_methods(composes_methods, targets=(_ParagraphTargets(), OBJECTS))
add_structure_methods(composes_methods)
add_contents_methods(composes_methods)
add_name_methods(composes_methods)
add_replay_methods(composes_methods)
add_what_if_methods(composes_methods)
add_font_report_method(composes_methods)


def _inside(model: TextModel, paragraph: str, offset: int, what: str = "offset") -> int:
    if not 0 <= offset <= len(model.paragraph(paragraph).text):
        raise RequestError("command_error", msg("{what} is outside the paragraph", what=what))
    return offset


# ------------------------------------------------------------------------------ reading
@composes_methods.method("paragraphs")
def _paragraphs(ctx):
    """The paragraphs in order, each as `{id, style, text, runs}` (`runs` are `[length, author, via]`: who wrote
    which stretch), the styles (see `styles`), the lists and the schemes they can have, and the revision they are
    at. A paragraph that is a list item also has `item` (`{list, level}`) and `label` (`{marker, path}`: what is
    drawn in front of it, derived from the structure, and for numbers the trail of counters and the number a
    reference prints); so has a paragraph whose style numbers it (a numbered heading). A table of contents has
    `generated` (its options, `{kind, first, last, numbers, places, leader}`) and `entries` (`{target, level, number,
    text, style, place}`, derived from the headings, E9.31). A paragraph with references has `fields` (`{kind,
    target, show}`, one for each U+FFFC of its text) and `shown` (`{text, state}`, what each reads as, step H). A named
    one has `name` (D554). `lists` are `{id, scheme,
    start, name}`; `schemes` are `{id, name, kind, levels, indent, gap}` (`indent` and `gap` in em; see `lists`)."""
    model = _text(ctx)
    labels, entries, shown = model.labels(), model.structure.all_entries(), model.structure.shown()
    return {
        "revision": current_revision(ctx),
        "styles": model.styles.views(model.palette.colours()),
        "lists": model.lists.to_data(),
        "schemes": model.schemes.to_data(),
        "paragraphs": [_paragraph_view(model, b, labels, entries, shown) for b in model.paragraphs],
    }


def _paragraph_view(model, paragraph, labels, entries, shown) -> dict:
    """A paragraph as `paragraphs` sends it: its data, its list label if it is an item, the entries of a table of
    contents, what its fields read as (`shown`, step H), its name if it has one (D554)."""
    view = paragraph.to_data()
    if paragraph.id in shown:
        view["shown"] = [s.to_data() for s in shown[paragraph.id]]
    if paragraph.id in labels:
        view["label"] = labels[paragraph.id].to_data()
    if paragraph.id in entries:
        view["entries"] = [entry.to_data() for entry in entries[paragraph.id]]
    name = model.thing_name(paragraph.id)
    if name:
        view["name"] = name
    description = model.paragraph_descriptions.get(paragraph.id)
    if description:
        view["description"] = description
    return view


@composes_methods.method("suggestions")
def _suggestions(ctx):
    """The suggestions that are still open, as `{id, author, paragraph, start, end, original, replacement, reason,
    state, outdated}`. `replacement` is null for a remark. An outdated one cannot be accepted any more."""
    return _text(ctx).visible_suggestions()


@composes_methods.method("export_choices")
def _export_choices(ctx):
    """What the export dialog may offer besides the format: `{descriptions}`, how many paragraphs have a description
    that `export_office` could write as a review comment (`description_comments`). The tick is shown only when it is
    above zero (A4). A read for anybody."""
    return {"descriptions": len(export_annotations(_text(ctx), ctx.user, comments=True).comments)}


@composes_methods.method(
    "export_office", "format:str tracked_changes:bool=false description_comments:bool=false", leaves="export"
)
def _export_office(ctx, *, format, tracked_changes, description_comments):
    """The document's current content as bytes of a Word file (`format` `"docx"`) or an OpenDocument text (`"odt"`),
    wrapped for the wire as `{format, content_type, data}` (`data` base64); the answer also has `losses`, what
    the file could not hold, as `{kind, detail, count}` codes.

    With `tracked_changes` (default off, so a clean copy is the default, D212), every open suggestion that proposes a
    replacement is written as a tracked change a reviewer can accept or reject in Word or any OpenDocument program,
    dated with when it was proposed, by whom. An odt also says in its metadata when the document was made and last
    changed, and by whom: all read from the document's log (D411).

    A name a person gave a paragraph is written as a bookmark around its words, one that was only worked out is not
    (D1311). With `description_comments` (default off, A4) what a person wrote about a paragraph is written as a review
    comment by the person who exports, dated today (A6). Such a file is always written anew: the file an import kept
    cannot be patched with comments, and the answer says so in `losses`."""
    if format not in ("docx", "odt"):
        raise RequestError("bad_request", msg('export_office: format must be "docx" or "odt"'))
    model = _text(ctx)
    info, times = export_info(ctx.reader.log(ctx.document), ctx.document.branch)
    if not ctx.reader.holds(HISTORY):  # a history she cannot read dates nothing: her export does (SEC-26, D2008)
        times = dict.fromkeys(model.suggestions, ctx.document.now())
    draw = None if ctx.renderings is None else ctx.renderings.rasteriser  # draws an SVG picture as a PNG (D464)
    notes = export_annotations(model, ctx.user, comments=description_comments)
    # the file an import kept cannot be patched with comments: a new one is written, and the answer says so
    why = msg("the descriptions are written as comments, which the kept file cannot take") if notes.comments else ""
    if format == "docx":
        return export_with_original(
            ctx,
            format,
            TextModel,
            lambda original, baseline, current, losses: apply_edits_to_docx(
                original,
                baseline,
                current,
                track_suggestions=tracked_changes,
                change_times=times,
                losses=losses,
                rasterise=draw,
            ),
            lambda: office_export(
                format,
                text_to_docx(
                    model,
                    track_suggestions=tracked_changes,
                    change_times=times,
                    rasterise=draw,
                    info=info,
                    annotations=notes,
                ),
                docx_export_losses(model, track_suggestions=tracked_changes, rasterised=draw is not None),
            ),
            docx_unwritten_changes,
            not_patched=why,
        )
    return export_with_original(
        ctx,
        format,
        TextModel,
        lambda original, baseline, current, _: apply_edits_to_odt(
            original,
            baseline,
            current,
            track_suggestions=tracked_changes,
            info=info,
            change_times=times,
            rasterise=draw,
        ),
        lambda: office_export(
            format,
            text_to_odt(
                model,
                track_suggestions=tracked_changes,
                info=info,
                change_times=times,
                rasterise=draw,
                annotations=notes,
            ),
            odt_export_losses(model, track_suggestions=tracked_changes, rasterised=draw is not None),
        ),
        odt_unwritten_changes,
        not_patched=why,
    )


# ------------------------------------------------------------------------------ writing
def edit_plan(
    model: TextModel, first: str, start: int, *, last: str, end: int, text: str, label: str = ""
) -> tuple[list[Command], tuple[str, int]]:
    """The commands that replace the text from ``first:start`` to ``last:end`` by ``text``, and where the cursor
    ends up (``(paragraph, offset)``). Paragraphs in between go away; the last one's rest is joined to the first. In
    the box of a table it is :func:`_box_plan`.

    A paragraph that this makes is called ``label`` and the first free number (D1310), in the language of the person
    who makes it; without a ``label`` it has no name, as in a log from before paragraphs had names. A box of a
    table is no paragraph a person points at, so it gets none."""
    if "/" in first or "/" in last or model.is_entry(first) or model.is_entry(last):
        return _box_plan(model, first, start, last=last, end=end, text=text)
    return _paragraph_plan(model, first, start, last=last, end=end, text=text, label=label)


def _paragraph_plan(
    model: TextModel, first: str, start: int, *, last: str, end: int, text: str, label: str = ""
) -> tuple[list[Command], tuple[str, int]]:
    """:func:`edit_plan` in the paragraphs of the text."""
    i, j = model.index_of(first), model.index_of(last)
    if j < i or (i == j and end < start):
        raise RequestError("command_error", msg("the range ends before it starts"))
    _inside(model, first, start, "start")
    _inside(model, last, end, "end")
    lines = plain(text).split("\n")  # words a person writes make no field (step H)
    if len(lines) - 1 > MAX_NEW_PARAGRAPHS or len(model.paragraphs) + len(lines) > MAX_PARAGRAPHS:
        raise RequestError("command_error", msg("that would make too many paragraphs"))
    paragraphs = model.paragraphs
    commands: list[Command] = []
    if i == j:
        if end > start:
            commands.append(DeleteText(first, start, end - start))
        tail = len(paragraphs[i].text) - end
    else:
        tail = len(paragraphs[j].text) - end
        if len(paragraphs[i].text) > start:
            commands.append(DeleteText(first, start, len(paragraphs[i].text) - start))
        for middle in paragraphs[i + 1 : j]:
            if middle.text:
                commands.append(DeleteText(middle.id, 0, len(middle.text)))
            commands.append(JoinParagraphs(middle.id, first, start))
        if end > 0:
            commands.append(DeleteText(last, 0, end))
        commands.append(JoinParagraphs(last, first, start))
    cursor, offset, style = first, start, paragraphs[i].style
    fresh = iter(model.fresh_ids(len(lines) - 1))
    made = iter(free_names(label, model.names_in_use(), len(lines) - 1) if label and len(lines) > 1 else ())
    for n, line in enumerate(lines):
        if n:
            style = next_style(model.styles, style) if tail == 0 else style
            new = next(fresh)
            commands.append(SplitParagraph(cursor, offset, new, style, next(made, "")))
            cursor, offset = new, 0
        if line:
            commands.append(InsertText(cursor, offset, line))
            offset += len(line)
    return commands, (cursor, offset)


def _box_plan(
    model: TextModel, first: str, start: int, *, last: str, end: int, text: str
) -> tuple[list[Command], tuple[str, int]]:
    """:func:`edit_plan` inside the box of a table (D1210, D1212): a box is one paragraph, so a range stays in one box
    and a line break in ``text`` is a space. A box a merge covers takes no words."""
    if first != last:
        raise RequestError("command_error", msg("a range stays inside one box of a table"))
    if not model.is_entry(first):
        raise RequestError("command_error", msg("there is no paragraph {paragraph!r}", paragraph=first))
    try:
        model.check_entry_edit(first)
    except ValueError as error:
        raise RequestError("command_error", message_of(error)) from None
    length = len(model.entry_words(first).text)
    for offset, what in ((start, "start"), (end, "end")):
        if not 0 <= offset <= length:
            raise RequestError("command_error", msg("{what} is outside the paragraph", what=what))
    if end < start:
        raise RequestError("command_error", msg("the range ends before it starts"))
    line = one_line(text)
    commands: list[Command] = []
    if end > start:
        commands.append(DeleteText(first, start, end - start))
    if line:
        commands.append(InsertText(first, start, line))
    return commands, (first, start + len(line))


add_word_methods(composes_methods, edit=edit_plan)


def _named(text: str, lines: int) -> str:
    if not text:
        return "deleted text"
    return f"inserted {lines} paragraphs" if lines > 1 else "replaced text"


@composes_methods.method(
    "replace_text", "paragraph:str start:int end_paragraph:str end:int text:text base:revision?", write=True
)
def _replace_text(ctx, *, paragraph, start, end_paragraph, end, text, base):
    """Replace the text from `paragraph`:`start` up to `end_paragraph`:`end` by `text` (offsets count characters). A
    line break in `text` starts a new paragraph; a range that spans paragraphs joins what is left of them. Typing is an
    empty range, deleting is empty text. One request is one step in the history. Returns the revision and where the
    cursor ends up: `{revision, paragraph, offset}`. Refused with `locked` where a colleague holds the text."""
    commands, (cursor, offset) = edit_plan(
        _text(ctx), paragraph, start, last=end_paragraph, end=end, text=text, label=paragraph_label(ctx)
    )
    result = {"paragraph": cursor, "offset": offset}
    if not commands:
        return {"revision": current_revision(ctx), **result}
    command = commands[0] if len(commands) == 1 else Batch(tuple(commands), _named(text, text.count("\n") + 1))
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"revision": applied.revision.to_data(), **result}


@composes_methods.method("add_paragraph_after", "paragraph:str base:revision?", write=True)
def _add_paragraph_after(ctx, *, paragraph, base):
    """An empty paragraph right after the paragraph `paragraph`, in the style Enter at its end would give, and after
    what hangs from its end: a table there stays where it is, before the new paragraph (D1331). Returns the revision and
    the new paragraph: `{revision, paragraph, offset}`, the offset 0. Refused with `command_error` for a box of a table
    or a paragraph the text does not have."""
    model = _text(ctx)
    try:
        found = None if "/" in paragraph or model.is_entry(paragraph) else model.paragraph(paragraph)
    except KeyError:
        found = None
    if found is None:
        raise RequestError("command_error", msg("there is no paragraph {paragraph!r}", paragraph=paragraph))
    [new] = model.fresh_ids(1)
    label = paragraph_label(ctx)
    name = next(iter(free_names(label, model.names_in_use(), 1)), "") if label else ""
    split = SplitParagraph(paragraph, len(found.text), new, next_style(model.styles, found.style), name, keep=True)
    applied = ctx.document.execute(split, author=ctx.user, base=base)
    return {"revision": applied.revision.to_data(), "paragraph": new, "offset": 0}


@composes_methods.method("set_style", "paragraph:str style:str base:revision?", write=True)
def _set_style(ctx, *, paragraph, style, base):
    """Give the paragraph `paragraph` the style named `style` (one of the ids `paragraphs` lists)."""
    return done(ctx, SetStyle(paragraph, style), base)


# ------------------------------------------------------------------------------ the page (D904)
@composes_methods.method("page")
def _page(ctx):
    """The page the text is printed on: `{paper, width, height, orientation, margins, page_numbers}`, lengths in
    mpt (thousandths of a point), `width` the short side, `margins` top, right, bottom, left."""
    return _text(ctx).page.to_data()


@composes_methods.method("set_page", "setup:dict base:revision?", write=True)
def _set_page(ctx, *, setup, base):
    """Lay the text out on another page (`setup` as `page` returns it). One step for everybody, in the history.
    `command_error` names what is wrong with a page that cannot be used."""
    people_only(ctx)
    try:
        page = PageSetup.from_data(setup)
    except PageSetupError as exc:
        raise RequestError("command_error", message_of(exc)) from None
    return done(ctx, SetPageSetup(page), base)


# ------------------------------------------------------------------------------ the language (D915, D917)
add_language_methods(composes_methods)


# ------------------------------------------------------------------------------ floating objects, for printing (D907)
@composes_methods.method("objects")
def _objects(ctx):
    """The floating objects of the text, the one in front last, as `{revision, objects}`. An object is the shape all
    three apps share (`{id, kind, w, h, style, paragraph, ref, imported, rotation, snap, anchor}`;
    `ref` is the id of the definition the kind shows: a picture, a container or a table, see `images`,
    `containers` and `tables`), with `anchor` `{kind: "paragraph", container: <paragraph id>, offset}`: the character it
    hangs from. `w` and `h` are CSS pixels. `imported`'s `source_path` is the picture's full path if it was saved on
    import (`null` if not), the same for everyone who can open the document."""
    model = _text(ctx)
    objects = [obj.to_data() for paragraph in model.paragraphs for obj in model.objects_on(paragraph.id)]
    return {"revision": current_revision(ctx), "objects": objects}


# ------------------------------------------------------------------------------ styles (E1.10, E9.7)
# ``styles``, ``change_style``, ``rename_style``, ``check_css``, the palette and ``set_object_style`` are the
# same in every app and come from ``.styles``. Only the one that names paragraphs stays here.
@composes_methods.method("deviate_style", "parent:str paragraphs:list set:dict? text:text? base:revision?", write=True)
def _deviate_style(ctx, *, parent, paragraphs, set, text, base):
    """Make a new style from `parent` that differs in the CSS given (`set` properties, or `text`) and give it to the
    paragraphs `paragraphs`, in one step. It gets a provisional name such as “Heading 1 (changed)” and is marked
    `to_name` until somebody names it (D75). Returns `{style, name, revision}`. `command_error` if nothing differs from
    the parent."""
    model = _text(ctx)
    if len(paragraphs) > MAX_STYLED_PARAGRAPHS or not all(isinstance(b, str) for b in paragraphs):
        raise RequestError(
            "bad_request",
            msg(
                "paragraphs must be a list of at most {limit} paragraph ids",
                limit=MAX_STYLED_PARAGRAPHS,
            ),
        )
    try:
        inherited = model.styles.computed(parent)
    except KeyError as exc:
        raise RequestError("command_error", exc.args[0]) from None
    for paragraph in paragraphs:
        model.paragraph(paragraph)  # KeyError -> command_error: the paragraph must exist
    given = validate_css(own_css(set, text) or {})
    own = {name: value for name, value in given.items() if inherited.get(name) != value}
    if not own:
        raise RequestError(
            "command_error",
            msg("the new style would look just like “{name}”", name=model.styles.get(parent).name),
        )
    name = model.styles.provisional_name(parent)
    kind = model.styles.get(parent).kind  # a deviation is of its parent's kind (D305)
    created = StyleDef(model.styles.unique_id(name), name, "", parent, own, to_name=True, kind=kind)
    commands: list[Command] = [CreateStyle(created), *(SetStyle(paragraph, created.id) for paragraph in paragraphs)]
    applied = ctx.document.execute(Batch(tuple(commands), "Deviate style"), author=ctx.user, base=base)
    return {"style": created.id, "name": name, "revision": applied.revision.to_data()}


# ------------------------------------------------------------------------------ cursors and zones
def _regions_at(ctx: Context, paragraph: str, offset: int, words: int) -> list[TextRange]:
    model = _text(ctx)
    if not 0 <= words <= MAX_ZONE_WORDS:
        raise RequestError("bad_request", msg("words must be from 0 to {limit}", limit=MAX_ZONE_WORDS))
    _inside(model, paragraph, offset)
    zone = word_window(model.paragraph(paragraph).text, offset, words, paragraph)
    return [zone, TextRange(paragraph, offset, offset)]


@composes_methods.method("look", "paragraph:str offset:int words:int=3")
def _look(ctx, *, paragraph, offset, words):
    """Show where my cursor is: the others see a caret and the ± `words` words around it. Locks nothing, so viewers
    may use it. The others receive an `ephemeral` event of kind `presence` with two text regions: the zone and the
    caret (an empty one)."""
    ctx.document.show_presence(ctx.user, _regions_at(ctx, paragraph, offset, words))
    return {}


@composes_methods.method("hold", "paragraph:str offset:int words:int=3", write=True)
def _hold(ctx, *, paragraph, offset, words):
    """Show my cursor and lock the ± `words` words around it (D11): colleagues cannot change that text, nor undo into
    it, until I move on, call `unlock`, or have been quiet for a few seconds (renew by calling `hold` again).
    `locked` if a colleague holds any of it."""
    ctx.document.lock(ctx.user, _regions_at(ctx, paragraph, offset, words), min(ctx.lock_seconds, ZONE_SECONDS))
    return {}


# ------------------------------------------------------------------------------ suggestions (D262)
@composes_methods.method(
    "suggest", "paragraph:str start:int end:int reason:text replacement:text? base:revision?", write=True
)
def _suggest(ctx, *, paragraph, start, end, reason, replacement, base):
    """The assistant only: propose that the text from `start` up to `end` of `paragraph` be replaced by `replacement`
    (empty text proposes a deletion), or, with no `replacement`, remark on it. Changes no text. Returns the id."""
    if not ctx.account.system:
        raise RequestError("forbidden", msg("only the assistant makes suggestions"))
    model = _text(ctx)
    original = model.paragraph(paragraph).text[start:end]
    command = ProposeSuggestion(model.fresh_suggestion_id(), paragraph, start, end, original, replacement, reason)
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"suggestion": command.id, "revision": applied.revision.to_data()}


@composes_methods.method("accept_suggestion", "id:str base:revision?", write=True)
def _accept(ctx, *, id, base):
    """Accept a suggestion: I replace the text, and I am its author; the suggestion's author is recorded as the one it
    came through. `command_error` if it is not open any more, is a remark, or the text under it has changed."""
    suggestion = _text(ctx).suggestion(id)
    if suggestion.replacement is None:
        raise RequestError("command_error", msg("a remark suggests no change; dismiss it instead"))
    anchor = suggestion.anchor
    command = AcceptSuggestion(
        id, anchor.paragraph, anchor.start, anchor.end, suggestion.replacement, suggestion.author
    )
    return done(ctx, command, base)


@composes_methods.method("reject_suggestion", "id:str base:revision?", write=True)
def _reject(ctx, *, id, base):
    """Reject a suggestion, or dismiss a remark. Logged; undo reopens it."""
    suggestion = _text(ctx).suggestion(id)
    if suggestion.state != "open":
        raise RequestError("command_error", msg("this suggestion is not open any more"))
    state = "dismissed" if suggestion.replacement is None else "rejected"
    return done(ctx, ResolveSuggestion(id, state), base)


# Objects in a text, containers among them (D390, D395, D560): an object hangs from a character of a paragraph
# and floats over it at an offset from that character, without pushing the words aside (D179, D1023).
def _paragraph_has(model: TextModel, *, paragraph: str, offset: int) -> None:
    try:
        text = model.paragraph(paragraph).text
    except KeyError:
        raise RequestError("command_error", msg("there is no paragraph {paragraph!r}", paragraph=paragraph)) from None
    if not 0 <= offset <= len(text):
        raise RequestError("command_error", msg("offset is outside the paragraph"))


def _at_character(
    model: TextModel,
    held: ParagraphAnchor | None,
    *,
    paragraph: str,
    offset: int,
    dx: int | None = None,
    dy: int | None = None,
    wrap: str | None = None,
    gap: int | None = None,
):
    """Where an object of a text is: character ``offset`` of the paragraph ``paragraph``, floating ``dx`` to the right
    and ``dy`` down from it, and how the text flows round it (D1061). What a move leaves out it keeps from where the
    object floats now; a new object floats over the text, as objects did before wrapping, unless it says otherwise."""
    _paragraph_has(model, paragraph=paragraph, offset=offset)
    base = held if held is not None else ParagraphAnchor(paragraph, offset)
    try:
        anchor = replace(
            base,
            paragraph=paragraph,
            offset=offset,
            dx=base.dx if dx is None else dx,
            dy=base.dy if dy is None else dy,
            wrap=base.wrap if wrap is None else wrap,
            gap=base.gap if gap is None else gap,
        )
        anchor.check_wrap()
    except ValueError as caught:
        raise RequestError("bad_request", message_of(caught)) from None
    return anchor.to_data()


IN_TEXT = Placement(
    new="paragraph:str offset:int wrap:str? gap:int?",
    move="paragraph:str offset:int dx:int? dy:int?",
    frame="",
    anchor=_at_character,
    says={
        "add_image": "It hangs from character `offset` of the paragraph `paragraph`. `wrap` says how the text flows "
        "round it (`over`, `around`, `above-below` or `behind`; it floats `over` the text when left out) and `gap` "
        "how far the text keeps from it, in CSS pixels.",
        "add_object": "It hangs from character `offset` of the paragraph `paragraph`; `wrap` and `gap` say how the "
        "text flows round it, as for `add_image`.",
        "move_object": "Hang it from another character: `offset` of the paragraph `paragraph`, and float it at `dx` to "
        "the right and `dy` down from there (CSS pixels; negative goes left and up). Leave `dx` or `dy` out and the "
        "object keeps the offset it has.",
        "resize_object": "Sizes are CSS pixels; it keeps hanging from where it hangs.",
        "rotate_object": "The character it hangs from and the offset from it stay.",
    },
)


#: The style the words of a new text box and a new shape start in: the text's body style, and a shape's label.
BOX_WORDS = {"text": DEFAULT_STYLE, "shape": "shape-label"}
add_object_methods(composes_methods, model_of=_text, placement=IN_TEXT)
add_container_methods(composes_methods, model_of=_text, placement=IN_TEXT)
add_shape_methods(
    composes_methods, model_of=_text, library=ShapeLibrary.load(), placement=IN_TEXT, words_styles=BOX_WORDS
)


@composes_methods.method("set_wrap", "id:str wrap:str gap:int? base:revision?", write=True)
def _set_wrap(ctx, *, id, wrap, gap, base):  # noqa: A002 - the wire name
    """How the text flows round an object (D1061, D1064): `over` (the words do not give way), `around` (they
    keep to the sides), `above-below` (they stop above it and go on below) or `behind` (the object is drawn
    under the words). `gap` is how far the words keep from it, in CSS pixels, 0 to 200; leave it out to keep
    the gap the object has (8 for a new one). Where the object hangs and its size do not change. One step, so
    one undo takes back one press of the key that cycles the modes."""
    held = _text(ctx).get_object(id).anchor
    anchor = replace(held, wrap=wrap, gap=held.gap if gap is None else gap)
    try:
        anchor.check_wrap()
    except ValueError as caught:
        raise RequestError("bad_request", message_of(caught)) from None
    return done(ctx, SetObjectWrap(id, anchor.wrap, anchor.gap), base)


add_table_methods(composes_methods, model_of=_text, placement=IN_TEXT)


def composes_methods_with(library: ShapeLibrary) -> MethodTable:
    """The method table of texts on a server whose shape library is ``library``."""
    table = composes_methods.extended()
    add_shape_methods(table, model_of=_text, library=library, placement=IN_TEXT, words_styles=BOX_WORDS)
    return table
