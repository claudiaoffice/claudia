"""Names of things (D550, D551): what a name is, when two names are the same, and the name a new thing gets.

Objects, slides, sheets and chart tabs of one document share one namespace, so that a person who says "figure 1" (or
types it behind a ``#`` in the chat) always means one thing. This module is the rule alone: pure functions on text.
Where a document keeps its names and who may set them is :class:`~claudia_core.ObjectModel`'s and the apps' business.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

#: The longest name a thing may have, in characters.
MAX_THING_NAME = 60


def clean_name(text: str) -> str:
    """``text`` with the spaces around it removed and every run of white space inside it made one space."""
    return " ".join(text.split())


def name_key(text: str) -> str:
    """What two names are compared by: the cleaned name in lower case, so "Figure  1" and "figure 1" are one name.

    ``casefold`` rather than ``lower``, so that "Straße" and "STRASSE" are one name as well."""
    return clean_name(text).casefold()


def name_problem(text: str) -> str | None:
    """Why ``text`` cannot be a name (a sentence for a dialog), or ``None`` when it can. Spaces, umlauts and ``#`` are
    all fine: a tag in the chat is made by picking a thing, not by parsing text, so a name needs no special syntax."""
    if any(unicodedata.category(c) == "Cc" for c in text):
        return "a name has no control characters"
    cleaned = clean_name(text)
    if not cleaned:
        return "a name needs some text"
    if len(cleaned) > MAX_THING_NAME:
        return f"a name has at most {MAX_THING_NAME} characters"
    return None


def free_name(label: str, taken: Iterable[str]) -> str:
    """The name a new thing of kind ``label`` gets: ``"<label> <n>"`` with the smallest ``n`` from 1 that is not
    taken, "taken" being decided by :func:`name_key`."""
    used = {name_key(name) for name in taken}
    number = 1
    while name_key(f"{label} {number}") in used:
        number += 1
    return f"{label} {number}"
