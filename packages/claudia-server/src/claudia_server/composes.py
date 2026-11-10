"""The methods of the text app: what a text view needs to show paragraphs, take what people type, follow cursors (E9).

``composes_methods`` is ``core_methods`` plus

* ``blocks`` and ``suggestions``: the document, to load it;
* ``replace_text``: the one way people write. It replaces a range (it may span paragraphs) by some text, and a line
  break in the text starts a new paragraph. A single request is a single step to undo;
* ``set_style``: give a paragraph a named style (D62);
* ``styles``, ``change_style``, ``deviate_style``, ``rename_style`` and ``check_css``: the styles are CSS in the
  document (E1.10, D73). Changing a style changes every paragraph that has it; deviating makes a new style, with a
  provisional name, from an old one and applies it, in one step (D75); naming ends the invitation to name it;
* ``look`` and ``hold``: where my cursor is. ``hold`` also locks the ± n words around it for everybody else (D11);
* ``suggest`` (the assistant only), ``accept_suggestion`` and ``reject_suggestion`` (D63).

The assistant has no direct write path into the text: ``replace_text`` and ``set_style`` refuse it, it can only
suggest, and people accept (D63).
"""

from __future__ import annotations

from claudia_composes_io import text_to_docx

from claudia_composes import (
    AcceptSuggestion,
    DeleteText,
    InsertText,
    JoinBlocks,
    ProposeSuggestion,
    ResolveSuggestion,
    SetStyle,
    SplitBlock,
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
    validate_css,
)

from .office_export import office_export
from .protocol import Context, RequestError, core_methods
from .styles import add_style_methods, own_css

MAX_ZONE_WORDS = 10  # the widest ± n words zone a cursor may ask for
ZONE_SECONDS = 15.0  # a held zone lapses this long after its owner was last active
MAX_NEW_PARAGRAPHS = 2_000  # line breaks in one piece of typed or pasted text
MAX_BLOCKS = 50_000  # paragraphs in a document
MAX_STYLED_BLOCKS = 2_000  # paragraphs one deviation may apply its new style to

composes_methods = core_methods.extended()


def _text(ctx: Context) -> TextModel:
    model = ctx.document.model
    if not isinstance(model, TextModel):
        raise RequestError("command_error", "this document is not a text")
    return model


def _people_only(ctx: Context) -> None:
    """The assistant suggests; it does not write (D63)."""
    if ctx.account.system:
        raise RequestError("forbidden", "the assistant can only make suggestions; people write the text")


add_style_methods(composes_methods, guard=_people_only)


def _rev(ctx: Context) -> str | None:
    revision = ctx.document.revision
    return None if revision is None else revision.to_data()


def _inside(model: TextModel, block: str, offset: int, what: str = "offset") -> int:
    if not 0 <= offset <= len(model.block(block).text):
        raise RequestError("command_error", f"{what} is outside the paragraph")
    return offset


# ------------------------------------------------------------------------------ reading
@composes_methods.method("blocks")
def _blocks(ctx):
    """The paragraphs in order, each as `{id, style, text, runs}` (`runs` are `[length, author, via]`: who wrote
    which stretch), the styles (see `styles`), and the revision they are at."""
    model = _text(ctx)
    return {
        "revision": _rev(ctx),
        "styles": model.styles.views(model.palette.colours()),
        "blocks": [b.to_data() for b in model.blocks],
    }


@composes_methods.method("suggestions")
def _suggestions(ctx):
    """The suggestions that are still open, as `{id, author, block, start, end, original, replacement, reason,
    state, outdated}`. `replacement` is null for a remark. An outdated one cannot be accepted any more."""
    return _text(ctx).visible_suggestions()


@composes_methods.method("export_office", "format:str")
def _export_office(ctx, *, format):
    """The document's current content as bytes of a Word file (`format` must be `"docx"`, the only one so far),
    wrapped for the wire as `{format, content_type, data}` (`data` base64). No tracked changes: open suggestions
    are not written in, same as `export_content` leaves out the history and the chat (D212)."""
    if format != "docx":
        raise RequestError("bad_request", 'export_office: format must be "docx"')
    return office_export(format, text_to_docx(_text(ctx), track_suggestions=False))


# ------------------------------------------------------------------------------ writing
def edit_plan(
    model: TextModel, first: str, start: int, *, last: str, end: int, text: str
) -> tuple[list[Command], tuple[str, int]]:
    """The commands that replace the text from ``first:start`` to ``last:end`` by ``text``, and where the cursor
    ends up (``(paragraph, offset)``). Paragraphs in between go away; the last one's rest is joined to the first."""
    i, j = model.index_of(first), model.index_of(last)
    if j < i or (i == j and end < start):
        raise RequestError("command_error", "the range ends before it starts")
    _inside(model, first, start, "start")
    _inside(model, last, end, "end")
    lines = text.split("\n")
    if len(lines) - 1 > MAX_NEW_PARAGRAPHS or len(model.blocks) + len(lines) > MAX_BLOCKS:
        raise RequestError("command_error", "that would make too many paragraphs")
    blocks = model.blocks
    commands: list[Command] = []
    if i == j:
        if end > start:
            commands.append(DeleteText(first, start, end - start))
        tail = len(blocks[i].text) - end
    else:
        tail = len(blocks[j].text) - end
        if len(blocks[i].text) > start:
            commands.append(DeleteText(first, start, len(blocks[i].text) - start))
        for middle in blocks[i + 1 : j]:
            if middle.text:
                commands.append(DeleteText(middle.id, 0, len(middle.text)))
            commands.append(JoinBlocks(middle.id, first, start))
        if end > 0:
            commands.append(DeleteText(last, 0, end))
        commands.append(JoinBlocks(last, first, start))
    cursor, offset, style = first, start, blocks[i].style
    fresh = iter(model.fresh_ids(len(lines) - 1))
    for n, line in enumerate(lines):
        if n:
            style = next_style(model.styles, style) if tail == 0 else style
            new = next(fresh)
            commands.append(SplitBlock(cursor, offset, new, style))
            cursor, offset = new, 0
        if line:
            commands.append(InsertText(cursor, offset, line))
            offset += len(line)
    return commands, (cursor, offset)


def _named(text: str, lines: int) -> str:
    if not text:
        return "deleted text"
    return f"inserted {lines} paragraphs" if lines > 1 else "replaced text"


@composes_methods.method(
    "replace_text", "block:str start:int end_block:str end:int text:text base:revision?", write=True
)
def _replace_text(ctx, *, block, start, end_block, end, text, base):
    """Replace the text from `block`:`start` up to `end_block`:`end` by `text` (offsets count characters). A line
    break in `text` starts a new paragraph; a range that spans paragraphs joins what is left of them. Typing is an
    empty range, deleting is empty text. One request is one step in the history. Returns the revision and where the
    cursor ends up: `{revision, block, offset}`. Refused with `locked` where a colleague holds the text."""
    _people_only(ctx)
    commands, (cursor, offset) = edit_plan(_text(ctx), block, start, last=end_block, end=end, text=text)
    result = {"block": cursor, "offset": offset}
    if not commands:
        return {"revision": _rev(ctx), **result}
    command = commands[0] if len(commands) == 1 else Batch(tuple(commands), _named(text, text.count("\n") + 1))
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"revision": applied.revision.to_data(), **result}


@composes_methods.method("set_style", "block:str style:str base:revision?", write=True)
def _set_style(ctx, *, block, style, base):
    """Give the paragraph `block` the style named `style` (one of the ids `blocks` lists)."""
    _people_only(ctx)
    applied = ctx.document.execute(SetStyle(block, style), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


# ------------------------------------------------------------------------------ styles (E1.10, E9.7)
# ``styles``, ``change_style``, ``rename_style``, ``check_css``, the palette and ``set_object_style`` are the
# same in every app and come from ``.styles``. Only the one that names paragraphs stays here.
@composes_methods.method("deviate_style", "parent:str blocks:list set:dict? text:text? base:revision?", write=True)
def _deviate_style(ctx, *, parent, blocks, set, text, base):
    """Make a new style from `parent` that differs in the CSS given (`set` properties, or `text`) and give it to the
    paragraphs `blocks`, in one step. It gets a provisional name such as “Heading 1 (changed)” and is marked `to_name`
    until somebody names it (D75). Returns `{style, name, revision}`. `command_error` if nothing differs from the
    parent."""
    _people_only(ctx)
    model = _text(ctx)
    if len(blocks) > MAX_STYLED_BLOCKS or not all(isinstance(b, str) for b in blocks):
        raise RequestError("bad_request", f"blocks must be a list of at most {MAX_STYLED_BLOCKS} paragraph ids")
    try:
        inherited = model.styles.computed(parent)
    except KeyError as exc:
        raise RequestError("command_error", exc.args[0]) from None
    for block in blocks:
        model.block(block)  # KeyError -> command_error: the paragraph must exist
    given = validate_css(own_css(set, text) or {})
    own = {name: value for name, value in given.items() if inherited.get(name) != value}
    if not own:
        raise RequestError(
            "command_error", "the new style would look just like “" + model.styles.get(parent).name + "”"
        )
    name = model.styles.provisional_name(parent)
    created = StyleDef(model.styles.unique_id(name), name, "", parent, own, to_name=True)
    commands: list[Command] = [CreateStyle(created), *(SetStyle(block, created.id) for block in blocks)]
    applied = ctx.document.execute(Batch(tuple(commands), "Deviate style"), author=ctx.user, base=base)
    return {"style": created.id, "name": name, "revision": applied.revision.to_data()}


# ------------------------------------------------------------------------------ cursors and zones
def _regions_at(ctx: Context, block: str, offset: int, words: int) -> list[TextRange]:
    model = _text(ctx)
    if not 0 <= words <= MAX_ZONE_WORDS:
        raise RequestError("bad_request", f"words must be from 0 to {MAX_ZONE_WORDS}")
    _inside(model, block, offset)
    zone = word_window(model.block(block).text, offset, words, block)
    return [zone, TextRange(block, offset, offset)]


@composes_methods.method("look", "block:str offset:int words:int=3")
def _look(ctx, *, block, offset, words):
    """Show where my cursor is: the others see a caret and the ± `words` words around it. Locks nothing, so viewers
    may use it. The others receive an `ephemeral` event of kind `presence` with two text regions: the zone and the
    caret (an empty one)."""
    ctx.document.show_presence(ctx.user, _regions_at(ctx, block, offset, words))
    return {}


@composes_methods.method("hold", "block:str offset:int words:int=3", write=True)
def _hold(ctx, *, block, offset, words):
    """Show my cursor and lock the ± `words` words around it (D11): colleagues cannot change that text, nor undo into
    it, until I move on, call `unlock`, or have been quiet for a few seconds (renew by calling `hold` again).
    `locked` if a colleague holds any of it."""
    ctx.document.lock(ctx.user, _regions_at(ctx, block, offset, words), min(ctx.lock_seconds, ZONE_SECONDS))
    return {}


# ------------------------------------------------------------------------------ suggestions (D63)
@composes_methods.method(
    "suggest", "block:str start:int end:int reason:text replacement:text? base:revision?", write=True
)
def _suggest(ctx, *, block, start, end, reason, replacement, base):
    """The assistant only: propose that the text from `start` up to `end` of `block` be replaced by `replacement`
    (empty text proposes a deletion), or, with no `replacement`, remark on it. Changes no text. Returns the id."""
    if not ctx.account.system:
        raise RequestError("forbidden", "only the assistant makes suggestions")
    model = _text(ctx)
    original = model.block(block).text[start:end]
    command = ProposeSuggestion(model.fresh_suggestion_id(), block, start, end, original, replacement, reason)
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"suggestion": command.id, "revision": applied.revision.to_data()}


@composes_methods.method("accept_suggestion", "id:str base:revision?", write=True)
def _accept(ctx, *, id, base):
    """Accept a suggestion: I replace the text, and I am its author; the suggestion's author is recorded as the one it
    came through. `command_error` if it is not open any more, is a remark, or the text under it has changed."""
    _people_only(ctx)
    suggestion = _text(ctx).suggestion(id)
    if suggestion.replacement is None:
        raise RequestError("command_error", "a remark suggests no change; dismiss it instead")
    anchor = suggestion.anchor
    command = AcceptSuggestion(id, anchor.block, anchor.start, anchor.end, suggestion.replacement, suggestion.author)
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@composes_methods.method("reject_suggestion", "id:str base:revision?", write=True)
def _reject(ctx, *, id, base):
    """Reject a suggestion, or dismiss a remark. Logged; undo reopens it."""
    _people_only(ctx)
    suggestion = _text(ctx).suggestion(id)
    if suggestion.state != "open":
        raise RequestError("command_error", "this suggestion is not open any more")
    state = "dismissed" if suggestion.replacement is None else "rejected"
    applied = ctx.document.execute(ResolveSuggestion(id, state), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}
