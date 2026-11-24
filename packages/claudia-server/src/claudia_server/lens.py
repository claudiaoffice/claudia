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

#: Said to a remote provider in place of the start of the document (CODE-80): it is shown how much there is, and has to
#: look for what it needs, so that what leaves the server is what it asked to see.
LOOK_FIRST = "Nothing a person wrote is shown here: look at what the question is about, with the requests below."

#: The requests that read the product's own help, the same in every app (E7.2).
HELP_METHODS = ("help_search", "help_topic")

_FENCES = re.compile(r"`{3,}")


def fence(text: str) -> str:
    """``text`` as a block of data: a fence round it, and no fence inside that could end it early."""
    return f"{FENCE}data\n{_FENCES.sub("'''", text)}\n{FENCE}"


def look_first(start: str) -> str:
    """The end of an outline: nothing is shown, so look, beginning with the request ``start``."""
    return f"{LOOK_FIRST} Start with {start}."


def show_help(method: str, result: Any) -> str:
    """The answer of ``help_search`` or ``help_topic`` as text for the model. Help is written by the product, not by
    the people who wrote the document, so unlike what comes out of a document it is not fenced as data (D1563). The
    loop cuts a long topic like any result."""
    if method == "help_search":
        return "\n".join(f"- {topic['id']} — {topic['title']}" for topic in result) or "No help topic matches that."
    return f"{result['title']}\n\n{result['body']}"


def count(number: int, one: str, many: str) -> str:
    """``1 sheet``, ``2 sheets``."""
    return f"{number} {one if number == 1 else many}"


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

    def orient(
        self,
        document: Document,
        *,
        can_write: bool,
        asker: str | None = None,
        writes: frozenset[str] | None = None,
    ) -> str:
        """Where the model starts: how things are counted and named, and what is in the document, briefly.

        ``asker`` is who asked (a lens may say where she is working); ``writes`` the write methods the model is
        offered for her (``None``: no limit), so an example names one it may use."""
        ...

    def outline(
        self,
        document: Document,
        *,
        can_write: bool,
        asker: str | None = None,
        writes: frozenset[str] | None = None,
    ) -> str:
        """The same start without anything a person wrote (D1568): how much there is and the ids, and that the model
        has to look. What a remote provider is given in place of ``orient``."""
        ...

    def show(self, method: str, params: dict, result: Any) -> str:
        """The answer of the read request ``method`` as text for the model."""
        ...

    def recorder(self, document: Document) -> Recorder:
        """A context manager to hold round one write request; afterwards ``report`` says what it did."""
        ...


class OutlineLens:
    """A lens whose first message is its outline: what a remote provider is shown, so that it is sent what it looks at
    and nothing before (CODE-80). Everything else is the lens's own."""

    def __init__(self, lens: Lens):
        self._lens = lens
        self.look_methods = lens.look_methods
        self.show = lens.show
        self.recorder = lens.recorder

    def orient(
        self,
        document: Document,
        *,
        can_write: bool,
        asker: str | None = None,
        writes: frozenset[str] | None = None,
    ) -> str:
        """The lens's outline."""
        return self._lens.outline(document, can_write=can_write, asker=asker, writes=writes)

    def outline(
        self,
        document: Document,
        *,
        can_write: bool,
        asker: str | None = None,
        writes: frozenset[str] | None = None,
    ) -> str:
        """The lens's outline (so that it is still a lens)."""
        return self.orient(document, can_write=can_write, asker=asker, writes=writes)
