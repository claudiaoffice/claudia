"""Which methods a document offers, and which assistant works in it, by the app it belongs to."""

from __future__ import annotations

from collections.abc import Callable

from claudia_ai import ModelRunner
from claudia_computes import WorkbookModel
from claudia_core import Document, DocumentModel

from .assistant import Assistant
from .computes import computes_methods
from .model_engine import ModelEngine, tools_of
from .protocol import MethodTable, core_methods
from .standin import ScriptedEngine

# What a language model may ask for in each app: editing methods only. Talking is what its answer is for, and who
# may enter a document, what is kept as a checkpoint or who holds a lock are decisions of people.
MODEL_METHODS = {"computes": ("set_cells", "add_sheet", "structure")}
MAX_LISTED_SHEETS = 50  # sheets named to the model; a small model has little room
WORKBOOK_CONTEXT = (
    "Rows and columns are counted from 0. A request looks like "
    '{{"method": "set_cells", "params": {{"sheet": "s1", "cells": [{{"row": 0, "col": 0, "input": "42"}}]}}}}.\n'
    "{sheets}"
)


def methods_for(model_cls: type[DocumentModel]) -> MethodTable:
    """The method table for documents of this model: the app's own when there is one, else the core's."""
    return computes_methods if model_cls.app == "computes" else core_methods


def stand_in_assistant_for(model_cls: type[DocumentModel]) -> Callable[[], Assistant] | None:
    """Makes the scripted stand-in assistant for the apps it knows (workbooks); ``None`` for the others."""
    if model_cls.app != "computes":
        return None
    engine = ScriptedEngine()
    return lambda: Assistant(engine)


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
    return lambda: Assistant(ModelEngine(runner, tools, workbook_context), max_waiting=max_waiting)


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
