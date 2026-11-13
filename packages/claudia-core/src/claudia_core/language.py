"""The language of a document (D915, D917): a BCP 47 tag such as ``de``, ``en-GB`` or ``sr-Latn-RS``, or none.

The layout library hyphenates a paragraph by the patterns of its language (D912), and hands the tag to the shaping
engine and into the PDF. The tag is part of the document, so every client hyphenates the same text the same way. A
document whose language is not known is not hyphenated, and the print preview says so.

Shared by the apps that print (composes, creates): a model that has a language has a ``language`` attribute, and
:class:`SetLanguage` changes it in one step, with the event :class:`LanguageChanged`.

The tag is checked for its shape only (a language of two or three letters, then a script of four letters, a region
of two letters or three digits, and variants), and written the way BCP 47 recommends: ``EN-gb`` becomes ``en-GB``.
Whether patterns exist for it is the server's business, not the document's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from .commands import Command, CommandRegistry, core_commands

if TYPE_CHECKING:
    from .context import Context

_SHAPE = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{1,8})*")
MAX_LENGTH = 35


class LanguageError(ValueError):
    """Not a language tag; the message says why."""


def normalize_language(tag: str) -> str:
    """``tag`` written as BCP 47 recommends; :class:`LanguageError` if it is not one."""
    if not isinstance(tag, str) or len(tag) > MAX_LENGTH or not _SHAPE.fullmatch(tag.strip()):
        raise LanguageError(f"{str(tag)[:40]!r} is not a language tag like de, en-GB or sr-Latn-RS")
    parts = tag.strip().split("-")
    out = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            out.append(part.title())
        elif (len(part) == 2 and part.isalpha()) or (len(part) == 3 and part.isdigit()):
            out.append(part.upper())
        else:
            out.append(part.lower())
    return "-".join(out)


@dataclass(frozen=True)
class LanguageChanged:
    """The language of the document changed; ``None`` when it is no longer set."""

    language: str | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "language", "language": self.language}


@core_commands.register
@dataclass(frozen=True)
class SetLanguage(Command):
    """Say which language the document is written in (a BCP 47 tag), or that it is not known (``None``). The layout
    hyphenates by it (D912). One step in the history, shared by everybody."""

    kind: ClassVar[str] = "core.SetLanguage"
    language: str | None

    def __post_init__(self) -> None:
        if self.language is not None:
            object.__setattr__(self, "language", normalize_language(self.language))

    @property
    def label(self) -> str:
        return "Language"

    @property
    def summary(self) -> str:
        return f"set the language to {self.language}" if self.language else "removed the language"

    def apply(self, ctx: Context) -> Command:
        model = ctx.model
        if not hasattr(model, "language"):
            raise TypeError(f"a {model.app} document has no language")
        old = model.language
        model.language = self.language
        ctx.emit(LanguageChanged(self.language))
        return SetLanguage(old)

    def to_data(self) -> dict:
        return {"language": self.language}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetLanguage:
        return cls(data["language"])
