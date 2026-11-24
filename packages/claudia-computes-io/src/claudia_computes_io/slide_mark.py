"""Which tabs of a file were slides (E6.31, D1478): the custom property "Claudia slides" of an xlsx file
(``docProps/custom.xml``) or an ods file (``meta:user-defined``), which every Office program shows and keeps.

The mark lists the tabs that are slides, by the name the file gives them, and how big a slide was written on its tab.
Read back, a tab the mark names is a slide while it still has that name and no cells; a tab that was renamed or typed
into in another program is a sheet (and what is on it hangs at its cells).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass

from ._placed import SlideSize

#: The name of the property.
MARK = "Claudia slides"


@dataclass(frozen=True)
class SlideMark:
    """The tabs that are slides, by name, and the size they were written at."""

    slides: tuple[str, ...]
    size: SlideSize

    def to_text(self) -> str:
        """The value of the property: ``{"slides": [...], "px_per_unit": 1.0}``."""
        return json.dumps({"slides": list(self.slides), "px_per_unit": self.size.px_per_unit}, ensure_ascii=False)

    @classmethod
    def from_text(cls, text: str | None) -> SlideMark | None:
        """The mark a property says, or ``None`` for one that says none (no property, or one somebody changed into
        something else)."""
        try:
            found = json.loads(text or "")
            slides, scale = found["slides"], float(found["px_per_unit"])
        except (ValueError, TypeError, KeyError):
            return None
        if not isinstance(slides, list) or not all(isinstance(name, str) for name in slides) or scale <= 0:
            return None
        return cls(tuple(slides), SlideSize(scale))

    def slide_tabs(self, tabs: Iterable[tuple[str, str, bool]]) -> list[str]:
        """Of the tabs of a file, as ``(id, name, has cells)``, the ids of those that are slides: named by the mark,
        and without cells."""
        named = set(self.slides)
        return [tab_id for tab_id, name, has_cells in tabs if name in named and not has_cells]


def properties_of(names: Iterable[str], size: SlideSize) -> dict[str, str]:
    """The custom properties a file is written with: the mark of the slides ``names``, none when there are none."""
    slides = tuple(names)
    return {MARK: SlideMark(slides, size).to_text()} if slides else {}
