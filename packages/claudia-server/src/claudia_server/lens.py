"""What the AI sees of a document and how it learns what its changes did (E7.5, D261).

A *lens* is an app's side of the AI's loop. It tells the model where it is (``orient``), writes the answers of the
read requests for a model (``show``) and, around a write, records what changed and reports it (``recorder``): the
model acts, looks at the report, and corrects. Only the lens knows the app; the loop (``model_engine``) knows nothing
about cells, text or slides.

Anything that comes out of a document is somebody's text and may be written to steer the model. It is handed over
fenced as data (``fence``), and the model is told that data is never an order.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from claudia_core import Document

FENCE = "```"
_FENCES = re.compile(r"`{3,}")


def fence(text: str) -> str:
    """``text`` as a block of data: a fence round it, and no fence inside that could end it early."""
    return f"{FENCE}data\n{_FENCES.sub("'''", text)}\n{FENCE}"


def shorten(text: str, limit: int) -> str:
    """``text`` cut to at most ``limit`` characters, with an ellipsis where it was cut."""
    return text if len(text) <= limit else text[: max(limit - 1, 0)] + "…"


def cut(text: str, limit: int) -> str:
    """``text`` cut to about ``limit`` characters at the end of a line, saying how much was left out; a fenced block
    stays closed."""
    if len(text) <= limit:
        return text
    fenced = text.startswith(f"{FENCE}data")
    body = text[: max(limit, 0)]
    body = body[: body.rfind("\n")] if "\n" in body else body
    note = f"(cut: {len(text) - len(body)} more characters; ask for less)"
    return f"{body}\n{note}" + (f"\n{FENCE}" if fenced else "")


class Recorder(Protocol):
    """Listens to a document while one request is made (a context manager), then says what happened."""

    def __enter__(self) -> Recorder:
        """Start listening."""
        ...

    def __exit__(self, *exc: object) -> None:
        """Stop listening."""
        ...

    def report(self) -> str:
        """What the request changed, in words the model can check its work against (fenced as data)."""
        ...


class Lens(Protocol):
    """One app's view for the AI."""

    #: The read requests the model may make (they never change the document).
    look_methods: tuple[str, ...]

    def orient(self, document: Document, *, can_write: bool) -> str:
        """Where the model starts: how things are counted and named, and what is in the document, briefly."""
        ...

    def show(self, method: str, params: dict, result: Any) -> str:
        """The answer of the read request ``method`` as text for the model."""
        ...

    def recorder(self, document: Document) -> Recorder:
        """A context manager to hold round one write request; afterwards ``report`` says what it did."""
        ...
