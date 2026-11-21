"""Names of things over the wire (D550): the name a new thing gets, renaming, and naming what has none.

Every object, slide, sheet and chart tab of a document has a name, in one namespace (``claudia_core.names``). The
server gives a new thing the first free ``"<what it is> <n>"``, in the language of the one who made it; anybody who may
edit renames it with ``rename_thing``. Documents from before names hold things without one, and ``name_unnamed`` names
them in one step of the history, when somebody first needs to point at them.
"""

from __future__ import annotations

import re
from functools import cache

from claudia_core import (
    MAX_THING_NAME,
    Batch,
    DescribeObject,
    DescribeThing,
    ObjectModel,
    RenameThing,
    clean_name,
    free_name,
    free_names,
    name_problem,
)

from .i18n import available_locales, localized, msg, translate
from .images import picture_words
from .protocol import Context, MethodTable, RequestError

#: What a new thing is called before anybody has named it, by kind. Written as ``msg`` so that each is translated.
_KIND_LABELS = {
    "text": msg("Text box"),
    "shape": msg("Shape"),
    "image": msg("Picture"),
    "diagram": msg("Chart"),
    "container": msg("Container"),
    "table": msg("Table"),
    "slide": msg("Slide"),
    # a paragraph of a text (D554, D1310): every one that is not a heading, a list item too; a heading is called by its
    # words (D1311)
    "paragraph": msg("Paragraph"),
}


def _label_of(kind: str) -> str:
    """What things of this ``kind`` are called before anybody names them: a heading or a list item is a paragraph."""
    return _KIND_LABELS.get(kind, _KIND_LABELS["paragraph"])


def _model(ctx: Context) -> ObjectModel:
    """The model of this document, which every app that has things to name is."""
    model = ctx.document.model
    if not isinstance(model, ObjectModel):
        raise RequestError("command_error", msg("this document has nothing that can be named"))
    return model


@cache
def _generic_name_pattern() -> re.Pattern[str]:
    """``"<what it is> <n>"`` in any language the server speaks, for every kind a thing can have."""
    words = {translate(label, locale) for label in _KIND_LABELS.values() for locale in ("en", *available_locales())}
    alternatives = "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))
    return re.compile(f"(?:{alternatives}) \\d+", re.IGNORECASE)


def is_generic_name(name: str) -> bool:
    """Is this the name a thing got by being made ("Paragraph 12", "Absatz 12", "Slide 3"), not one a person chose?
    A name a person gave is a statement; a generic one only keeps the thing apart from the others. So only the first is
    written to a Word or OpenDocument file as a bookmark (D1311). A person who types "Paragraph 12" herself gets what
    she typed, a name that is not written out: a loss that costs nothing."""
    return _generic_name_pattern().fullmatch(name) is not None


def paragraph_label(ctx: Context) -> str:
    """What a new paragraph is called before anybody has renamed it, without its number ("Paragraph"), said in the
    language of the connection (D1310). Every paragraph that is not a heading has it: a list item is one too."""
    return localized(_KIND_LABELS["paragraph"], ctx.locale)


def default_name(ctx: Context, kind: str) -> str:
    """The first free ``"<label> <n>"`` for a new thing of ``kind``, said in the language of the connection."""
    label = localized(_label_of(kind), ctx.locale)
    return free_name(label, _model(ctx).names_in_use())


def _refuse_fixed_name(model: ObjectModel, thing_id: str) -> None:
    """``command_error`` for a thing whose name is worked out (a heading is called by its words, D1311)."""
    if model.has_thing(thing_id) and model.name_is_fixed(thing_id):
        raise RequestError(
            "command_error", msg("a heading is called by its words: change the words to change the name")
        )


def _rename_thing(ctx: Context, *, id: str, name: str, base) -> dict:  # noqa: A002 - the wire name
    """Give the object, slide, sheet or chart tab `id` the name `name` (spaces around it and doubled inside it are
    tidied away). The formulas that read a renamed sheet are written again with its name. `bad_request` for a name
    without text or with more than 60 characters; `command_error` when somebody else has the name (a named range
    counts: the sentence says who, however capitals and spaces are written), for an unknown id and for a named range,
    which is renamed with `rename_name`. Undo gives the old name and the formulas back."""
    _refuse_fixed_name(_model(ctx), id)
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
        name = free_name(localized(_label_of(kind), locale), taken)
        taken.append(name)
        steps.append(RenameThing(thing, name))
    return steps


def name_unnamed_things(model: object, locale: str) -> int:
    """Give every unnamed thing of ``model`` the first free name for what it is, in ``locale``, *in place*: no history
    step, because the model is not a document yet. What an import does with a file's things (E1.13, D1311): a slide is
    "Slide 1", a paragraph "Paragraph 4". One pass over the things however many there are: a text of fifty thousand
    paragraphs is not renamed one command at a time. Returns how many were named."""
    if not isinstance(model, ObjectModel):
        return 0
    wanted: dict[str, list[str]] = {}  # the things of each kind of name, in order
    for kind, thing in model.unnamed_things():
        wanted.setdefault(localized(_label_of(kind), locale), []).append(thing)
    taken = list(model.names_in_use())
    for label, things in wanted.items():
        names = free_names(label, taken, len(things))
        taken.extend(names)
        for thing, name in zip(things, names, strict=True):
            model.set_thing_name(thing, name)
    return sum(len(things) for things in wanted.values())


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


def _proposed_name(model: ObjectModel, kind: str, locale: str) -> str:
    """The name a thing gets when it is first pointed at: the first free "<what it is> <n>"."""
    return free_name(localized(_label_of(kind), locale), model.names_in_use())


def _name_thing(ctx: Context, *, id: str, base) -> dict:  # noqa: A002 - the wire name
    """Give the thing `id` a name if it has none, so that it can be pointed at (a tag in the chat): by what it is
    ("Paragraph 3"), said in your language; a heading with words is called by them and needs none. One
    step in the history; a thing that has a name keeps it and nothing is written. Returns `{name, revision}`.
    `command_error` for an id that is not in the document."""
    model = _model(ctx)
    if not model.has_thing(id):
        raise RequestError("command_error", msg("there is nothing called {id!r} in this document", id=id))
    current = model.thing_name(id)
    if current:
        revision = ctx.document.revision
        return {"name": current, "revision": None if revision is None else revision.to_data()}
    name = _proposed_name(model, _kind_of(model, id), ctx.locale)
    applied = ctx.document.execute(RenameThing(id, name), author=ctx.user, base=base)
    return {"name": name, "revision": applied.revision.to_data()}


def _is_drawn(model: ObjectModel, thing_id: str) -> bool:
    """Is it something drawn (a picture, a chart, a shape, a container, a text box), which can be mere decoration?
    A table is an object, but a table is read, not looked at."""
    return thing_id in model.objects and model.objects[thing_id].body.kind != "table"


def _thing_details(ctx: Context, *, id: str) -> dict:  # noqa: A002 - the wire name
    """What the Name & describe… dialog shows about the thing `id`: `{id, kind, name, name_fixed, description, drawn,
    decorative}`. `name_fixed` is true where the name is worked out and the dialog shows it locked (a heading is
    called by its words); `drawn` is true for what can be marked `decorative` (a picture, a chart, a shape, a
    container, a text box). `command_error` for an id that is not in the document."""
    model = _model(ctx)
    if not model.has_thing(id):
        raise RequestError("command_error", msg("there is nothing called {id!r} in this document", id=id))
    drawn = _is_drawn(model, id)
    return {
        "id": id,
        "kind": _kind_of(model, id),
        "name": model.thing_name(id),
        "name_fixed": model.name_is_fixed(id),
        "description": model.thing_description(id) if not drawn else model.get_object(id).body.description,
        "drawn": drawn,
        "decorative": model.get_object(id).body.decorative if drawn else False,
    }


def _name_and_describe(
    ctx: Context,
    *,
    id: str,
    name: str,
    description: str,
    decorative: bool,
    base,  # noqa: A002 - the wire name
) -> dict:
    """The one dialog of Name & describe… for any thing (D1317): give the thing `id` the name `name` and the
    description `description`, together, as **one step in the history**, so that one Undo takes both back. What does
    not change is not written, and when nothing changes nothing is. A heading keeps its name (it is called by its
    words); an empty `name` is only for a thing that has none yet. `decorative` is for what is drawn (see
    `thing_details`): marking it drops the description, and a picture needs words or the tick. Refused as a whole with
    `bad_request` for a name that is no name, `command_error` for a name somebody else has, for a heading's name, for
    a tick on something that is not drawn, and for an id that is not in the document. Returns `{revision, name,
    description, decorative}`."""
    model = _model(ctx)
    if not model.has_thing(id):
        raise RequestError("command_error", msg("there is nothing called {id!r} in this document", id=id))
    steps: list = []
    current, cleaned = model.thing_name(id), clean_name(name)
    if cleaned != current and (name or current):
        _refuse_fixed_name(model, id)
        problem = name_problem(name)
        if problem is not None:
            raise RequestError("bad_request", problem)
        steps.append(model.rename_command(id, cleaned))
    drawn = _is_drawn(model, id)
    if decorative and not drawn:
        raise RequestError("command_error", msg("only something that is drawn can be marked as decoration"))
    if drawn:
        body = model.get_object(id).body
        words = picture_words(description, bool(decorative)) if body.kind == "image" else description
        if decorative:
            words = ""
        if (words, bool(decorative)) != (body.description, body.decorative):
            steps.append(DescribeObject(id, words, bool(decorative)))
    elif description != model.thing_description(id):
        steps.append(DescribeThing(id, description))
    revision = ctx.document.revision
    if steps:
        command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name="Name and describe")
        revision = ctx.document.execute(command, author=ctx.user, base=base).revision
    return {
        "revision": None if revision is None else revision.to_data(),
        "name": cleaned if steps and cleaned else current,
        "description": "" if decorative else description,
        "decorative": bool(decorative),
    }


def add_name_methods(table: MethodTable) -> None:
    """Add ``rename_thing``, ``name_thing``, ``name_unnamed``, ``thing_details`` and ``name_and_describe`` to an
    app's method table."""

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

    def thing_details(ctx: Context, **params) -> dict:
        return _thing_details(ctx, **params)

    def name_and_describe(ctx: Context, **params) -> dict:
        return _name_and_describe(ctx, **params)

    thing_details.__doc__ = _thing_details.__doc__
    name_and_describe.__doc__ = _name_and_describe.__doc__
    table.method("thing_details", "id:str")(thing_details)
    table.method(
        "name_and_describe", "id:str name:str description:text decorative:bool=false base:revision?", write=True
    )(name_and_describe)
