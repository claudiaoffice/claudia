"""The paragraph: a stretch of styled text and who wrote which part of it (E9.7, E10.17, D181).

A paragraph is the same thing wherever text appears in the suite — a paragraph of a composes document, the words
in a creates text box, the label inside a shape on a sheet. It carries:

* ``text`` — the characters.
* ``style`` — the id of a style in the document's :class:`~claudia_core.StyleBook`, which is where its font, its
  size, its colour and its alignment come from. This is the *paragraph's* style, separate from the style of the
  object a paragraph may sit inside: a shape's own style says what its background and border look like (``fill``,
  ``stroke``), its paragraph's style says what its words look like.
* ``runs`` — who wrote which stretch, by character count, independent of how it is styled. ``runs`` always add up
  to exactly the length of ``text``.

A paragraph is **immutable**. Editing one makes a new one (``with_text``, ``with_style``, or
``dataclasses.replace``). That is not ceremony: a paragraph is stored inside a frozen
:class:`~claudia_core.ObjectBody`, and every command returns its own inverse built from the state it found, so a
paragraph changed in place would hand the inverse the *new* text and quietly break undo.

Where a paragraph may be split or joined — composes, where it sits in a flowing document — the model owns that
and replaces its paragraphs in its own list. A paragraph inside an object is never split or joined: it has a box
of a fixed size, and text that does not fit is clipped at the border rather than overflowing or pushing anything
(D182). Nothing here enforces that; it is the view's part, and the note is here because this is where the
question is asked.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace

#: How long one paragraph's text may be.
MAX_PARAGRAPH_TEXT = 20_000


@dataclass(frozen=True)
class Run:
    """``length`` characters written by ``author`` (``None``: unknown), through ``via``'s suggestion if any."""

    length: int
    author: str | None
    via: str | None = None


def total(runs: Iterable[Run]) -> int:
    """The number of characters the runs cover."""
    return sum(run.length for run in runs)


def normalized(runs: Iterable[Run]) -> list[Run]:
    """The runs without empty ones, with neighbours of the same origin joined."""
    out: list[Run] = []
    for run in runs:
        if run.length <= 0:
            continue
        if out and (out[-1].author, out[-1].via) == (run.author, run.via):
            out[-1] = Run(out[-1].length + run.length, run.author, run.via)
        else:
            out.append(run)
    return out


def slice_runs(runs: Iterable[Run], start: int, end: int) -> list[Run]:
    """The runs covering characters ``start <= i < end``."""
    out: list[Run] = []
    at = 0
    for run in runs:
        first, last = max(at, start), min(at + run.length, end)
        if last > first:
            out.append(Run(last - first, run.author, run.via))
        at += run.length
    return normalized(out)


def delete_runs(runs: Iterable[Run], start: int, end: int) -> list[Run]:
    """The runs with characters ``start <= i < end`` taken out."""
    kept = list(runs)
    return normalized(slice_runs(kept, 0, start) + slice_runs(kept, end, total(kept)))


def insert_runs(runs: Iterable[Run], offset: int, new: Iterable[Run]) -> list[Run]:
    """The runs with ``new`` put in at ``offset``."""
    kept = list(runs)
    return normalized(slice_runs(kept, 0, offset) + list(new) + slice_runs(kept, offset, total(kept)))


def runs_to_data(runs: Iterable[Run]) -> list[list]:
    """The plain-data form: one ``[length, author, via]`` per run."""
    return [[run.length, run.author, run.via] for run in runs]


def runs_from_data(data: Iterable[list]) -> list[Run]:
    """Inverse of :func:`runs_to_data`."""
    return [Run(item[0], item[1], item[2] if len(item) > 2 else None) for item in data]


@dataclass(frozen=True)
class Paragraph:
    """One paragraph: its id, its style, its characters, and who wrote which of them.

    ``runs`` always add up to the length of ``text``; :meth:`check` says so out loud. Immutable — see the module
    description for why that matters to undo."""

    id: str
    style: str
    text: str = ""
    runs: tuple[Run, ...] = field(default_factory=tuple)

    def __len__(self) -> int:
        """The number of characters in the paragraph."""
        return len(self.text)

    def with_text(self, text: str, runs: Iterable[Run]) -> Paragraph:
        """The same paragraph with other words in it, and the runs that say who wrote them."""
        return replace(self, text=text, runs=tuple(normalized(runs)))

    def with_style(self, style: str) -> Paragraph:
        """The same paragraph under another style."""
        return replace(self, style=style)

    def written_by(self, author: str | None, via: str | None = None) -> Paragraph:
        """The same paragraph with all of its text attributed to one person: what setting the whole text at once
        means, as opposed to typing into it character by character."""
        return replace(self, runs=((Run(len(self.text), author, via),) if self.text else ()))

    def check(self) -> None:
        """``ValueError`` with a sentence if the paragraph does not hold together."""
        if not isinstance(self.text, str) or len(self.text) > MAX_PARAGRAPH_TEXT:
            raise ValueError(f"a paragraph holds text of at most {MAX_PARAGRAPH_TEXT} characters")
        if total(self.runs) != len(self.text):
            raise ValueError("the runs must cover exactly the paragraph's text")

    def to_data(self) -> dict:
        """The plain-data form: ``{id, style, text, runs}``."""
        return {"id": self.id, "style": self.style, "text": self.text, "runs": runs_to_data(self.runs)}

    @classmethod
    def from_data(cls, data: dict) -> Paragraph:
        """Inverse of :meth:`to_data`."""
        return cls(data["id"], data["style"], data.get("text", ""), tuple(runs_from_data(data.get("runs", []))))
