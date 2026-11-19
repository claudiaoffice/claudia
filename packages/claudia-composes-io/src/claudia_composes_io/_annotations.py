"""What a person wrote about the text, in a docx or an odt: names and descriptions (E1.13, D1311, D1318).

**Writing.** A paragraph a person *gave* a name is a bookmark around its words, so Word's and LibreOffice's "go to
bookmark" finds it; a name that was only worked out (a generic "Paragraph 4", the title of a heading) is not written.
What a person wrote *about* a paragraph is a review comment, when the person exporting asks for it, by the person
exporting and dated the day of the export (A6). Which names were given and which were worked out is for the caller
to say: it knows the language of the generic names.

**Reading.** A bookmark around the words of exactly one paragraph is the name of that paragraph. A bookmark a program
makes for itself (starting with ``_``, claudia's ``ref-``), one around a part of a paragraph, one around several, and
one that is no name are left alone. Comments are not read back as descriptions (A7).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from claudia_core import clean_name, distinct_name, name_problem

_NOT_WORD = re.compile(r"[^\w]")
_WORD_MAX = 40  # Word's longest bookmark name


@dataclass(frozen=True)
class Annotations:
    """What an export writes about the paragraphs besides their words, by paragraph id.

    ``names`` are the names a person gave (written as bookmarks), ``comments`` what a person wrote about a paragraph
    (written as review comments by ``author`` at ``when``, an ISO 8601 date and time)."""

    names: Mapping[str, str] = field(default_factory=dict)
    comments: Mapping[str, str] = field(default_factory=dict)
    author: str = ""
    when: str = ""


def word_bookmark_names(names: Iterable[str]) -> list[str]:
    """The names a docx can hold for ``names``, one each and all different: Word allows letters, digits and ``_``,
    starting with a letter, up to 40 characters, so a space becomes ``_`` and a name that starts otherwise gets an
    ``N``. Two names that come to the same are told apart by a number."""
    used: set[str] = set()
    made = []
    for name in names:
        base = _NOT_WORD.sub("_", clean_name(name))
        if not base[:1].isalpha():
            base = "N" + base
        base = base[:_WORD_MAX]
        candidate, number = base, 1
        while candidate.casefold() in used:
            number += 1
            tail = f"_{number}"
            candidate = base[: _WORD_MAX - len(tail)] + tail
        used.add(candidate.casefold())
        made.append(candidate)
    return made


def is_technical(bookmark: str) -> bool:
    """Is this a bookmark a program makes for itself (a contents entry, "where I was", a reference), not a name?"""
    return bookmark.startswith(("_", "ref-"))


def name_of_bookmark(bookmark: str, *, spaces: bool) -> str | None:
    """The name a bookmark gives, or ``None`` when it gives none. ``spaces``: the file's format cannot hold a space in
    a bookmark (docx), so a ``_`` is read as one."""
    if is_technical(bookmark):
        return None
    name = clean_name(bookmark.replace("_", " ") if spaces else bookmark)
    return None if name_problem(name) else name


def name_paragraphs(model, bookmarks: Mapping[str, list[str]], *, spaces: bool) -> None:  # noqa: ANN001
    """Give the paragraphs of ``model`` the names of the bookmarks around them: ``bookmarks`` has the bookmarks around
    exactly one paragraph, by its id. The first that gives a name is taken; a name somebody has already gets a number
    (``distinct_name``); a heading keeps being called by its title."""
    taken = [name for _kind, _thing, name in model.named_things()]
    for block in model.blocks:
        if model.name_is_fixed(block.id):
            continue
        for bookmark in bookmarks.get(block.id, ()):
            name = name_of_bookmark(bookmark, spaces=spaces)
            if name is None:
                continue
            name = distinct_name(name, taken)
            model.set_thing_name(block.id, name)
            taken.append(name)
            break
