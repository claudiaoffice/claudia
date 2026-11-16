"""How the levels of a numbering scheme are said in a docx, both ways (E9.22, step D); an odt says them as
:mod:`claudia_odf_io.lists` does.

A scheme of the model (:class:`claudia_core.Scheme`) has nine levels; each writes its counter in a format, or a
bullet, with text before and after, and shows the counters from some level on (``2.1.3`` or ``c``). Word says the
same with a number format and a level text (``%1.%2.``). What a file draws that a level cannot say (another separator
than a full stop, a picture bullet, an ordinal) is not read as a scheme: the list keeps the nearest built-in one and
its look is reported.

When a list is read, its levels are compared with the schemes the document has; a file's list that looks like one
of them is drawn with it, any other look becomes a scheme of its own, named after the list.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from claudia_core import MAX_LIST_LEVEL, LevelFormat, SchemeBook

#: A model format and what Word calls it.
WORD_FORMATS = {
    "decimal": "decimal",
    "lower-alpha": "lowerLetter",
    "upper-alpha": "upperLetter",
    "lower-roman": "lowerRoman",
    "upper-roman": "upperRoman",
    "bullet": "bullet",
    "none": "none",
}
_FROM_WORD = {word: model for model, word in WORD_FORMATS.items()}
_PLACE = re.compile(r"%([1-9])")
_MAX_AFFIX = 20


def _affix(text: str) -> bool:
    return len(text) <= _MAX_AFFIX and (not text or text.isprintable())


# -- Word ------------------------------------------------------------------------------------------------------------
def word_level(level: LevelFormat, number: int) -> tuple[str, str]:
    """The ``w:numFmt`` and ``w:lvlText`` of ``level`` at level ``number`` (0 the outermost)."""
    if level.format == "bullet":
        return "bullet", f"{level.before}{level.bullet}{level.after}"
    if level.format == "none":
        return "none", f"{level.before}{level.after}"
    places = ".".join(f"%{k + 1}" for k in range(level.from_level, number + 1))
    return WORD_FORMATS[level.format], f"{level.before}{places}{level.after}"


def read_word_level(number_format: str | None, text: str | None, number: int) -> LevelFormat | None:
    """The level a docx's ``w:numFmt`` and ``w:lvlText`` say, at level ``number``; ``None`` when a level of the model
    cannot say it."""
    model = _FROM_WORD.get(number_format or "decimal")
    text = text or ""
    if model is None:
        return None
    if model == "bullet":
        return LevelFormat("bullet", text, from_level=number) if 1 <= len(text) <= 4 and text.isprintable() else None
    places = list(_PLACE.finditer(text))
    if model == "none" or not places:
        return LevelFormat("none", before=text, from_level=number) if _affix(text) and not places else None
    levels = [int(place.group(1)) - 1 for place in places]
    if levels != list(range(levels[0], number + 1)):
        return None  # not the trail of counters down to its own, in order
    between = [text[a.end() : b.start()] for a, b in zip(places, places[1:], strict=False)]
    before, after = text[: places[0].start()], text[places[-1].end() :]
    if any(gap != "." for gap in between) or not (_affix(before) and _affix(after)):
        return None
    return LevelFormat(model, before=before, after=after, from_level=levels[0])


# -- schemes from what a file says -----------------------------------------------------------------------------------
def scheme_for(
    levels: Mapping[int, LevelFormat | None], counts: bool, name: str | None, book: SchemeBook
) -> str | None:
    """The id of the scheme of ``book`` that draws a list with these ``levels`` (by level number, ``None`` for a level
    the model cannot say), adding one to ``book`` if none does. ``None`` when a level cannot be said: the caller then
    falls back on a built-in scheme and reports the look."""
    if any(level is None for level in levels.values()):
        return None
    return book.drawing(
        {n: level for n, level in levels.items() if level is not None and n <= MAX_LIST_LEVEL}, counts, name
    )
