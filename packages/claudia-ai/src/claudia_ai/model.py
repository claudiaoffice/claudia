"""The language model behind the AI user (E7.1).

A ``LanguageModel`` turns a conversation (a list of ``{"role", "content"}`` messages) into the next answer. Everything
else only knows this small interface, so the model can be exchanged: ``claudia_ai.OpenVinoModel`` runs one on this
machine; tests use ``claudia_ai.testing.FakeModel``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

Message = dict[str, str]


class ModelError(Exception):
    """The model cannot be loaded or failed while answering. The message is meant for the person using the assistant."""


class LanguageModel(Protocol):
    """A chat model."""

    name: str

    def generate(self, messages: list[Message], *, max_new_tokens: int, stop: Callable[[], bool]) -> str:
        """The assistant's next message. May take a long time, so it runs on a worker thread (``ModelRunner``).

        ``stop`` says that the answer is no longer wanted (a timeout, shutting down): the model must return soon after
        it turns true, with whatever it has. Raises ``ModelError``."""
        ...
