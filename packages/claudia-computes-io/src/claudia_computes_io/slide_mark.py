"""Which tabs of a file were slides (E6.31, D1478): the custom property "Claudia slides" of an xlsx file
(``docProps/custom.xml``) or an ods file (``meta:user-defined``), which every Office program shows and keeps.

The mark lists the tabs that are slides, by the name the file gives them, how big a slide was written on its tab, and
the style of each text box and shape on them and of its words, by the name of the box (D1479): a file says how a box
looks, not which style of the workbook gave it that look. Read back, a tab the mark names is a slide while it still
has that name and no cells; a tab that was renamed or typed into in another program is a sheet (and what is on it
hangs at its cells).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from ._placed import SlideSize

#: The name of the property.
MARK = "Claudia slides"


@dataclass(frozen=True)
class SlideMark:
    """The tabs that are slides, by name, the size they were written at, and the styles of the boxes on them: by the
    name of the box, the style of the box and the style of its words."""

    slides: tuple[str, ...]
    size: SlideSize
    styles: Mapping[str, tuple[str, str]] = field(default_factory=dict)

    def to_text(self) -> str:
        """The value of the property: ``{"slides": [...], "px_per_unit": 1.0, "styles": {name: [box, words]}}``."""
        styles = {name: list(pair) for name, pair in self.styles.items()}
        return json.dumps(
            {"slides": list(self.slides), "px_per_unit": self.size.px_per_unit, "styles": styles}, ensure_ascii=False
        )

    @classmethod
    def from_text(cls, text: str | None) -> SlideMark | None:
        """The mark a property says, or ``None`` for one that says none (no property, or one somebody changed into
        something else)."""
        try:
            found = json.loads(text or "")
            slides, scale, styles = found["slides"], float(found["px_per_unit"]), found.get("styles", {})
        except (ValueError, TypeError, KeyError, AttributeError):
            return None
        if not isinstance(slides, list) or not all(isinstance(name, str) for name in slides) or scale <= 0:
            return None
        if not isinstance(styles, dict):
            return None
        pairs = {
            name: (pair[0], pair[1])
            for name, pair in styles.items()
            if isinstance(pair, list) and len(pair) == 2 and all(isinstance(each, str) for each in pair)  # noqa: PLR2004
        }
        return cls(tuple(slides), SlideSize(scale), pairs)

    def slide_tabs(self, tabs: Iterable[tuple[str, str, bool]]) -> list[str]:
        """Of the tabs of a file, as ``(id, name, has cells)``, the ids of those that are slides: named by the mark,
        and without cells."""
        named = set(self.slides)
        return [tab_id for tab_id, name, has_cells in tabs if name in named and not has_cells]


def properties_of(names: Iterable[str], size: SlideSize, styles: Mapping[str, tuple[str, str]]) -> dict[str, str]:
    """The custom properties a file is written with: the mark of the slides ``names`` with the ``styles`` of their
    boxes, none when there are none."""
    slides = tuple(names)
    return {MARK: SlideMark(slides, size, dict(styles)).to_text()} if slides else {}
