"""Page setup and language as a file says them: lengths, paper presets and language tags (D454).

A file says a page in its own units and may lie on its side; the model says it in mpt (thousandths of a point), short
side first, with the orientation apart (:class:`~claudia_core.PageSetup`). The functions here are the part of the
conversion that is the same for every format: reading a length, finding the preset a size is, and giving a size the
model can hold or saying that it cannot."""

from __future__ import annotations

import re

from claudia_core import PAPERS, LanguageError, PageSetup, PageSetupError, normalize_language
from claudia_core.page import DEFAULT_MARGIN

#: How far a size may be from a preset's and still be that paper: Word and LibreOffice round A4 differently.
PAPER_TOLERANCE = 1500  # mpt, a little over half a millimetre
_UNITS = {"mm": 72000 / 25.4, "cm": 720000 / 25.4, "in": 72000.0, "pt": 1000.0, "pc": 12000.0}
_LENGTH = re.compile(r"\s*(-?\d+(?:\.\d+)?|-?\.\d+)\s*(mm|cm|in|pt|pc)\s*")
#: What a file says when a text has no language: LibreOffice writes "zxx" ("no linguistic content") and "none".
NO_LANGUAGE = ("zxx", "none")


def length_to_mpt(text: str | None) -> int | None:
    """``text`` (``"21cm"``, ``"595.276pt"``) as mpt, or ``None`` when it is not a length in a unit a file uses."""
    found = _LENGTH.fullmatch(text) if text else None
    return round(float(found.group(1)) * _UNITS[found.group(2)]) if found else None


def mpt_to_points(mpt: int) -> str:
    """``mpt`` as a length in points, which says any whole number of mpt exactly (``"595.276pt"``)."""
    return f"{mpt / 1000:.3f}".rstrip("0").rstrip(".") + "pt"


def page_from_sizes(
    width: int | None,
    height: int | None,
    margins: tuple[int | None, int | None, int | None, int | None],
    *,
    landscape: bool | None = None,
    page_numbers: bool = False,
) -> PageSetup | None:
    """The page setup that a file's sizes say (mpt: the page's width and height as the file gives them, the margins
    top, right, bottom and left, with ``None`` where the file does not say), or ``None`` when the model cannot hold it
    (a side the file does not give, a page smaller than 25 mm or bigger than 1.2 m, margins that leave no room).
    A file lies on its side by giving the longer side as width; ``landscape`` (what the file says of it) decides when
    the two sides are equal. A size within :data:`PAPER_TOLERANCE` of a preset is that paper."""
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    short, long = sorted((width, height))
    lying = width > height if width != height else bool(landscape)
    edges = [DEFAULT_MARGIN if margin is None else max(margin, 0) for margin in margins]
    paper = next(
        (
            name
            for name, (preset_short, preset_long) in PAPERS.items()
            if abs(short - preset_short) <= PAPER_TOLERANCE and abs(long - preset_long) <= PAPER_TOLERANCE
        ),
        None,
    )
    try:
        if paper is not None:
            return PageSetup.preset(
                paper,
                orientation="landscape" if lying else "portrait",
                margin_top=edges[0],
                margin_right=edges[1],
                margin_bottom=edges[2],
                margin_left=edges[3],
                page_numbers=page_numbers,
            )
        return PageSetup(
            "custom",
            short,
            long,
            "landscape" if lying else "portrait",
            edges[0],
            edges[1],
            edges[2],
            edges[3],
            page_numbers,
        )
    except PageSetupError:
        return None


def sides_of(page: PageSetup) -> tuple[int, int]:
    """The width and height of the page as a file says them: the long side first when it lies on its side."""
    return (page.height, page.width) if page.orientation == "landscape" else (page.width, page.height)


def language_from_parts(language: str | None, script: str | None, country: str | None) -> str | None:
    """The BCP 47 tag of a file's language, script and country (``"de"``, ``None``, ``"AT"`` -> ``"de-AT"``), or
    ``None`` when it says none or something that is no tag."""
    if not language or language.lower() in NO_LANGUAGE:
        return None
    tag = "-".join(
        part for part in (language, script if script and script.lower() not in NO_LANGUAGE else None) if part
    )
    if country and country.lower() not in NO_LANGUAGE:
        tag += f"-{country}"
    try:
        return normalize_language(tag)
    except LanguageError:
        return None


def parts_of_language(tag: str | None) -> tuple[str, str | None, str | None]:
    """A BCP 47 tag as the language, script and country a file says it with (``"zxx"`` for none); what follows the
    region (variants) is not in the three, as in every office format."""
    if tag is None:
        return NO_LANGUAGE[0], None, None
    language, *rest = tag.split("-")
    script = next((part for part in rest if len(part) == 4 and part.isalpha()), None)
    country = next(
        (part for part in rest if (len(part) == 2 and part.isalpha()) or (len(part) == 3 and part.isdigit())), None
    )
    return language, script, country
