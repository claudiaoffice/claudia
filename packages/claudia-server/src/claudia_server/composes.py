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
    ChangeStyle,
    Command,
    CreateStyle,
    RenameStyle,
    StyleDef,
    format_css,
    parse_css,
    validate_css,
)

from .protocol import Context, RequestError, core_methods

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
    return {"revision": _rev(ctx), "styles": model.styles.views(), "blocks": [b.to_data() for b in model.blocks]}


@composes_methods.method("styles")
def _styles(ctx):
    """The styles as `{id, name, purpose, based_on, css, computed, to_name}`. `css` is what the style sets itself,
    `computed` the CSS it really has once its parents (`based_on`) are taken in. `to_name` is true for a style that
    was made by deviating and still has the name it was given (E9.7)."""
    return _text(ctx).styles.views()


@composes_methods.method("suggestions")
def _suggestions(ctx):
    """The suggestions that are still open, as `{id, author, block, start, end, original, replacement, reason,
    state, outdated}`. `replacement` is null for a remark. An outdated one cannot be accepted any more."""
    return _text(ctx).visible_suggestions()


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
def _own_css(properties: dict | None, text: str | None) -> dict[str, str] | None:
    """The CSS a request gave, as a dictionary: from `set` or from the text of a style; ``None`` if it gave neither."""
    if properties is not None and text is not None:
        raise RequestError("bad_request", "give the CSS as set properties or as text, not both")
    if text is None:
        return properties
    css, problems = parse_css(text)
    if problems:
        raise RequestError("command_error", "; ".join(p.message for p in problems))
    return css


@composes_methods.method("change_style", "style:str set:dict? unset:list? text:text? base:revision?", write=True)
def _change_style(ctx, *, style, set, unset, text, base):
    """Change a style for every paragraph that has it (and for the styles based on it, where they do not set the
    property themselves). Either `set` properties (`{"color": "#5B4BC4"}`) and `unset` property names, or `text`,
    the complete CSS text of the style, which replaces what it sets. `command_error` names every property that is not
    allowed. A change that changes nothing is not an edit (`revision` is then null)."""
    _people_only(ctx)
    known = _text(ctx).styles
    try:
        own = known.get(style).css
    except KeyError as exc:
        raise RequestError("command_error", exc.args[0]) from None
    wanted = _own_css(set, text)
    if text is not None:
        assert wanted is not None
        change = {name: value for name, value in wanted.items() if own.get(name) != value}
        removed = tuple(name for name in own if name not in wanted)
    else:
        if unset is not None and not all(isinstance(name, str) for name in unset):
            raise RequestError("bad_request", "unset must be a list of property names")
        removed = tuple(name for name in dict.fromkeys(unset or ()) if name in own)
        change = validate_css(wanted or {})
        change = {name: value for name, value in change.items() if own.get(name) != value}
    if not change and not removed:
        return {"revision": _rev(ctx)}
    applied = ctx.document.execute(ChangeStyle(style, change, removed), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


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
    given = validate_css(_own_css(set, text) or {})
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


@composes_methods.method("rename_style", "style:str name:str base:revision?", write=True)
def _rename_style(ctx, *, style, name, base):
    """Give a style the name its maker chose. That ends the invitation to name it. `command_error` if another style
    has that name (in any letters) or the name is empty, long, or more than one line."""
    _people_only(ctx)
    applied = ctx.document.execute(RenameStyle(style, name, False), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


@composes_methods.method("check_css", "text:text")
def _check_css(ctx, *, text):
    """Check the CSS text of a style without changing anything (so viewers may ask, and a client can check while
    somebody types): `{css, text, problems}` with the valid declarations, the same in the fixed order a style is written
    in, and a problem `{line, property, message}` for each line that is not allowed."""
    css, problems = parse_css(text)
    return {"css": css, "text": format_css(css), "problems": [p.to_data() for p in problems]}


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
