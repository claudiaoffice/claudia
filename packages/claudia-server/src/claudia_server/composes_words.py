"""Paragraphs and words by what they say: the text methods a language model can use (E7.10, D681).

A model cannot count characters reliably, so it cannot use ``replace_text`` or ``suggest``, which take offsets. These
methods name a paragraph by its id and the words in it by quoting them (``find``); ``occurrence`` picks one when the
words are there more than once, and an empty ``find`` means the paragraph's whole text. They are ordinary methods of
the text app, open to people and scripts as well:

* ``paragraphs`` and ``outline``: read the text in windows, and its headings;
* ``replace_words``: change the quoted words (a line break in the new text starts a new paragraph);
* ``add_paragraphs``: put new paragraphs after one, or at the start;
* ``suggest_words``: the assistant only, propose a change of the quoted words or remark on them, as ``suggest`` does
  (D262: the suggest mode of composes).

Which of them the assistant may call for whom is ``apps.MODEL_METHODS`` and the asker's mode and role (D261, D262),
checked at dispatch like every other write.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from functools import partial, update_wrapper

from claudia_composes import ProposeSuggestion, SetStyle, SplitBlock, TextModel
from claudia_core import Batch, Command

from .i18n import msg
from .protocol import Context, MethodTable, RequestError
from .wire import current_revision, done

MAX_READ = 50  # paragraphs one ``paragraphs`` answer holds at most
MAX_OUTLINE = 200  # headings one ``outline`` answer holds at most

#: ``edit_plan`` of :mod:`claudia_server.composes`: the commands that replace a range by some text, and the cursor.
type EditPlan = Callable[..., tuple[list[Command], tuple[str, int]]]


def _text(ctx: Context) -> TextModel:
    model = ctx.document.model
    if not isinstance(model, TextModel):
        raise RequestError("command_error", msg("this document is not a text"))
    return model


def _paragraph(model: TextModel, block: str) -> str:
    """The words of the paragraph ``block``, or of the box of a table if that is its id."""
    if model.is_entry(block):
        return model.entry_words(block).text
    try:
        return model.block(block).text
    except KeyError:
        raise RequestError("command_error", msg("there is no paragraph {block!r}", block=block)) from None


def locate(text: str, find: str, occurrence: int, block: str) -> tuple[int, int]:
    """Where the ``occurrence``-th (from 1) appearance of ``find`` is in ``text``; ``find`` empty is the whole text.
    ``RequestError`` that says what is there instead when it is not found."""
    if not find:
        return 0, len(text)
    if occurrence < 1:
        raise RequestError("bad_request", msg("occurrence counts from 1"))
    starts: list[int] = []
    at = text.find(find)
    while at >= 0:
        starts.append(at)
        at = text.find(find, at + len(find))
    if not starts:
        raise RequestError(
            "command_error",
            msg(
                "the words {find!r} are not in paragraph {block}; read it again and quote it exactly",
                find=find,
                block=block,
            ),
        )
    if occurrence > len(starts):
        raise RequestError(
            "command_error",
            msg(
                "{find!r} is {count} times in paragraph {block}, not {occurrence}",
                find=find,
                count=len(starts),
                block=block,
                occurrence=occurrence,
            ),
        )
    start = starts[occurrence - 1]
    return start, start + len(find)


def paragraph_view(model: TextModel, index: int, labels: dict) -> dict:
    """One paragraph as the reading methods give it: `{id, index, style, text}`, `label` (the marker drawn in front
    of a list item) and `name` when it has them."""
    block = model.blocks[index]
    view: dict = {"id": block.id, "index": index, "style": block.style, "text": block.text}
    if block.id in labels:
        view["label"] = labels[block.id].marker
    name = model.block_names.get(block.id)
    if name:
        view["name"] = name
    return view


def _paragraphs(ctx, *, first, count, containing):
    """Read paragraphs in order: from `first` (an id; the start if left out), at most `count` (up to 50). With
    `containing`, only the ones whose text contains those words, ignoring case. Returns `{revision, total,
    paragraphs, more}`: `total` paragraphs in the text, each as `{id, index, style, text, label?, name?}`, and
    `more` the id of the next paragraph that would follow, or null."""
    model = _text(ctx)
    if not 1 <= count <= MAX_READ:
        raise RequestError("bad_request", msg("count must be from 1 to {limit}", limit=MAX_READ))
    try:
        index = 0 if first is None else model.index_of(first)
    except KeyError:
        raise RequestError("command_error", msg("there is no paragraph {block!r}", block=first)) from None
    wanted = None if not containing else containing.casefold()
    labels = model.labels()
    found: list[dict] = []
    more = None
    for at in range(index, len(model.blocks)):
        block = model.blocks[at]
        if wanted is not None and wanted not in block.text.casefold():
            continue
        if len(found) == count:
            more = block.id
            break
        found.append(paragraph_view(model, at, labels))
    return {"revision": current_revision(ctx), "total": len(model.blocks), "paragraphs": found, "more": more}


def _outline(ctx):
    """The headings of the text in order (the paragraphs whose style is the title or a heading, or is based on
    one), as `{revision, total, headings}`: each heading as `paragraphs` gives a paragraph, `total` the number of
    paragraphs in the text. At most 200 headings."""
    model = _text(ctx)
    labels = model.labels()
    headings = [
        paragraph_view(model, at, labels)
        for at, block in enumerate(model.blocks)
        if model.block_kind(block) == "heading"
    ][:MAX_OUTLINE]
    return {"revision": current_revision(ctx), "total": len(model.blocks), "headings": headings}


def _replace_words(ctx, *, edit, block, find, text, occurrence, base):
    """Replace the words `find` of the paragraph `block` by `text`, quoting `find` exactly as it is written
    (`occurrence` picks one when they are there more than once, counting from 1). Leave `find` empty to replace
    the paragraph's whole text. A line break in `text` starts a new paragraph. One step in the history. Returns
    `{revision, block, offset}`, where the new text ends. `command_error` names what is wrong when the words
    are not there; `locked` where a colleague holds the text."""
    model = _text(ctx)
    start, end = locate(_paragraph(model, block), find, occurrence, block)
    commands, (cursor, offset) = edit(model, block, start, last=block, end=end, text=text)
    if not commands:
        return {"revision": current_revision(ctx), "block": cursor, "offset": offset}
    named = "replaced words" if "\n" not in text else "rewrote paragraphs"
    command = commands[0] if len(commands) == 1 else Batch(tuple(commands), named)
    return done(ctx, command, base, block=cursor, offset=offset)


def _add_paragraphs(ctx, *, edit, text, after, style, base):
    """Add new paragraphs, one per line of `text`, after the paragraph `after` (an id), or at the start of the
    text when `after` is left out. They get `style` (one of the paragraph styles `styles` lists) or, without it, the
    style that usually follows (body text after a heading; at the start, the first paragraph's). One step in the
    history. Returns `{revision, paragraphs}`: the ids of the new paragraphs."""
    model = _text(ctx)
    if not text:
        raise RequestError("bad_request", msg("there is no text to add"))
    if style is not None:
        try:
            model.check_style(style)
        except ValueError as exc:
            raise RequestError("command_error", str(exc)) from None
    if after is None:
        first = model.blocks[0].id
        commands, _ = edit(model, first, 0, last=first, end=0, text=text + "\n")
        splits = [c.new_id for c in commands if isinstance(c, SplitBlock)]
        added = [first, *splits[:-1]]  # the last split carries what the first paragraph held before
    else:
        length = len(_paragraph(model, after))
        commands, _ = edit(model, after, length, last=after, end=length, text="\n" + text)
        added = [c.new_id for c in commands if isinstance(c, SplitBlock)]
        if style is not None:
            commands = [replace(c, style=style) if isinstance(c, SplitBlock) else c for c in commands]
    if style is not None and after is None:
        commands += [SetStyle(block, style) for block in added]
    lines = len(added)
    command = Batch(tuple(commands), f"added {lines} paragraph{'s' if lines != 1 else ''}")
    return done(ctx, command, base, paragraphs=added)


def _suggest_words(ctx, *, block, find, reason, replacement, occurrence, base):
    """The assistant only: propose that the words `find` of the paragraph `block` (quoted exactly; `occurrence`
    as in `replace_words`; empty for the whole paragraph) be replaced by `replacement`, giving the `reason`; an
    empty `replacement` proposes a deletion, none at all makes it a remark. A suggestion stays inside its
    paragraph. Changes no text: people accept or reject it. Returns `{suggestion, revision}`."""
    if not ctx.account.system:
        raise RequestError("forbidden", msg("only the assistant makes suggestions"))
    if replacement is not None and "\n" in replacement:
        raise RequestError(
            "command_error", msg("a suggestion stays inside its paragraph; remark on new paragraphs instead")
        )
    model = _text(ctx)
    start, end = locate(_paragraph(model, block), find, occurrence, block)
    original = model.block(block).text[start:end]
    command = ProposeSuggestion(model.fresh_suggestion_id(), block, start, end, original, replacement, reason)
    return done(ctx, command, base, suggestion=command.id)


def add_word_methods(table: MethodTable, *, edit: EditPlan) -> None:
    """Add the methods of this module to the text app's ``table``; ``edit`` is its ``edit_plan``."""
    table.method("paragraphs", "first:str? count:int=20 containing:text?")(_paragraphs)
    table.method("outline")(_outline)
    table.method("replace_words", "block:str find:text text:text occurrence:int=1 base:revision?", write=True)(
        update_wrapper(partial(_replace_words, edit=edit), _replace_words)
    )
    table.method("add_paragraphs", "text:text after:str? style:str? base:revision?", write=True)(
        update_wrapper(partial(_add_paragraphs, edit=edit), _add_paragraphs)
    )
    table.method(
        "suggest_words",
        "block:str find:text reason:text replacement:text? occurrence:int=1 base:revision?",
        write=True,
    )(_suggest_words)


__all__ = ["add_word_methods", "locate", "paragraph_view"]
