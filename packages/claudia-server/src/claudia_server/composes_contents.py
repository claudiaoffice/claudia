"""Putting a table of contents into a text and taking it out again (E9.31, step E): composes' own part of what
:mod:`claudia_server.structure_methods` shares (``contents``, ``set_contents``).

* ``insert_contents(paragraph)``: after the paragraph ``paragraph``, a "Contents" paragraph in the style Contents Title
(its
  words are the author's to change; the style has no heading level, so the table does not list itself) and the
  table itself, a generated paragraph. One step.
* ``remove_contents(paragraph)``: the table goes; the "Contents" paragraph above it stays, as the author's. One step.

Both are open to the assistant only through its allow-list (SEC-10, D640), which does not name them in this round.
"""

from __future__ import annotations

from claudia_composes import DEFAULT_STYLE, InsertText, JoinParagraphs, SplitParagraph, TextModel
from claudia_core import Batch, Command, SetGenerated, SetListItem, Toc

from .i18n import msg
from .protocol import Context, MethodTable, RequestError
from .wire import done

#: The style of the heading above a table of contents; a text from before it was built in has body text instead.
CONTENTS_TITLE = "contents-title"


def _text(ctx: Context) -> TextModel:
    model = ctx.document.model
    if not isinstance(model, TextModel):
        raise RequestError("command_error", msg("this document is not a text"))
    return model


def _paragraph(model: TextModel, paragraph: str):  # noqa: ANN202 (a Paragraph)
    try:
        return model.paragraph(paragraph)
    except KeyError:
        raise RequestError("command_error", msg("no paragraph {id!r}", id=paragraph)) from None


def plan_insert(model: TextModel, paragraph: str, words: str, options: Toc) -> tuple[list[Command], str]:
    """The commands that put a titled table of contents after ``paragraph``, and the id of the table."""
    after = _paragraph(model, paragraph)
    if after.generated is not None:
        raise RequestError("command_error", msg("there is a table of contents here already"))
    title, table = model.fresh_ids(2)
    style = CONTENTS_TITLE if CONTENTS_TITLE in model.styles else DEFAULT_STYLE
    commands: list[Command] = [SplitParagraph(paragraph, len(after.text), title, style)]
    if after.item is not None:
        commands.append(SetListItem(title, None))  # a split keeps the list; the title is no item
    commands += [
        InsertText(title, 0, words),
        SplitParagraph(title, len(words), table, DEFAULT_STYLE),
        SetGenerated(table, options),
    ]
    return commands, table


def plan_remove(model: TextModel, paragraph: str) -> list[Command]:
    """The commands that take the table of contents ``paragraph`` away: it becomes a plain paragraph, which is joined to
    the paragraph before it (the first paragraph of a text stays, empty)."""
    table = _paragraph(model, paragraph)
    if table.generated is None:
        raise RequestError("command_error", msg("this paragraph is not a table of contents"))
    commands: list[Command] = [SetGenerated(paragraph, None)]
    at = model.index_of(paragraph)
    if at > 0:
        before = model.paragraphs[at - 1]
        commands.append(JoinParagraphs(paragraph, before.id, len(before.text)))
    return commands


def add_contents_methods(table: MethodTable) -> None:
    """Add ``insert_contents`` and ``remove_contents`` to composes' method table."""

    @table.method("insert_contents", "paragraph:str base:revision?", write=True)
    def _insert_contents(ctx, *, paragraph, base):
        """Put a table of contents after the paragraph `paragraph`: a paragraph "Contents" (in the reader's language) in
        the style Contents Title, then the table, listing the headings of levels 1 to 3 with their numbers. One step.
        Returns `{revision, paragraph}`, the id of the table. `command_error` on a table of contents."""
        model = _text(ctx)
        commands, made = plan_insert(model, paragraph, msg("Contents"), Toc())
        return done(ctx, Batch(tuple(commands), "Table of contents"), base, paragraph=made)

    @table.method("remove_contents", "paragraph:str base:revision?", write=True)
    def _remove_contents(ctx, *, paragraph, base):
        """Take the table of contents `paragraph` away; the paragraph above it stays. One step. `command_error` for a
        paragraph that is not a table of contents."""
        model = _text(ctx)
        return done(ctx, Batch(tuple(plan_remove(model, paragraph)), "Remove table of contents"), base)
