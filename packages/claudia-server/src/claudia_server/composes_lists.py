"""The methods that make and shape lists in a text (E9.21).

* ``make_list(blocks, scheme)``: bullets or numbers for paragraphs, or (``scheme`` null) none. Asking for what the
  paragraphs already are takes them out of their list, asking for the other kind of a whole list changes its scheme,
  anything else starts a new list at the levels the paragraphs have;
* ``indent_item(blocks, by)``: move items one level in (``1``) or out (``-1``);
* ``continue_list(block)``: let the list of ``block`` go on where the nearest earlier list of its kind ends;
* ``list_start(list, start)``: the number a list's first level starts at.

Each is one request and so one step in the history, and none is open to the assistant (D63): the structure of a text
is written by people, like its words. Which Enter, Tab or Backspace does is the session's rule, built from these.
"""

from __future__ import annotations

from collections.abc import Callable

from claudia_composes import SetListItem, TextModel
from claudia_core import (
    SCHEMES,
    Batch,
    ChangeList,
    Command,
    CreateList,
    ListDef,
    ListItem,
    RemoveList,
    Revision,
)

from .i18n import msg
from .protocol import Context, MethodTable, RequestError

MAX_LISTED = 2_000  # paragraphs one request may touch


def _blocks(model: TextModel, ids: list) -> list[str]:
    """The paragraphs these ids name, in the order of the text and each once."""
    if not ids or len(ids) > MAX_LISTED or not all(isinstance(i, str) for i in ids):
        raise RequestError("bad_request", msg("blocks must be a list of 1 to {limit} paragraph ids", limit=MAX_LISTED))
    wanted = set(ids)
    for block_id in wanted:
        model.block(block_id)  # KeyError -> command_error: the paragraph must exist
    return [b.id for b in model.blocks if b.id in wanted]


def _revision(ctx: Context) -> dict:
    revision = ctx.document.revision
    return {"revision": None if revision is None else revision.to_data()}


def _run(ctx: Context, commands: list[Command], name: str, base: Revision | None) -> dict:
    applied = ctx.document.execute(
        commands[0] if len(commands) == 1 else Batch(tuple(commands), name), author=ctx.user, base=base
    )
    return {"revision": applied.revision.to_data()}


def _plan_make_list(model: TextModel, ids: list[str], scheme: str | None) -> tuple[list[Command], str]:
    items = {i: model.block(i).item for i in ids}
    if scheme is None:
        return [SetListItem(i, None) for i, item in items.items() if item is not None], "Remove list"
    if scheme not in SCHEMES:
        raise RequestError(
            "command_error",
            msg("there is no list scheme {scheme!r}; there are {schemes}", scheme=scheme, schemes=", ".join(SCHEMES)),
        )
    name = "Numbered list" if SCHEMES[scheme].counts else "Bulleted list"
    held = [item for item in items.values() if item is not None]
    if len(held) == len(items) and all(model.lists.get(item.list).scheme == scheme for item in held):
        return [SetListItem(i, None) for i in items], "Remove list"  # asked for what they are: take them out
    if len(held) == len(items) and len({item.list for item in held}) == 1:
        (only,) = {item.list for item in held}
        whole = {b.id for b in model.blocks if b.item is not None and b.item.list == only}
        if whole == set(items):  # exactly that list: it is the list that changes, not its items
            return [ChangeList(ListDef(only, scheme, model.lists.get(only).start, model.lists.get(only).name))], name
    new = ListDef(model.lists.unique_id(), scheme)
    commands: list[Command] = [CreateList(new)]
    commands += [SetListItem(i, ListItem(new.id, 0 if item is None else item.level)) for i, item in items.items()]
    return commands, name


def _plan_indent(model: TextModel, ids: list[str], by: int) -> list[Command]:
    """One level for every item, taken from the top: a selection moves in together, and an item may rely on the
    one above it having moved."""
    levels = {b.id: b.item.level for b in model.blocks if b.item is not None}
    lists = {b.id: b.item.list for b in model.blocks if b.item is not None}
    order = [b.id for b in model.blocks]
    commands: list[Command] = []
    for block_id in ids:
        if block_id not in levels:
            continue
        level = levels[block_id]
        if by > 0:
            at = order.index(block_id)
            above = order[at - 1] if at else None
            # no deeper than one below the paragraph above, and a list's first item stays where it is
            ceiling = levels[above] + 1 if above in levels and lists[above] == lists[block_id] else 0
            target = min(level + 1, ceiling) if ceiling > level else level
        else:
            target = max(level - 1, 0)
        if target != level:
            levels[block_id] = target
            commands.append(SetListItem(block_id, ListItem(lists[block_id], target)))
    return commands


def _plan_continue(model: TextModel, block_id: str) -> list[Command]:
    item = model.block(block_id).item
    if item is None:
        raise RequestError("command_error", msg("this paragraph is not a list item"))
    scheme = model.lists.get(item.list).scheme
    members = [b for b in model.blocks if b.item is not None and b.item.list == item.list]
    first = model.index_of(members[0].id)
    before = [b for b in model.blocks[:first] if b.item is not None and b.item.list != item.list]
    target = next((b.item.list for b in reversed(before) if model.lists.get(b.item.list).scheme == scheme), None)  # type: ignore[union-attr]
    if target is None:
        raise RequestError("command_error", msg("there is no earlier list of this kind to continue"))
    moved: list[Command] = [SetListItem(b.id, ListItem(target, b.item.level)) for b in members]  # type: ignore[union-attr]
    return [*moved, RemoveList(item.list)]


def add_list_methods(table: MethodTable, *, guard: Callable[[Context], None]) -> None:
    """Add the list methods to the text app's method table; ``guard`` refuses the assistant."""

    @table.method("make_list", "blocks:list scheme:str? base:revision?", write=True)
    def _make_list(ctx, *, blocks, scheme, base):
        """Make the paragraphs `blocks` bullets (`scheme` `"bullets"`) or numbers (`"numbers"`), or plain again
        (`scheme` null). Paragraphs that already are that kind leave their list; a whole list asked for in the other
        kind changes its scheme; otherwise the paragraphs become a new list, at the levels they had. One step.
        Returns `{revision}`."""
        guard(ctx)
        model = ctx.document.model
        assert isinstance(model, TextModel)
        commands, name = _plan_make_list(model, _blocks(model, blocks), scheme)
        if not commands:
            return _revision(ctx)
        return _run(ctx, commands, name, base)

    @table.method("indent_item", "blocks:list by:int base:revision?", write=True)
    def _indent_item(ctx, *, blocks, by, base):
        """Move the list items among `blocks` one level in (`by` 1) or out (`by` -1). An item goes no deeper than
        one below the paragraph above it, and a list's first item cannot go in. Paragraphs that are no items, and
        items that cannot move, stay. Returns `{revision, changed}`: how many items moved (none: no step is made)."""
        guard(ctx)
        if by not in (1, -1):
            raise RequestError("bad_request", msg("by is 1 (in) or -1 (out)"))
        model = ctx.document.model
        assert isinstance(model, TextModel)
        commands = _plan_indent(model, _blocks(model, blocks), by)
        if not commands:
            return {**_revision(ctx), "changed": 0}
        return {**_run(ctx, commands, "Indent list" if by > 0 else "Outdent list", base), "changed": len(commands)}

    @table.method("continue_list", "block:str base:revision?", write=True)
    def _continue_list(ctx, *, block, base):
        """Let the list that `block` is an item of go on where the nearest earlier list of the same kind ends: its
        items join that list and keep their levels. `command_error` if `block` is no item or there is no such list."""
        guard(ctx)
        model = ctx.document.model
        assert isinstance(model, TextModel)
        return _run(ctx, _plan_continue(model, block), "Continue list", base)

    @table.method("list_start", "list:str start:int base:revision?", write=True)
    def _list_start(ctx, *, list, start, base):  # noqa: A002  (the parameter is named as it is on the wire)
        """Number the first level of the list `list` from `start` on (1 to 999999)."""
        guard(ctx)
        model = ctx.document.model
        assert isinstance(model, TextModel)
        try:
            current = model.lists.get(list)
        except KeyError as exc:
            raise RequestError("command_error", exc.args[0]) from None
        return _run(ctx, [ChangeList(ListDef(current.id, current.scheme, start, current.name))], "List start", base)
