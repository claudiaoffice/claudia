"""The text structure every app shares (step C of ``claudiaoffice-log/notes/text-structure-across-apps.md``).

What an app knows of its paragraphs is *where they are*: composes has a body with objects hanging from it, creates has
slides with text boxes, computes has sheets with objects. What follows from that is the same in every app and is
worked out here, once: which list items count together and so what each one's label is, and what the clients have to
be told about it.

* A :class:`ParagraphHost` is the one thing an app writes for itself: its paragraphs in the order they are read
  (:class:`Placed`), its books of styles, lists and schemes, and a ``structure_version`` that changes whenever that
  order or a paragraph's place in a list may have changed (an item set, a paragraph split or joined, an object added
  or taken away, a slide removed). Typing changes none of it.
* A :class:`TextStructure` belongs to one model. It counts the items in reading order with
  :func:`~claudia_core.numbering_labels`, keeps the answer until the structure, the styles, the lists or the schemes
  change, and in ``settle`` tells the clients the labels that differ from what they were told (:class:`LabelsChanged`).
* A paragraph's **effective item** is its own item, else the one its style gives it (step D, numbered headings): a
  style with a heading level of 1 or more that names a list makes its paragraphs items of that list, at the level
  below their heading level. Only paragraphs of the main text get one: words floating beside a text are no headings.

* The **entries** of a table of contents (an agenda) are the headings of the main text whose level it lists, with their
  numbers and, where the kernel knows it, their place (a slide number); see :mod:`claudia_core.generated`.

Later steps add to this class what a reference shows.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Iterator
from dataclasses import dataclass
from typing import NamedTuple, Protocol

from .generated import CONTENTS_STYLE, ContentsEntry, Generated, GeneratedChanged
from .lists import Label, ListBook, numbering_labels
from .paragraphs import MAX_LIST_LEVEL, ListItem, Paragraph
from .schemes import SchemeBook
from .styles import StyleBook


class Placed(NamedTuple):
    """A paragraph where it is read: its ``container`` (a paragraph of the body, a slide, a sheet), whether it is part
    of the ``main`` text (it counts for the outline and a table of contents; a floating object's words in a text do
    not), and the ``place`` a reader finds it at when the app knows it without laying anything out (a slide's number),
    else ``None``."""

    paragraph: Paragraph
    container: str
    main: bool
    place: str | None


class ParagraphHost(Protocol):
    """What an app gives the shared text structure: its paragraphs in reading order and the books they refer to."""

    styles: StyleBook
    lists: ListBook
    schemes: SchemeBook

    def reading_order(self) -> Iterable[Placed]:
        """Every paragraph of the document, in the order it is read."""
        ...

    @property
    def structure_version(self) -> Hashable:
        """Changes whenever the reading order or a paragraph's place in a list may have changed."""
        ...


@dataclass(frozen=True)
class LabelsChanged:
    """These paragraphs have another label (or, with ``None``, none any more), by paragraph id: a paragraph of a text
    or the words of an object. Only what differs from what the clients were last told is in it, so typing, which
    changes no label, sends nothing."""

    labels: tuple[tuple[str, Label | None], ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "labels",
            "labels": {paragraph: None if label is None else label.to_data() for paragraph, label in self.labels},
        }


class Emitter(Protocol):
    """Whatever ``settle`` tells the clients through: a command's context (anything with ``emit``)."""

    def emit(self, event: object) -> None:
        """Send an event to the clients."""
        ...


class TextStructure:
    """What is derived from the structure of one document's paragraphs: the label of every list item and of every
    numbered heading, and the entries of every table of contents (agenda)."""

    def __init__(self, host: ParagraphHost) -> None:
        self.host = host
        self._key: tuple[Hashable, int, int, int] | None = None
        self._labels: dict[str, Label] = {}
        self._generated_key: Hashable = None
        self._generated: dict[str, tuple[Placed, Generated]] = {}
        #: The labels the clients have been told about (with the document, then by ``settle``).
        self._told: dict[str, Label] = self.labels()
        #: The entries of each generated paragraph the clients have been told about.
        self._told_entries: dict[str, tuple[ContentsEntry, ...]] = self.all_entries()

    def reading_order(self) -> Iterator[Placed]:
        """The host's paragraphs in the order they are read."""
        yield from self.host.reading_order()

    def effective_item(self, placed: Placed) -> ListItem | None:
        """The list item a paragraph is: its own, else (in the main text) the one its style gives it."""
        own = placed.paragraph.item
        return self._numbered(placed.paragraph, {}) if own is None and placed.main else own

    def _numbered(self, paragraph: Paragraph, seen: dict[str, ListItem | None]) -> ListItem | None:
        """The item a paragraph's style gives it; ``seen`` keeps the answer per style while one count runs."""
        if paragraph.style not in seen:
            styles = self.host.styles
            item = None
            if paragraph.style in styles:
                level, numbering = styles.heading_level(paragraph.style), styles.numbering(paragraph.style)
                if numbering is not None and numbering in self.host.lists and level is not None and level >= 1:
                    item = ListItem(numbering, min(level - 1, MAX_LIST_LEVEL))
            seen[paragraph.style] = item
        return seen[paragraph.style]

    def items(self) -> Iterator[tuple[str, ListItem | None]]:
        """Every paragraph id with its effective item, in reading order."""
        seen: dict[str, ListItem | None] = {}
        for placed in self.reading_order():
            own = placed.paragraph.item
            if own is None and placed.main:
                own = self._numbered(placed.paragraph, seen)
            yield placed.paragraph.id, own

    def labels(self) -> dict[str, Label]:
        """The label of every list item and numbered heading, by paragraph id, counted in reading order. Worked out
        again only when the structure, the styles, the lists or the schemes changed since last time; the answer is
        shared, so callers must not change it."""
        host = self.host
        key = (host.structure_version, host.styles.version, host.lists.version, host.schemes.version)
        if self._key != key:
            self._labels = numbering_labels(self.items(), host.lists, host.schemes)
            self._key = key
        return self._labels

    # -- tables of contents (step E) -----------------------------------------------------------------
    def generated(self) -> dict[str, tuple[Placed, Generated]]:
        """Every generated paragraph, by id, with its options. Looked for again only when the structure changed (a
        paragraph made generated or plain again changes it)."""
        key = self.host.structure_version
        if self._generated_key != key:
            self._generated = {
                placed.paragraph.id: (placed, placed.paragraph.generated)
                for placed in self.reading_order()
                if placed.paragraph.generated is not None
            }
            self._generated_key = key
        return self._generated

    def outline(self) -> list[tuple[Placed, int]]:
        """Every heading of the main text with its level (1 or deeper: the title, level 0, names the document and is
        never listed), in reading order; generated paragraphs are no headings."""
        styles, found = self.host.styles, []
        for placed in self.reading_order():
            paragraph = placed.paragraph
            if not placed.main or paragraph.generated is not None or paragraph.style not in styles:
                continue
            level = styles.heading_level(paragraph.style)
            if isinstance(level, int) and level >= 1:
                found.append((placed, level))
        return found

    def all_entries(self) -> dict[str, tuple[ContentsEntry, ...]]:
        """The entries of every table of contents, by its paragraph id. A document without one costs nothing."""
        generated = self.generated()
        if not generated:
            return {}
        outline, labels, styles = self.outline(), self.labels(), self.host.styles
        found: dict[str, tuple[ContentsEntry, ...]] = {}
        for paragraph_id, (own, options) in generated.items():
            entries = []
            for placed, level in outline:
                if not options.lists(level):
                    continue
                label = labels.get(placed.paragraph.id)
                wanted = CONTENTS_STYLE.format(level=level)
                entries.append(
                    ContentsEntry(
                        placed.paragraph.id,
                        level,
                        label.number if options.numbers and label is not None else None,
                        placed.paragraph.text,
                        wanted if wanted in styles else own.paragraph.style,
                        placed.place if options.places else None,
                    )
                )
            found[paragraph_id] = tuple(entries)
        return found

    def entries(self, paragraph_id: str) -> tuple[ContentsEntry, ...]:
        """The entries of one table of contents; none for a paragraph that is not one."""
        return self.all_entries().get(paragraph_id, ())

    def settle(self, ctx: Emitter) -> None:
        """Tell the clients which labels and which entries of tables of contents changed: one item set may have
        renumbered a hundred others, one retyped heading changes an entry. A paragraph that is no longer there is not
        mentioned (its client drops it with the paragraph)."""
        self._settle_entries(ctx)
        now = self.labels()
        if now is self._told or now == self._told:
            return
        changed: list[tuple[str, Label | None]] = [
            (paragraph, label) for paragraph, label in now.items() if self._told.get(paragraph) != label
        ]
        gone = [paragraph for paragraph in self._told if paragraph not in now]
        if gone:
            present = {placed.paragraph.id for placed in self.reading_order()}
            changed += [(paragraph, None) for paragraph in gone if paragraph in present]
        self._told = now
        if changed:
            ctx.emit(LabelsChanged(tuple(changed)))

    def _settle_entries(self, ctx: Emitter) -> None:
        now = self.all_entries()
        if now == self._told_entries:
            return
        for paragraph_id, entries in now.items():
            if self._told_entries.get(paragraph_id) != entries:
                ctx.emit(GeneratedChanged(paragraph_id, entries))
        gone = [paragraph_id for paragraph_id in self._told_entries if paragraph_id not in now]
        if gone:
            present = {placed.paragraph.id for placed in self.reading_order()}
            for paragraph_id in gone:
                if paragraph_id in present:
                    ctx.emit(GeneratedChanged(paragraph_id, None))
        self._told_entries = now
