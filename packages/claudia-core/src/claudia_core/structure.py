"""The text structure every app shares (step C of ``claudiaoffice-log/notes/text-structure-across-apps.md``).

What an app knows of its paragraphs is *where they are*: composes has a body with objects hanging from it, creates has
slides with text boxes, computes has sheets with objects. What follows from that is the same in every app and is
worked out here, once: which list items count together and so what each one's label is, and what the clients have to
be told about it.

* A :class:`ParagraphHost` is the one thing an app writes for itself: its paragraphs in the order they are read
  (:class:`Placed`), its style book and its list book, and a ``structure_version`` that changes whenever that order or
  a paragraph's place in a list may have changed (an item set, a paragraph split or joined, an object added or taken
  away, a slide removed). Typing changes none of it.
* A :class:`TextStructure` belongs to one model. It counts the items in reading order with
  :func:`~claudia_core.numbering_labels`, keeps the answer until the structure or the lists change, and in ``settle``
  tells the clients the labels that differ from what they were told (:class:`LabelsChanged`).

Steps D and later add to this class what else is derived from the structure: an item a paragraph gets from its style
(numbered headings), the outline, the entries of a table of contents and what a reference shows.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Iterator
from dataclasses import dataclass
from typing import NamedTuple, Protocol

from .lists import Label, ListBook, numbering_labels
from .paragraphs import ListItem, Paragraph
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
    """What is derived from the structure of one document's paragraphs: today the label of every list item."""

    def __init__(self, host: ParagraphHost) -> None:
        self.host = host
        self._key: tuple[Hashable, int] | None = None
        self._labels: dict[str, Label] = {}
        #: The labels the clients have been told about (with the document, then by ``settle``).
        self._told: dict[str, Label] = self.labels()

    def reading_order(self) -> Iterator[Placed]:
        """The host's paragraphs in the order they are read."""
        yield from self.host.reading_order()

    def effective_item(self, paragraph: Paragraph) -> ListItem | None:
        """The list item a paragraph is: its own."""
        return paragraph.item

    def labels(self) -> dict[str, Label]:
        """The label of every list item, by paragraph id, counted in reading order. Worked out again only when the
        structure or the lists changed since last time; the answer is shared, so callers must not change it."""
        key = (self.host.structure_version, self.host.lists.version)
        if self._key != key:
            self._labels = numbering_labels(
                ((placed.paragraph.id, self.effective_item(placed.paragraph)) for placed in self.reading_order()),
                self.host.lists,
            )
            self._key = key
        return self._labels

    def settle(self, ctx: Emitter) -> None:
        """Tell the clients which labels changed: one item set may have renumbered a hundred others. A paragraph that
        is no longer there is not mentioned (its client drops it with the paragraph)."""
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
