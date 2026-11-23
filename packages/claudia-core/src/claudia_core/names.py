"""Names of things (D550, D551): what a name is, when two names are the same, and the name a new thing gets.

Objects, slides, sheets and chart tabs of one document share one namespace, so that a person who says "figure 1" (or
types it behind a ``#`` in the chat) always means one thing. This module is the rule alone: pure functions on text.
Where a document keeps its names and who may set them is :class:`~claudia_core.ObjectModel`'s and the apps' business.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

from .errors import Refusal

#: The longest name a thing may have, in characters.
MAX_THING_NAME = 60


def clean_name(text: str) -> str:
    """``text`` with the spaces around it removed and every run of white space inside it made one space."""
    return " ".join(text.split())


def name_key(text: str) -> str:
    """What two names are compared by: the cleaned name in lower case, so "Figure  1" and "figure 1" are one name.

    ``casefold`` rather than ``lower``, so that "Straße" and "STRASSE" are one name as well."""
    return clean_name(text).casefold()


def name_problem(text: str) -> Refusal | None:
    """Why ``text`` cannot be a name (the refusal to raise or to say in a dialog), or ``None`` when it can. Spaces,
    umlauts and ``#`` are all fine: a tag in the chat is made by picking a thing, not by parsing text, so a name needs
    no special syntax."""
    if any(unicodedata.category(c) == "Cc" for c in text):
        return Refusal("a name has no control characters")
    cleaned = clean_name(text)
    if not cleaned:
        return Refusal("a name needs some text")
    if len(cleaned) > MAX_THING_NAME:
        return Refusal("a name has at most {limit} characters", limit=MAX_THING_NAME)
    return None


def free_name(label: str, taken: Iterable[str]) -> str:
    """The name a new thing of kind ``label`` gets: ``"<label> <n>"`` with the smallest ``n`` from 1 that is not
    taken, "taken" being decided by :func:`name_key`."""
    used = {name_key(name) for name in taken}
    number = 1
    while name_key(f"{label} {number}") in used:
        number += 1
    return f"{label} {number}"


def distinct_name(name: str, taken: Iterable[str]) -> str:
    """``name`` itself when nobody has it (by :func:`name_key`), else the first free ``"<name> (<n>)"`` from 2.

    Used where a name is *worked out* rather than chosen (a heading is called by its title, D1311, A3 of the E1
    architecture; a generic name that two people made at once): the same state always gives the same answer. The
    number fits inside :data:`MAX_THING_NAME` by shortening ``name``."""
    used = {name_key(other) for other in taken}
    if name_key(name) not in used:
        return name
    number = 2
    while True:
        suffix = f" ({number})"
        candidate = clean_name(name[: MAX_THING_NAME - len(suffix)]) + suffix
        if name_key(candidate) not in used:
            return candidate
        number += 1


def free_names(label: str, taken: Iterable[str], count: int) -> list[str]:
    """``count`` names for new things of kind ``label``: what :func:`free_name` gives, one after the other, each
    counting the ones before it as taken. Reads ``taken`` once, so a paste of two thousand paragraphs into a text of
    fifty thousand does not read every name two thousand times."""
    used = {name_key(name) for name in taken}
    made: list[str] = []
    number = 1
    while len(made) < count:
        candidate = f"{label} {number}"
        number += 1
        if name_key(candidate) not in used:
            used.add(name_key(candidate))
            made.append(candidate)
    return made
