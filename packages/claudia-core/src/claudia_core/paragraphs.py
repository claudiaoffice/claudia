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
* ``item`` — set when the paragraph is an item of a list (E9.21): which list, and at which level. It is *structure*;
  the bullet or number is never part of the text but derived from it (:mod:`claudia_core.lists`).

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

from .errors import Refusal
from .fields import FIELD_CHAR, Field, field_from_data, fields_before, plain
from .generated import Generated, generated_from_data

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


#: The deepest level of a list: levels run from 0 to this.
MAX_LIST_LEVEL = 8


@dataclass(frozen=True)
class ListItem:
    """A paragraph's membership of a list: the list's id (an entry of the document's
    :class:`~claudia_core.ListBook`) and the item's ``level``, 0 being the outermost."""

    list: str
    level: int = 0

    def check(self) -> None:
        """``ValueError`` with a sentence if the item makes no sense."""
        if not isinstance(self.level, int) or not 0 <= self.level <= MAX_LIST_LEVEL:
            raise ValueError(f"A list item's level is from 0 to {MAX_LIST_LEVEL}, got {self.level!r}")

    def to_data(self) -> dict:
        """The plain-data form: ``{list, level}``."""
        return {"list": self.list, "level": self.level}

    @classmethod
    def from_data(cls, data: dict) -> ListItem:
        """Inverse of :meth:`to_data`."""
        return cls(data["list"], data["level"])


@dataclass(frozen=True)
class Paragraph:
    """One paragraph: its id, its style, its characters, who wrote which of them, and the list it is an item of.

    ``runs`` always add up to the length of ``text``; :meth:`check` says so out loud. Immutable — see the module
    description for why that matters to undo."""

    id: str
    style: str
    text: str = ""
    runs: tuple[Run, ...] = field(default_factory=tuple)
    item: ListItem | None = None
    #: The options of a generated paragraph, a table of contents or an agenda (E9.31). Its entries are derived; it
    #: has no words of its own.
    generated: Generated | None = None
    #: The fields in the words, in order. The *k*-th U+FFFC of ``text`` is the *k*-th field (step H).
    fields: tuple[Field, ...] = ()

    def __len__(self) -> int:
        """The number of characters in the paragraph."""
        return len(self.text)

    def with_text(self, text: str, runs: Iterable[Run]) -> Paragraph:
        """The same paragraph with other words in it, and the runs that say who wrote them."""
        return replace(self, text=text, runs=tuple(normalized(runs)))

    def typed(self, offset: int, text: str, runs: Iterable[Run], fields: tuple[Field, ...] = ()) -> Paragraph:
        """The paragraph with ``text`` put in at ``offset``, written as ``runs`` say, with the ``fields`` of the U+FFFC
        in it. ``ValueError`` when they do not match, ``IndexError`` outside the words."""
        if not 0 <= offset <= len(self.text):
            raise IndexError("insert outside the text")
        if total(runs := list(runs)) != len(text):
            raise ValueError("the runs must cover exactly the inserted text")
        if text.count(FIELD_CHAR) != len(fields):
            raise ValueError("every field stands at one U+FFFC of the text that is put in")
        at = fields_before(self.text, offset)
        return replace(
            self,
            text=self.text[:offset] + text + self.text[offset:],
            runs=tuple(normalized(insert_runs(self.runs, offset, runs))),
            fields=(*self.fields[:at], *fields, *self.fields[at:]),
        )

    def cut(self, start: int, end: int) -> tuple[Paragraph, str, list[Run], tuple[Field, ...]]:
        """The paragraph without ``start <= i < end``, and what was cut: its words, runs and fields."""
        if not 0 <= start <= end <= len(self.text):
            raise IndexError("delete outside the text")
        first, last = fields_before(self.text, start), fields_before(self.text, end)
        kept = replace(
            self,
            text=self.text[:start] + self.text[end:],
            runs=tuple(normalized(delete_runs(self.runs, start, end))),
            fields=(*self.fields[:first], *self.fields[last:]),
        )
        return kept, self.text[start:end], slice_runs(self.runs, start, end), self.fields[first:last]

    def with_fields(self, fields: tuple[Field, ...]) -> Paragraph:
        """The same paragraph with other fields at its U+FFFC (as many as it has)."""
        if len(fields) != self.text.count(FIELD_CHAR):
            raise ValueError("every field stands at one U+FFFC of the text")
        return replace(self, fields=tuple(fields))

    def with_style(self, style: str) -> Paragraph:
        """The same paragraph under another style."""
        return replace(self, style=style)

    def with_item(self, item: ListItem | None) -> Paragraph:
        """The same paragraph as an item of a list (or, with ``None``, no longer one)."""
        return replace(self, item=item)

    def with_generated(self, generated: Generated | None) -> Paragraph:
        """The same paragraph generated as ``generated`` says (``None``: plain again). Only an empty paragraph can be
        generated: ``ValueError`` otherwise."""
        if generated is not None and self.text:
            raise Refusal("only an empty paragraph can become a table of contents")
        return replace(self, generated=generated)

    def written_by(self, author: str | None, via: str | None = None) -> Paragraph:
        """The same paragraph with all of its text attributed to one person: what setting the whole text at once
        means, as opposed to typing into it character by character."""
        return replace(self, runs=((Run(len(self.text), author, via),) if self.text else ()))

    def check(self) -> None:
        """``ValueError`` with a sentence if the paragraph does not hold together."""
        if not isinstance(self.text, str) or len(self.text) > MAX_PARAGRAPH_TEXT:
            raise Refusal(
                "a paragraph holds text of at most {limit} characters",
                limit=MAX_PARAGRAPH_TEXT,
            )
        if total(self.runs) != len(self.text):
            raise ValueError("the runs must cover exactly the paragraph's text")
        if self.item is not None:
            self.item.check()
        if self.generated is not None:
            self.generated.check()
            if self.text:
                raise ValueError("a generated paragraph has no words of its own")
        if self.text.count(FIELD_CHAR) != len(self.fields):
            raise ValueError("every field stands at one U+FFFC of the text, and every U+FFFC is a field")
        for found in self.fields:
            found.check()

    def to_data(self) -> dict:
        """The plain-data form: ``{id, style, text, runs}``, ``item`` when the paragraph is a list item and
        ``generated`` when it is generated. A paragraph that is neither is written exactly as before lists existed."""
        data: dict = {"id": self.id, "style": self.style, "text": self.text, "runs": runs_to_data(self.runs)}
        if self.item is not None:
            data["item"] = self.item.to_data()
        if self.generated is not None:
            data["generated"] = self.generated.to_data()
        if self.fields:
            data["fields"] = [f.to_data() for f in self.fields]
        return data

    @classmethod
    def from_data(cls, data: dict) -> Paragraph:
        """Inverse of :meth:`to_data`."""
        item, generated = data.get("item"), data.get("generated")
        return cls(
            data["id"],
            data["style"],
            data.get("text", ""),
            tuple(runs_from_data(data.get("runs", []))),
            None if item is None else ListItem.from_data(item),
            None if generated is None else generated_from_data(generated),
            tuple(field_from_data(f) for f in data.get("fields", ())),
        )


def replace_spans(paragraph: Paragraph, edits: Iterable[tuple[int, int, str]], author: str | None) -> Paragraph:
    """The paragraph with the stretches ``(start, end, text)`` replaced by their text, which ``author`` wrote.

    Everything outside the stretches keeps its words, its runs and its style, so replacing a term does not make the
    person who replaced it the author of the sentence around it. The stretches must not overlap; the order they are
    given in does not matter."""
    for start, end, new in sorted(edits, reverse=True):  # from the back, so that the offsets before it still hold
        paragraph = paragraph.cut(start, end)[0]
        words = plain(new)  # a replacement is words: it makes no field (the fields it cuts go with their U+FFFC)
        if words:
            paragraph = paragraph.typed(start, words, [Run(len(words), author)])
    return paragraph
