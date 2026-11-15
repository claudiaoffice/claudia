"""Names of things over the wire (D550): the name a new thing gets, renaming, and naming what has none.

Every object, slide, sheet and chart tab of a document has a name, in one namespace (``claudia_core.names``). The
server gives a new thing the first free ``"<what it is> <n>"``, in the language of the one who made it; anybody who may
edit renames it with ``rename_thing``. Documents from before names hold things without one, and ``name_unnamed`` names
them in one step of the history, when somebody first needs to point at them.
"""

from __future__ import annotations

from collections.abc import Callable

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


def _name_unnamed(ctx: Context, *, base) -> dict:
    """Name every object and slide that has no name yet (a document from before names), each by what it is: "Text box
    1", "Slide 2". One step in the history; things that have a name are not touched. Returns how many were named."""
    model = _model(ctx)
    taken = list(model.names_in_use())
    steps = []
    for kind, thing in model.unnamed_things():
        name = free_name(localized(_KIND_LABELS[kind], ctx.locale), taken)
        taken.append(name)
        steps.append(RenameThing(thing, name))
    if not steps:
        revision = ctx.document.revision
        return {"named": 0, "revision": None if revision is None else revision.to_data()}
    command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name="Name things")
    applied = ctx.document.execute(command, author=ctx.user, base=base)
    return {"named": len(steps), "revision": applied.revision.to_data()}


def add_name_methods(table: MethodTable, *, guard: Callable[[Context], None] | None = None) -> None:
    """Add ``rename_thing`` and ``name_unnamed`` to an app's method table. ``guard`` is asked first and may refuse (a
    text the assistant may not write, D63)."""

    def rename_thing(ctx: Context, **params) -> dict:
        if guard is not None:
            guard(ctx)
        return _rename_thing(ctx, **params)

    def name_unnamed(ctx: Context, **params) -> dict:
        if guard is not None:
            guard(ctx)
        return _name_unnamed(ctx, **params)

    rename_thing.__doc__ = _rename_thing.__doc__
    name_unnamed.__doc__ = _name_unnamed.__doc__
    table.method("rename_thing", "id:str name:str base:revision?", write=True)(rename_thing)
    table.method("name_unnamed", "base:revision?", write=True)(name_unnamed)
