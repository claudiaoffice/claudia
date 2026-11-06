"""Which methods a document offers, and which assistant works in it, by the app it belongs to."""

from __future__ import annotations

from collections.abc import Callable

from claudia_ai import ModelRunner
from claudia_computes import WorkbookModel
from claudia_core import Document, DocumentModel
from claudia_creates import ShapeLibrary

from .assistant import Assistant, Engine
from .composes import composes_methods
from .computes import computes_methods
from .creates import creates_methods, creates_methods_with
from .model_engine import ModelEngine, tools_of
from .protocol import MethodTable, core_methods
from .standin import ScriptedEngine
from .standin_text import TextEngine

_METHODS: dict[str, MethodTable] = {
    "computes": computes_methods,
    "composes": composes_methods,
    "creates": creates_methods,
}
_ENGINES: dict[str, Callable[[], Engine]] = {"computes": ScriptedEngine, "composes": TextEngine}

# What the assistant may ask for in each app: editing methods only. Talking is what its answer is for, and who may
# enter a document, what is kept as a checkpoint or who holds a lock are decisions of people. This is more than a
# prompt-building list (it also picks the tools *described* to a model): it is the account's allow-list, checked at
# dispatch for both the model-driven engine and the scripted stand-in alike (SEC-10). An app with no entry here gets
# none, so an assistant for it can write nothing until somebody decides what it may do.
MODEL_METHODS = {"computes": ("set_cells", "add_sheet", "structure"), "composes": ("suggest",)}
MAX_LISTED_SHEETS = 50  # sheets named to the model; a small model has little room
WORKBOOK_CONTEXT = (
    "Rows and columns are counted from 0. A request looks like "
    '{{"method": "set_cells", "params": {{"sheet": "s1", "cells": [{{"row": 0, "col": 0, "input": "42"}}]}}}}.\n'
    "{sheets}"
)


def methods_for(model_cls: type[DocumentModel], *, shapes: ShapeLibrary | None = None) -> MethodTable:
    """The method table for documents of this model: the app's own when there is one, else the core's.

    ``shapes`` is the library of outlines a presentation server offers; it matters to presentations only, and by
    default they get the built-in shapes."""
    if model_cls.app == "creates" and shapes is not None:
        return creates_methods_with(shapes)
    return _METHODS.get(model_cls.app, core_methods)


def stand_in_assistant_for(model_cls: type[DocumentModel]) -> Callable[[], Assistant] | None:
    """Makes the scripted stand-in assistant for the apps it knows (workbooks, texts); ``None`` for the others.

    Bound by the same allow-list as a model-driven assistant (``MODEL_METHODS``, SEC-10): the stand-in is a trusted
    script today, but the guarantee a person is shown must not depend on which engine happens to answer."""
    engine_class = _ENGINES.get(model_cls.app)
    if engine_class is None:
        return None
    engine = engine_class()
    allowed = MODEL_METHODS.get(model_cls.app, ())
    return lambda: Assistant(engine, allowed_methods=allowed)


def model_assistant_for(
    model_cls: type[DocumentModel], runner: ModelRunner, *, max_waiting: int = 4
) -> Callable[[], Assistant] | None:
    """Makes assistants that ask a language model, for the apps it knows (workbooks); ``None`` for the others.

    All assistants share the one ``runner``: one model for the server. ``max_waiting`` questions of a document may
    wait behind the one being answered."""
    names = MODEL_METHODS.get(model_cls.app)
    if names is None:
        return None
    tools = tools_of(methods_for(model_cls), names)
    return lambda: Assistant(
        ModelEngine(runner, tools, workbook_context), max_waiting=max_waiting, allowed_methods=names
    )


def workbook_context(document: Document) -> str:
    """What the model is told about a workbook: how to count, an example request and the sheets (id: name)."""
    model = document.model
    assert isinstance(model, WorkbookModel)
    sheets = list(model.sheets.values())
    if not sheets:
        listing = "There are no sheets yet: add one with add_sheet."
    else:
        lines = [f"{sheet.id}: {' '.join(sheet.name.split())}" for sheet in sheets[:MAX_LISTED_SHEETS]]
        if len(sheets) > MAX_LISTED_SHEETS:
            lines.append(f"... and {len(sheets) - MAX_LISTED_SHEETS} more")
        listing = "Sheets in this document (id: name):\n" + "\n".join(lines)
    return WORKBOOK_CONTEXT.format(sheets=listing)
