"""The language of a text (D915): a BCP 47 tag such as ``de``, ``en-GB`` or ``sr-Latn-RS``, or none.

The layout library hyphenates a paragraph by the patterns of its language (D912), and hands the tag to the shaping
engine and into the PDF. The tag is part of the document, so every client hyphenates the same text the same way. A
text whose language is not known is not hyphenated, and the print preview says so.

The tag is checked for its shape only (a language of two or three letters, then a script of four letters, a region
of two letters or three digits, and variants), and written the way BCP 47 recommends: ``EN-gb`` becomes ``en-GB``.
Whether patterns exist for it is the server's business, not the document's.
"""

from __future__ import annotations

import re

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
