"""State events the text model raises through ``Context.emit``: what a replica needs to follow the document.

Each event describes one step on the text, so a client that holds the paragraphs applies it to what it has, and
moves its own cursor through it, without asking for the document again.
"""

from __future__ import annotations

from dataclasses import dataclass

from claudia_core import Label, ListItem

from .runs import Run, runs_to_data


@dataclass(frozen=True)
class TextChanged:
    """``removed`` characters at ``offset`` of a paragraph were replaced by ``inserted``, written as ``runs``."""

    block: str
    offset: int
    removed: int
    inserted: str
    runs: tuple[Run, ...] = ()

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "text",
            "block": self.block,
            "offset": self.offset,
            "removed": self.removed,
            "inserted": self.inserted,
            "runs": runs_to_data(list(self.runs)),
        }


@dataclass(frozen=True)
class BlockSplit:
    """The paragraph ``block`` was cut at ``offset``; the rest is the new paragraph ``new_id``, right after it."""

    block: str
    offset: int
    new_id: str
    style: str

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "split", "block": self.block, "offset": self.offset, "new_id": self.new_id, "style": self.style}


@dataclass(frozen=True)
class BlocksJoined:
    """The paragraph ``block`` was put at the end of ``into``, whose text was ``at`` characters long."""

    block: str
    into: str
    at: int

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "join", "block": self.block, "into": self.into, "at": self.at}


@dataclass(frozen=True)
class StyleChanged:
    """The paragraph ``block`` has another style."""

    block: str
    style: str

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "style", "block": self.block, "style": self.style}


@dataclass(frozen=True)
class ItemChanged:
    """The paragraph ``block`` is now this list item, or (``None``) no list item."""

    block: str
    item: ListItem | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "item", "block": self.block, "item": None if self.item is None else self.item.to_data()}


@dataclass(frozen=True)
class LabelsChanged:
    """These paragraphs have another marker (or, with ``None``, none any more). Only what differs from what the
    clients were last told is in it, so typing, which changes no label, sends nothing."""

    labels: tuple[tuple[str, Label | None], ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "labels",
            "labels": {block: None if label is None else label.to_data() for block, label in self.labels},
        }


@dataclass(frozen=True)
class SuggestionsChanged:
    """These suggestions are new or changed (state, place); a client replaces what it holds under their ids."""

    items: tuple[dict, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "suggestions", "items": list(self.items)}


@dataclass(frozen=True)
class LanguageChanged:
    """The language of the text changed (D915); ``None`` when it is no longer set."""

    language: str | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "language", "language": self.language}


@dataclass(frozen=True)
class PageSetupChanged:
    """The page the text is printed on changed (D904)."""

    setup: dict

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "page", "setup": dict(self.setup)}
