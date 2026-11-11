"""One style API for all three apps: put a style into the slots of anything that can be styled (D304, D309, D316).

A request names *targets* in the app's own terms — ``{"block": id}`` for a composes paragraph, ``{"object": id}`` for
a floating object in any app, ``{"sheet": id, "range": [r0, c0, r1, c1]}`` for cells in computes — and the server
turns each into commands through a :class:`StyleTarget`: a small adapter per kind of target that says which kind of
thing it is (a row of :data:`claudia_core.SLOTS`), which style each of its slots holds, and the command that puts a
style into one slot. Everything else — which slots a style fits, deviating, counting uses — is written once here.

:func:`add_target_methods` registers ``style_model``, ``apply_style``, ``deviate`` and ``style_uses``. The older,
narrower methods (``set_style``, ``set_object_style``, ``set_paragraph_style``, composes' ``deviate_style``,
``deviate_object_style``) stay until every client uses these (the styling-suite plan, step 3.4).

The slot table is a parameter, not a constant (D315): a later kind of thing — a slide's background — is one more row
of the table and one more adapter, and nothing here changes.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any, Protocol

from claudia_core import (
    SLOTS,
    Batch,
    Command,
    CreateStyle,
    SetObjectStyle,
    SetParagraphStyle,
    SlotTable,
    StyleBook,
    StyleDef,
    fits,
    validate_css,
)

from .protocol import Context, MethodTable, RequestError

#: How many targets one request may name (composes has the same bound for paragraphs, D75).
MAX_TARGETS = 200


class StyleTarget(Protocol):
    """How one kind of target becomes a thing with slots, and a style in a slot becomes a command."""

    #: The key a target of this kind is given by: ``"object"`` for ``{"object": id}``.
    key: str

    def thing(self, model: Any, target: dict) -> str:
        """Which row of the slot table the target is (``"text"``, ``"paragraph"``, ``"cell"``). ``KeyError`` if
        the target does not exist, ``ValueError`` if it is malformed."""

    def style_in(self, model: Any, target: dict, slot: str) -> str | None:
        """The style the target's ``slot`` holds now (``None``: none, or not one style throughout)."""

    def command(self, model: Any, target: dict, slot: str, style: str) -> Command:
        """The command that puts ``style`` into the target's ``slot``."""

    def uses(self, model: Any) -> Counter[str]:
        """How many of this kind of target use each style, one count per slot that holds it."""


class ObjectTargets:
    """A floating object, in any app: ``{"object": id}``. Its slots are its own style and its words' (D304)."""

    key = "object"

    def thing(self, model: Any, target: dict) -> str:
        object_id = _text_field(target, "object")
        if object_id not in model.objects:
            raise KeyError(f"no object {object_id!r}")
        return model.objects[object_id].body.kind

    def style_in(self, model: Any, target: dict, slot: str) -> str | None:
        body = model.get_object(target["object"]).body
        if _slot_index(body.kind, slot) == 0:
            return body.style
        return body.paragraph.style if body.paragraph is not None else None

    def command(self, model: Any, target: dict, slot: str, style: str) -> Command:
        kind = model.get_object(target["object"]).body.kind
        if _slot_index(kind, slot) == 0:
            return SetObjectStyle(target["object"], style)
        return SetParagraphStyle(target["object"], style)

    def uses(self, model: Any) -> Counter[str]:
        counted: Counter[str] = Counter()
        for obj in model.objects.values():
            counted[obj.body.style] += 1
            if obj.body.paragraph is not None:
                counted[obj.body.paragraph.style] += 1
        return counted


#: The object targets every app has.
OBJECTS = ObjectTargets()


def _slot_index(thing: str, slot: str) -> int:
    return [s.name for s in SLOTS.slots_of(thing)].index(slot)


def _text_field(target: dict, key: str) -> str:
    value = target.get(key)
    if not isinstance(value, str):
        raise ValueError(f"a target names its {key} by id")
    return value


class _Resolver:
    """The targets of one request, each with its adapter and its row of the slot table."""

    def __init__(self, ctx: Context, adapters: dict[str, StyleTarget], slots: SlotTable, given: object):
        if not isinstance(given, list) or not given or len(given) > MAX_TARGETS:
            raise RequestError("bad_request", f"targets is a list of 1 to {MAX_TARGETS} targets")
        self.model = ctx.document.model
        self.slots = slots
        self.items: list[tuple[StyleTarget, dict, str]] = []
        for target in given:
            if not isinstance(target, dict):
                raise RequestError("bad_request", 'a target is an object such as {"object": id}')
            keys = [key for key in adapters if key in target]
            if len(keys) != 1:
                raise RequestError("bad_request", f"a target names one of: {', '.join(adapters)}")
            adapter = adapters[keys[0]]
            try:
                thing = adapter.thing(self.model, target)
                slots.slots_of(thing)
            except KeyError as exc:
                raise RequestError("command_error", str(exc.args[0])) from None
            except ValueError as exc:
                raise RequestError("bad_request", str(exc)) from None
            self.items.append((adapter, target, thing))

    def chosen_slots(self, thing: str, slot: str | None) -> list[str]:
        names = [s.name for s in self.slots.slots_of(thing)]
        if slot is None:
            return names
        if slot not in names:
            raise RequestError("command_error", f"a {thing} has no slot “{slot}”; it has {', '.join(names)}")
        return [slot]

    def commands(self, style: StyleDef, slot: str | None, only_holding: str | None = None) -> list[Command]:
        """The commands that put ``style`` into the chosen slots of every target. With no ``slot``, every slot of
        a target that the style fits — or, for a deviation (``only_holding``), every slot that held the parent."""
        steps: list[Command] = []
        for adapter, target, thing in self.items:
            names = self.chosen_slots(thing, slot)
            if only_holding is not None and slot is None:
                names = [n for n in names if adapter.style_in(self.model, target, n) == only_holding]
            fitting = [n for n in names if fits(style.kind, self.slots.slot(thing, n))]
            if not fitting:
                where = f"the {slot} of a {thing}" if slot else f"any slot of a {thing}"
                raise RequestError("command_error", f"“{style.name}” is a {style.kind} style and does not fit {where}")
            steps.extend(adapter.command(self.model, target, name, style.id) for name in fitting)
        return steps


def _book(ctx: Context) -> StyleBook:
    book = getattr(ctx.document.model, "styles", None)
    if not isinstance(book, StyleBook):
        raise RequestError("bad_request", "this document has no styles")
    return book


def _known(book: StyleBook, style: str) -> StyleDef:
    try:
        return book.get(style)
    except KeyError as exc:
        raise RequestError("command_error", exc.args[0]) from None


def _run(ctx: Context, steps: list[Command], name: str, base) -> Any:
    command = steps[0] if len(steps) == 1 else Batch(tuple(steps), name)
    try:
        return ctx.document.execute(command, author=ctx.user, base=base)
    except (KeyError, ValueError) as exc:
        raise RequestError("command_error", str(exc.args[0] if isinstance(exc, KeyError) else exc)) from None


def add_target_methods(
    table: MethodTable,
    allowed: Callable[[Context], None],
    targets: Iterable[StyleTarget],
    *,
    own_css: Callable[[dict | None, str | None], dict | None],
    slots: SlotTable = SLOTS,
) -> None:
    """Register ``style_model``, ``apply_style``, ``deviate`` and ``style_uses`` for ``targets``."""
    adapters = {adapter.key: adapter for adapter in targets}

    @table.method("style_model")
    def _style_model(ctx):
        """What a style property means and where a style can go (D303-D305, D312, D316): `{facets, kinds, slots,
        targets}`. `facets` maps each facet to its properties, `kinds` each kind to the facets it may hold, `slots`
        each kind of thing to its slots `{name, reads, kind, takes}` — `takes` lists the kinds of style that fit the
        slot. `targets` are the target keys this app accepts (`object`, `block`, `cell`). A client draws and filters
        with this and keeps no copy of its own."""
        return {**slots.to_data(), "targets": list(adapters)}

    @table.method("apply_style", "targets:list style:str slot:str? base:revision?", write=True)
    def _apply_style(ctx, *, targets, style, slot, base):
        """Put `style` into the slots of `targets`, in one step. A target is `{"object": id}`, `{"block": id}` or
        `{"sheet": id, "range": [r0, c0, r1, c1]}` (see `style_model`'s `targets`). With `slot`, only that slot of
        each target; without, every slot of it the style fits — one bundle fills both slots of a cell or a text box
        (D309, D311, D316). `command_error` if the style fits no chosen slot of a target, or a target is not there."""
        allowed(ctx)
        found = _known(_book(ctx), style)
        steps = _Resolver(ctx, adapters, slots, targets).commands(found, slot)
        applied = _run(ctx, steps, "Apply style", base)
        return {"revision": applied.revision.to_data()}

    @table.method("deviate", "parent:str targets:list slot:str? set:dict? text:text? base:revision?", write=True)
    def _deviate(ctx, *, parent, targets, slot, set, text, base):
        """Make a new style from `parent` that differs in the CSS given (`set` properties, or `text`) and put it
        into `targets`, in one step: "change these only" (D75). The new style is of the parent's kind, gets a
        provisional name such as “Header (changed)” and is marked `to_name` until somebody names it. With `slot`
        ("only the box", D309), only that slot of each target changes; without, every slot that held `parent`.

        Returns `{style, name, revision}`. `command_error` if nothing differs from the parent, a property does not
        belong to the parent's kind, or the new style fits no chosen slot."""
        allowed(ctx)
        book = _book(ctx)
        source = _known(book, parent)
        resolver = _Resolver(ctx, adapters, slots, targets)
        inherited = book.computed(parent)
        wanted = validate_css(own_css(set, text) or {})
        own = {name: value for name, value in wanted.items() if inherited.get(name) != value}
        if not own:
            raise RequestError("command_error", f"the new style would look just like “{source.name}”")
        name = book.provisional_name(parent)
        made = StyleDef(book.unique_id(name), name, "", parent, own, to_name=True, kind=source.kind)
        steps = [CreateStyle(made), *resolver.commands(made, slot, only_holding=parent)]
        applied = _run(ctx, steps, "Deviate style", base)
        return {"style": made.id, "name": name, "revision": applied.revision.to_data()}

    @table.method("style_uses")
    def _style_uses(ctx):
        """How many things use each style, one count per slot that holds it: `{uses: {style: count}}`. A paragraph,
        an object's box and its words, and every cell of a style range each count once."""
        counted: Counter[str] = Counter()
        for adapter in adapters.values():
            counted.update(adapter.uses(ctx.document.model))
        return {"uses": dict(counted)}
