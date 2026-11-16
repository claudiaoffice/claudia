"""The methods that make and shape lists, numbered headings and numbering schemes, the same in every app whose
paragraphs have a structure (E9.21, E9.22; step D of ``claudiaoffice-log/notes/text-structure-across-apps.md``).

They work on paragraph ids in the order the document is read (:class:`claudia_core.ParagraphHost`): the paragraphs of
a composes text and the words of the objects floating over it, or the words of the text boxes of a presentation,
slide by slide. So a list runs on from one text box to the next as it does from one paragraph to the next.

* ``lists``: the lists, the schemes and every label, for a client that does not load them with the document;
* ``make_list(blocks, scheme)``: bullets or numbers for paragraphs, or (``scheme`` null) none. Asking for what the
  paragraphs already are takes them out of their list, asking for the other kind of a whole list changes its scheme,
  anything else starts a new list at the levels the paragraphs have;
* ``indent_item(blocks, by)``: move items one level in (``1``) or out (``-1``);
* ``continue_list(block)``: let the list of ``block`` go on where the nearest earlier list of its kind ends;
* ``list_start(list, start)``: the number a list's first level starts at;
* ``number_headings(on)``: number every heading style in the list ``outline`` (scheme ``chapters``), or no longer;
  creates offers it as Number All Slide Titles, since a slide title is a heading;
* ``new_scheme``, ``change_scheme``, ``reset_scheme`` and ``remove_scheme``: the numbering manager (All Numbering).

Each is one request and so one step in the history; what the assistant may call is its allow-list (SEC-10, D640).
Which Enter, Tab or Backspace does is the session's rule, built from these.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from claudia_core import (
    NO_NUMBERING,
    Batch,
    ChangeList,
    ChangeScheme,
    Command,
    CreateList,
    CreateScheme,
    ItemHost,
    ListDef,
    ListItem,
    ParagraphHost,
    RemoveList,
    RemoveScheme,
    Revision,
    Scheme,
    SetListItem,
    SetStyleNumbering,
    TextStructure,
    builtin_scheme,
)

from .i18n import msg
from .protocol import Context, MethodTable, RequestError
from .wire import current_revision

MAX_LISTED = 2_000  # paragraphs one request may touch
#: The list Number Headings numbers the heading styles in, and the scheme it gets when it is made.
OUTLINE_LIST, OUTLINE_SCHEME = "outline", "chapters"


class _Host(ParagraphHost, ItemHost, Protocol):
    """What these methods need of a model: its paragraphs in reading order, their items and what is derived."""

    structure: TextStructure


def _host(ctx: Context) -> _Host:
    model = ctx.document.model
    needed = ("reading_order", "item_of", "put_item", "lists", "schemes", "styles")
    if not all(hasattr(model, name) for name in needed):
        raise RequestError("command_error", msg("this document has no lists"))
    return model  # type: ignore[return-value]


def _order(model: _Host) -> list[str]:
    return [placed.paragraph.id for placed in model.reading_order()]


def _items(model: _Host) -> dict[str, ListItem]:
    """Every paragraph's own item, by id, in reading order."""
    return {p.paragraph.id: p.paragraph.item for p in model.reading_order() if p.paragraph.item is not None}


def _paragraphs(model: _Host, ids: list) -> list[str]:
    """The paragraphs these ids name, in reading order and each once."""
    if not ids or len(ids) > MAX_LISTED or not all(isinstance(i, str) for i in ids):
        raise RequestError("bad_request", msg("blocks must be a list of 1 to {limit} paragraph ids", limit=MAX_LISTED))
    wanted = set(ids)
    order = _order(model)
    missing = wanted.difference(order)
    if missing:
        raise RequestError("command_error", msg("no paragraph {id!r}", id=sorted(missing)[0]))
    return [i for i in order if i in wanted]


def _revision(ctx: Context) -> dict:
    return {"revision": current_revision(ctx)}


def _run(ctx: Context, commands: list[Command], name: str, base: Revision | None) -> dict:
    applied = ctx.document.execute(
        commands[0] if len(commands) == 1 else Batch(tuple(commands), name), author=ctx.user, base=base
    )
    return {"revision": applied.revision.to_data()}


def _scheme(model: _Host, scheme_id: str) -> Scheme:
    try:
        return model.schemes.get(scheme_id)
    except KeyError as exc:
        raise RequestError("command_error", exc.args[0]) from None


# ------------------------------------------------------------------------------ planning
def _plan_make_list(model: _Host, ids: list[str], scheme: str | None) -> tuple[list[Command], str]:
    items = {i: model.item_of(i) for i in ids}
    if scheme is None:
        return [SetListItem(i, None) for i, item in items.items() if item is not None], "Remove list"
    name = "Numbered list" if _scheme(model, scheme).counts else "Bulleted list"
    held = [item for item in items.values() if item is not None]
    if len(held) == len(items) and all(model.lists.get(item.list).scheme == scheme for item in held):
        return [SetListItem(i, None) for i in items], "Remove list"  # asked for what they are: take them out
    if len(held) == len(items) and len({item.list for item in held}) == 1:
        (only,) = {item.list for item in held}
        whole = {i for i, item in _items(model).items() if item.list == only}
        if whole == set(items):  # exactly that list: it is the list that changes, not its items
            return [ChangeList(replace(model.lists.get(only), scheme=scheme))], name
    new = ListDef(model.lists.unique_id(), scheme)
    commands: list[Command] = [CreateList(new)]
    commands += [SetListItem(i, ListItem(new.id, 0 if item is None else item.level)) for i, item in items.items()]
    return commands, name


def _plan_indent(model: _Host, ids: list[str], by: int) -> list[Command]:
    """One level for every item, taken from the top: a selection moves in together, and an item may rely on the
    one above it having moved."""
    items = _items(model)
    levels = {i: item.level for i, item in items.items()}
    order = _order(model)
    commands: list[Command] = []
    for paragraph in ids:
        if paragraph not in levels:
            continue
        level = levels[paragraph]
        if by > 0:
            at = order.index(paragraph)
            above = order[at - 1] if at else None
            # no deeper than one below the paragraph above, and a list's first item stays where it is
            same = above is not None and above in levels and items[above].list == items[paragraph].list
            ceiling = levels[above] + 1 if same and above is not None else 0
            target = min(level + 1, ceiling) if ceiling > level else level
        else:
            target = max(level - 1, 0)
        if target != level:
            levels[paragraph] = target
            commands.append(SetListItem(paragraph, ListItem(items[paragraph].list, target)))
    return commands


def _plan_continue(model: _Host, paragraph: str) -> list[Command]:
    item = model.item_of(paragraph)
    if item is None:
        raise RequestError("command_error", msg("this paragraph is not a list item"))
    scheme = model.lists.get(item.list).scheme
    items = _items(model)
    members = [i for i, each in items.items() if each.list == item.list]
    order = _order(model)
    before = [items[i] for i in order[: order.index(members[0])] if i in items and items[i].list != item.list]
    target = next((each.list for each in reversed(before) if model.lists.get(each.list).scheme == scheme), None)
    if target is None:
        raise RequestError("command_error", msg("there is no earlier list of this kind to continue"))
    moved: list[Command] = [SetListItem(i, ListItem(target, items[i].level)) for i in members]
    return [*moved, RemoveList(item.list)]


def heading_styles(model: _Host) -> list[str]:
    """The paragraph styles that make their paragraphs headings of level 1 or deeper (the title, level 0, is never
    numbered), each with a level of its own."""
    return [
        style.id
        for style in model.styles
        if style.kind == "paragraph" and isinstance(style.heading_level, int) and style.heading_level >= 1
    ]


def _plan_number_headings(model: _Host, on: bool) -> list[Command]:
    styles = heading_styles(model)
    if not on:
        own = [s for s in styles if model.styles.get(s).numbering not in (None, NO_NUMBERING)]
        return [SetStyleNumbering(s, None) for s in own]
    commands: list[Command] = []
    if OUTLINE_LIST not in model.lists:
        if OUTLINE_SCHEME not in model.schemes:
            chapters = builtin_scheme(OUTLINE_SCHEME)
            assert chapters is not None  # a built-in scheme
            commands.append(CreateScheme(chapters))
        commands.append(CreateList(ListDef(OUTLINE_LIST, OUTLINE_SCHEME, name="Outline")))
    commands += [SetStyleNumbering(s, OUTLINE_LIST) for s in styles if model.styles.numbering(s) is None]
    return commands


def _scheme_from(data: object) -> Scheme:
    try:
        scheme = Scheme.from_data(data)  # type: ignore[arg-type]
        scheme.check()
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise RequestError("command_error", msg("not a numbering scheme: {reason}", reason=exc)) from None
    return scheme


# ------------------------------------------------------------------------------ the methods
def add_structure_methods(table: MethodTable) -> None:
    """Add the methods of lists, numbered headings and schemes to an app's method table."""
    _add_list_methods(table)
    _add_scheme_methods(table)


def _add_list_methods(table: MethodTable) -> None:
    @table.method("lists")
    def _lists(ctx):
        """The lists (`{id, scheme, start, name}`), the schemes (`{id, name, kind, levels, indent, gap}`, a level being
        `{format, bullet, before, after, from_level}`), and `labels`: by paragraph id, what is drawn in front of each
        list item and numbered heading (`{marker, path, number}`), and the `revision` they are at."""
        model = _host(ctx)
        return {
            "revision": current_revision(ctx),
            "lists": model.lists.to_data(),
            "schemes": model.schemes.to_data(),
            "labels": {paragraph: label.to_data() for paragraph, label in model.structure.labels().items()},
        }

    @table.method("make_list", "blocks:list scheme:str? base:revision?", write=True)
    def _make_list(ctx, *, blocks, scheme, base):
        """Make the paragraphs `blocks` (paragraph ids: paragraphs of a text, or the objects whose words they are)
        bullets (`scheme` `"bullets"`), numbers (`"numbers"`, or any scheme of the document), or plain again (`scheme`
        null). Paragraphs that already are that kind leave their list; a whole list asked for in another scheme
        changes its scheme; otherwise the paragraphs become a new list, at the levels they had. One step. Returns
        `{revision}`."""
        model = _host(ctx)
        commands, name = _plan_make_list(model, _paragraphs(model, blocks), scheme)
        if not commands:
            return _revision(ctx)
        return _run(ctx, commands, name, base)

    @table.method("indent_item", "blocks:list by:int base:revision?", write=True)
    def _indent_item(ctx, *, blocks, by, base):
        """Move the list items among `blocks` one level in (`by` 1) or out (`by` -1). An item goes no deeper than
        one below the paragraph read before it, and a list's first item cannot go in. Paragraphs that are no items,
        and items that cannot move, stay. Returns `{revision, changed}`: how many items moved (none: no step)."""
        if by not in (1, -1):
            raise RequestError("bad_request", msg("by is 1 (in) or -1 (out)"))
        model = _host(ctx)
        commands = _plan_indent(model, _paragraphs(model, blocks), by)
        if not commands:
            return {**_revision(ctx), "changed": 0}
        return {**_run(ctx, commands, "Indent list" if by > 0 else "Outdent list", base), "changed": len(commands)}

    @table.method("continue_list", "block:str base:revision?", write=True)
    def _continue_list(ctx, *, block, base):
        """Let the list that `block` is an item of go on where the nearest earlier list of the same scheme ends: its
        items join that list and keep their levels. `command_error` if `block` is no item or there is no such list."""
        model = _host(ctx)
        (paragraph,) = _paragraphs(model, [block])
        return _run(ctx, _plan_continue(model, paragraph), "Continue list", base)

    @table.method("list_start", "list:str start:int base:revision?", write=True)
    def _list_start(ctx, *, list, start, base):  # noqa: A002  (the parameter is named as it is on the wire)
        """Number the first level of the list `list` from `start` on (1 to 999999)."""
        model = _host(ctx)
        try:
            current = model.lists.get(list)
        except KeyError as exc:
            raise RequestError("command_error", exc.args[0]) from None
        return _run(ctx, [ChangeList(replace(current, start=start))], "List start", base)

    @table.method("number_headings", "on:bool base:revision?", write=True)
    def _number_headings(ctx, *, on, base):
        """Number the headings (`on` true): every paragraph style with a heading level of 1 or more that is not
        numbered yet is numbered in the list `outline` (made with the scheme `chapters` if the document has none), so
        Heading 1 counts 1, 2, 3 and Heading 2 1.1, 1.2 under it. In a presentation the slide title is such a style:
        this numbers every slide title. `on` false takes the numbering off those styles again; the list stays, with
        its start. One step; nothing to do is no step (`revision` unchanged)."""
        model = _host(ctx)
        commands = _plan_number_headings(model, on)
        if not commands:
            return _revision(ctx)
        return _run(ctx, commands, "Number headings" if on else "Remove heading numbers", base)


def _add_scheme_methods(table: MethodTable) -> None:
    @table.method("new_scheme", "like:str name:str base:revision?", write=True)
    def _new_scheme(ctx, *, like, name, base):
        """A new numbering scheme named `name`, drawn as the scheme `like` is to begin with. Returns
        `{revision, scheme}`, the new scheme's id."""
        model = _host(ctx)
        made = replace(_scheme(model, like), id=model.schemes.unique_id(), name=name)
        try:
            made.check()
        except ValueError as exc:
            raise RequestError("command_error", str(exc)) from None
        return {**_run(ctx, [CreateScheme(made)], "New numbering scheme", base), "scheme": made.id}

    @table.method("change_scheme", "scheme:dict base:revision?", write=True)
    def _change_scheme(ctx, *, scheme, base):
        """Give the scheme with `scheme.id` the definition `scheme` (as `lists` sends schemes): every list that
        uses it, and so every item, is drawn the new way. `command_error` for a scheme that makes no sense. The
        same definition is no step."""
        model = _host(ctx)
        wanted = _scheme_from(scheme)
        if _scheme(model, wanted.id) == wanted:
            return _revision(ctx)
        return _run(ctx, [ChangeScheme(wanted)], "Change numbering scheme", base)

    @table.method("reset_scheme", "scheme:str base:revision?", write=True)
    def _reset_scheme(ctx, *, scheme, base):
        """Draw a built-in scheme (`bullets`, `numbers`, `chapters`) as it was built in again. `command_error` for
        a scheme of the document's own."""
        model = _host(ctx)
        current, original = _scheme(model, scheme), builtin_scheme(scheme)
        if original is None:
            raise RequestError("command_error", msg("only a built-in scheme can be reset"))
        if current == original:
            return _revision(ctx)
        return _run(ctx, [ChangeScheme(original)], "Reset numbering scheme", base)

    @table.method("remove_scheme", "scheme:str base:revision?", write=True)
    def _remove_scheme(ctx, *, scheme, base):
        """Take a numbering scheme out of the document. `command_error` while a list uses it."""
        model = _host(ctx)
        _scheme(model, scheme)
        return _run(ctx, [RemoveScheme(scheme)], "Remove numbering scheme", base)
