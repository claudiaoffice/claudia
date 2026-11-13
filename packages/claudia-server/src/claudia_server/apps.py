"""Which methods a document offers, and which assistant works in it, by the app it belongs to."""

from __future__ import annotations

from collections.abc import Callable

from claudia_ai import ModelRunner
from claudia_core import Document, DocumentModel
from claudia_creates import ShapeLibrary

from .assistant import Assistant, Engine, Say, Step, Task
from .composes import composes_methods
from .computes import computes_methods
from .creates import creates_methods, creates_methods_with
from .lens import Lens
from .model_engine import Budget, ModelEngine, tools_of
from .protocol import MethodTable, core_methods
from .slide_lens import SlideLens
from .standin import ScriptedEngine
from .standin_text import TextEngine
from .workbook_lens import WorkbookLens

_METHODS: dict[str, MethodTable] = {
    "computes": computes_methods,
    "composes": composes_methods,
    "creates": creates_methods,
}
NO_MODEL = (
    "There is no language model on this server, so I cannot work on slides yet. Whoever runs the server can give me "
    "one: start it with --ai MODEL_DIR (./start.sh creates --ai), or choose a model on the AI page of the server "
    "settings."
)


class NoModelEngine:
    """Creates' answer while its server has no language model (E7.9, D265). There is no scripted stand-in for slides
    (D265), but ``@ai`` must say why nothing happens instead of failing with "ai is not here"."""

    def plan(self, task: Task) -> list[Step]:
        """The one answer, whatever was asked."""
        return [Say(NO_MODEL)]


_ENGINES: dict[str, Callable[[], Engine]] = {
    "computes": ScriptedEngine,
    "composes": TextEngine,
    "creates": NoModelEngine,
}

# What the assistant may ask for in each app: editing methods only. Talking is what its answer is for, and who may
# enter a document, what is kept as a checkpoint or who holds a lock are decisions of people. This is more than a
# prompt-building list (it also picks the tools *described* to a model): it is the account's allow-list, checked at
# dispatch for both the model-driven engine and the scripted stand-in alike (SEC-10). An app with no entry here gets
# none, so an assistant for it can write nothing until somebody decides what it may do.
MODEL_METHODS = {
    "computes": ("set_cells", "add_sheet", "structure", "resize_lines"),
    "composes": ("suggest",),
    # D265: slides and the objects that need no binary data, their words and their words' style; D293: the speaker
    # notes. Not images, export, snapping or rotation to begin with, and not the planned times (people plan).
    "creates": (
        "add_slide",
        "set_slide_notes",
        "add_object",
        "set_text",
        "set_paragraph_style",
        "move_object",
        "resize_object",
        "remove_object",
    ),
}
# What it may write for a person who chose *suggest* (D262). Composes' ``suggest`` *is* its suggest mode; computes and
# creates have no way to propose yet (E7.8), so there it may write nothing until a person switches to *act*.
SUGGEST_METHODS = {"computes": (), "composes": ("suggest",), "creates": ()}
# The apps whose documents the model can be shown and its changes reported on (E7.5): without a lens there is no
# model-driven AI for an app, and its stand-in (if it has one) answers instead.
_LENSES: dict[str, Lens] = {"computes": WorkbookLens(), "creates": SlideLens()}


def methods_for(model_cls: type[DocumentModel], *, shapes: ShapeLibrary | None = None) -> MethodTable:
    """The method table for documents of this model: the app's own when there is one, else the core's.

    ``shapes`` is the library of outlines a presentation server offers; it matters to presentations only, and by
    default they get the built-in shapes."""
    if model_cls.app == "creates" and shapes is not None:
        return creates_methods_with(shapes)
    return _METHODS.get(model_cls.app, core_methods)


def stand_in_assistant_for(model_cls: type[DocumentModel]) -> Callable[[], Assistant] | None:
    """Makes the scripted stand-in assistant for the apps it knows (workbooks, texts; for presentations one that says
    there is no model, D265); ``None`` for the others.

    Bound by the same allow-list as a model-driven assistant (``MODEL_METHODS``, SEC-10): the stand-in is a trusted
    script today, but the guarantee a person is shown must not depend on which engine happens to answer."""
    engine_class = _ENGINES.get(model_cls.app)
    if engine_class is None:
        return None
    engine = engine_class()
    allowed = MODEL_METHODS.get(model_cls.app, ())
    proposes = SUGGEST_METHODS.get(model_cls.app, ())
    return lambda: Assistant(engine, allowed_methods=allowed, suggest_methods=proposes)


def model_assistant_for(
    model_cls: type[DocumentModel], runner: ModelRunner, *, max_waiting: int = 4, budget: Budget | None = None
) -> Callable[[], Assistant] | None:
    """Makes assistants that ask a language model, for the apps that have a lens (workbooks, presentations); ``None``
    for the others.

    All assistants share the one ``runner``: one model for the server. ``max_waiting`` questions of a document may
    wait behind the one being answered; ``budget`` is what one question may cost (rounds, requests)."""
    lens = _LENSES.get(model_cls.app)
    names = MODEL_METHODS.get(model_cls.app)
    if lens is None or names is None:
        return None
    table = methods_for(model_cls)
    tools = (*tools_of(table, lens.look_methods, kind="look"), *tools_of(table, names))
    proposes = SUGGEST_METHODS.get(model_cls.app, ())
    return lambda: Assistant(
        ModelEngine(runner, tools, lens, budget=budget or Budget()),
        max_waiting=max_waiting,
        allowed_methods=names,
        suggest_methods=proposes,
    )


def workbook_context(document: Document, *, can_write: bool = True) -> str:
    """What the model is told about a workbook before it is asked anything (see ``WorkbookLens.orient``)."""
    return _LENSES["computes"].orient(document, can_write=can_write)
