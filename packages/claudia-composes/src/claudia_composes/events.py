"""State events the text model raises through ``Context.emit``: what a replica needs to follow the document.

Each event describes one step on the text, so a client that holds the paragraphs applies it to what it has, and
moves its own cursor through it, without asking for the document again.
"""

from __future__ import annotations

from dataclasses import dataclass

from claudia_core import Field, Generated, ListItem

from .runs import Run, runs_to_data


@dataclass(frozen=True)
class TextChanged:
    """``removed`` characters at ``offset`` of a paragraph were replaced by ``inserted``, written as ``runs``."""

    paragraph: str
    offset: int
    removed: int
    inserted: str
    runs: tuple[Run, ...] = ()

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "text",
            "paragraph": self.paragraph,
            "offset": self.offset,
            "removed": self.removed,
            "inserted": self.inserted,
            "runs": runs_to_data(list(self.runs)),
        }


@dataclass(frozen=True)
class ParagraphSplit:
    """The paragraph ``paragraph`` was cut at ``offset``; the rest is the new paragraph ``new_id``, right after it."""

    paragraph: str
    offset: int
    new_id: str
    style: str

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "split",
            "paragraph": self.paragraph,
            "offset": self.offset,
            "new_id": self.new_id,
            "style": self.style,
        }


@dataclass(frozen=True)
class ParagraphsJoined:
    """The paragraph ``paragraph`` was put at the end of ``into``, whose text was ``at`` characters long."""

    paragraph: str
    into: str
    at: int

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "join", "paragraph": self.paragraph, "into": self.into, "at": self.at}


@dataclass(frozen=True)
class StyleChanged:
    """The paragraph ``paragraph`` has another style."""

    paragraph: str
    style: str

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "style", "paragraph": self.paragraph, "style": self.style}


@dataclass(frozen=True)
class ItemChanged:
    """The paragraph ``paragraph`` is now this list item, or (``None``) no list item."""

    paragraph: str
    item: ListItem | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "item", "paragraph": self.paragraph, "item": None if self.item is None else self.item.to_data()}


@dataclass(frozen=True)
class FieldsPut:
    """The paragraph ``paragraph`` has these fields at its U+FFFC now (a reference put in, taken out or shown
    otherwise). What they read as comes as a ``fields`` event."""

    paragraph: str
    fields: tuple[Field, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "paragraph_fields", "paragraph": self.paragraph, "fields": [f.to_data() for f in self.fields]}


@dataclass(frozen=True)
class ParagraphGenerated:
    """The paragraph ``paragraph`` is now a table of contents with these options, or (``None``) a plain paragraph again.
    Its entries come as a ``generated`` event."""

    paragraph: str
    generated: Generated | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        options = None if self.generated is None else self.generated.to_data()
        return {"type": "paragraph_generated", "paragraph": self.paragraph, "generated": options}


@dataclass(frozen=True)
class SuggestionsChanged:
    """These suggestions are new or changed (state, place); a client replaces what it holds under their ids."""

    items: tuple[dict, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "suggestions", "items": list(self.items)}


@dataclass(frozen=True)
class PageSetupChanged:
    """The page the text is printed on changed (D904)."""

    setup: dict

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "page", "setup": dict(self.setup)}


# The language is the kernel's now (D917); its event is re-exported here, where it was first imported from.
from claudia_core import LanguageChanged  # noqa: E402,F401
