"""Which methods a document offers, by the app it belongs to."""

from __future__ import annotations

from collections.abc import Callable

from claudia_core import DocumentModel

from .assistant import Assistant
from .computes import computes_methods
from .protocol import MethodTable, core_methods
from .standin import ScriptedEngine


def methods_for(model_cls: type[DocumentModel]) -> MethodTable:
    """The method table for documents of this model: the app's own when there is one, else the core's."""
    return computes_methods if model_cls.app == "computes" else core_methods


def stand_in_assistant_for(model_cls: type[DocumentModel]) -> Callable[[], Assistant] | None:
    """Makes the scripted stand-in assistant for the apps it knows (workbooks); ``None`` for the others."""
    if model_cls.app != "computes":
        return None
    engine = ScriptedEngine()
    return lambda: Assistant(engine)
