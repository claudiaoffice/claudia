"""Names of things over the wire (D550): the name a new thing gets, renaming, and naming what has none.

Every object, slide, sheet and chart tab of a document has a name, in one namespace (``claudia_core.names``). The
server gives a new thing the first free ``"<what it is> <n>"``, in the language of the one who made it; anybody who may
edit renames it with ``rename_thing``. Documents from before names hold things without one, and ``name_unnamed`` names
them in one step of the history, when somebody first needs to point at them.
"""

from __future__ import annotations

from claudia_core import MAX_THING_NAME, Batch, ObjectModel, RenameThing, clean_name, free_name, name_problem

from .i18n import localized, msg
from .protocol import Context, MethodTable, RequestError

#: What a new thing is called before anybody has named it, by kind. Written as ``msg`` so that each is translated.
_KIND_LABELS = {
    "text": msg("Text box"),
    "shape": msg("Shape"),
    "image": msg("Picture"),
    "diagram": msg("Chart"),
    "rendered": msg("Diagram"),
    "slide": msg("Slide"),
    # the paragraphs of a text (D554): named one at a time, when somebody points at one
    "heading": msg("Heading"),
    "item": msg("List item"),
    "paragraph": msg("Paragraph"),
}


def _model(ctx: Context) -> ObjectModel:
    """The model of this document, which every app that has things to name is."""
    model = ctx.document.model
    if not isinstance(model, ObjectModel):
        raise RequestError("command_error", msg("this document has nothing that can be named"))
    return model


def default_name(ctx: Context, kind: str) -> str:
    """The first free ``"<label> <n>"`` for a new thing of ``kind``, said in the language of the connection."""
    label = localized(_KIND_LABELS[kind], ctx.locale)
    return free_name(label, _model(ctx).names_in_use())


def _rename_thing(ctx: Context, *, id: str, name: str, base) -> dict:  # noqa: A002 - the wire name
    """Give the object, slide, sheet or chart tab `id` the name `name` (spaces around it and doubled inside it are
    tidied away). The formulas that read a renamed sheet are written again with its name. `bad_request` for a name
    without text or with more than 60 characters; `command_error` when somebody else has the name (a named range
    counts: the sentence says who, however capitals and spaces are written), for an unknown id and for a named range,
    which is renamed with `rename_name`. Undo gives the old name and the formulas back."""
    cleaned = clean_name(name)
    if not cleaned:
        raise RequestError("bad_request", msg("a name needs some text"))
    if len(cleaned) > MAX_THING_NAME:
        raise RequestError("bad_request", msg("a name has at most {limit} characters", limit=MAX_THING_NAME))
    problem = name_problem(name)
    if problem is not None:
        raise RequestError("bad_request", problem)
    applied = ctx.document.execute(RenameThing(id, cleaned), author=ctx.user, base=base)
    return {"revision": applied.revision.to_data()}


def naming_steps(model: object, locale: str) -> list[RenameThing]:
    """The renames that give every unnamed thing of ``model`` the first free name for what it is, in ``locale``; none
    for a model that has no things. Used for a document from before names and for what an empty document already
    holds when it is made (a presentation's first slide)."""
    if not isinstance(model, ObjectModel):
        return []
    taken = list(model.names_in_use())
    steps = []
    for kind, thing in model.unnamed_things():
        name = free_name(localized(_KIND_LABELS[kind], locale), taken)
        taken.append(name)
        steps.append(RenameThing(thing, name))
    return steps


def _name_unnamed(ctx: Context, *, base) -> dict:
    """Name every object and slide that has no name yet (a document from before names), each by what it is: "Text box
    1", "Slide 2". One step in the history; things that have a name are not touched. Returns how many were named."""
    steps = naming_steps(_model(ctx), ctx.locale)
    if not steps:
        revision = ctx.document.revision
        return {"named": 0, "revision": None if revision is None else revision.to_data()}
    command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name="Name things")
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"named": len(steps), "revision": applied.revision.to_data()}


def _kind_of(model: ObjectModel, thing_id: str) -> str:
    """The kind of the thing ``thing_id``, named or not."""
    for kind, thing, _name in model.named_things():
        if thing == thing_id:
            return kind
    for kind, thing in model.unnamed_things():
        if thing == thing_id:
            return kind
    block_kind = getattr(model, "block_kind", None)  # a paragraph without a name is in neither list (D554)
    if block_kind is not None:
        return block_kind(model.block(thing_id))  # type: ignore[attr-defined]
    raise KeyError(thing_id)


def _proposed_name(model: ObjectModel, thing_id: str, kind: str, locale: str) -> str:
    """The name a thing gets when it is first pointed at: a heading's own words when they make a free name, else the
    first free "<what it is> <n>"."""
    if kind == "heading":
        words = clean_name(model.block(thing_id).text)[:MAX_THING_NAME].strip()  # type: ignore[attr-defined]
        if words and name_problem(words) is None and model.name_holder(thing_id, words) is None:
            return words
    return free_name(localized(_KIND_LABELS[kind], locale), model.names_in_use())


def _name_thing(ctx: Context, *, id: str, base) -> dict:  # noqa: A002 - the wire name
    """Give the thing `id` a name if it has none, so that it can be pointed at (a tag in the chat): a heading is named
    by its words when nothing else has them, anything else by what it is ("Paragraph 3"), said in your language. One
    step in the history; a thing that has a name keeps it and nothing is written. Returns `{name, revision}`.
    `command_error` for an id that is not in the document."""
    model = _model(ctx)
    if not model.has_thing(id):
        raise RequestError("command_error", msg("there is nothing called {id!r} in this document", id=id))
    current = model.thing_name(id)
    if current:
        revision = ctx.document.revision
        return {"name": current, "revision": None if revision is None else revision.to_data()}
    name = _proposed_name(model, id, _kind_of(model, id), ctx.locale)
    applied = ctx.document.execute(RenameThing(id, name), author=ctx.user, base=base)
    return {"name": name, "revision": applied.revision.to_data()}


def add_name_methods(table: MethodTable) -> None:
    """Add ``rename_thing``, ``name_thing`` and ``name_unnamed`` to an app's method table."""

    def rename_thing(ctx: Context, **params) -> dict:
        return _rename_thing(ctx, **params)

    def name_unnamed(ctx: Context, **params) -> dict:
        return _name_unnamed(ctx, **params)

    def name_thing(ctx: Context, **params) -> dict:
        return _name_thing(ctx, **params)

    rename_thing.__doc__ = _rename_thing.__doc__
    name_unnamed.__doc__ = _name_unnamed.__doc__
    name_thing.__doc__ = _name_thing.__doc__
    table.method("name_thing", "id:str base:revision?", write=True)(name_thing)
    table.method("rename_thing", "id:str name:str base:revision?", write=True)(rename_thing)
    table.method("name_unnamed", "base:revision?", write=True)(name_unnamed)
