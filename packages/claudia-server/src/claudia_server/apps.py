"""Which methods a document offers, by the app it belongs to."""

from __future__ import annotations

from collections.abc import Callable

from claudia_core import DocumentModel

from .assistant import Assistant, Engine
from .composes import composes_methods
from .computes import computes_methods
from .protocol import MethodTable, core_methods
from .standin import ScriptedEngine
from .standin_text import TextEngine

_METHODS: dict[str, MethodTable] = {"computes": computes_methods, "composes": composes_methods}
_ENGINES: dict[str, Callable[[], Engine]] = {"computes": ScriptedEngine, "composes": TextEngine}


def methods_for(model_cls: type[DocumentModel]) -> MethodTable:
    """The method table for documents of this model: the app's own when there is one, else the core's."""
    return _METHODS.get(model_cls.app, core_methods)


def stand_in_assistant_for(model_cls: type[DocumentModel]) -> Callable[[], Assistant] | None:
    """Makes the scripted stand-in assistant for the apps it knows (workbooks, texts); ``None`` for the others."""
    engine_class = _ENGINES.get(model_cls.app)
    if engine_class is None:
        return None
    engine = engine_class()
    return lambda: Assistant(engine)
