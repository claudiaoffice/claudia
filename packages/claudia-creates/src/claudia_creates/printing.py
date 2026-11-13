"""How a presentation is printed (D917): which layout, on which page.

``slides`` puts one slide on each page, scaled to fit inside the margins; on the ``slide`` paper with no margins the
page is the slide, edge to edge. ``handouts-N`` puts N slides on each page in a grid (2, 4, 6, 9), or three beside
lines for notes (3). The page is the kernel's :class:`~claudia_core.PageSetup`, the same one composes prints its
text on, so the paper, orientation, margins and page numbers mean the same in both apps.

The setup is part of the presentation, like a text's page (D904): changing it is one step for everybody, so every
preview and every PDF of a deck are the same. The layout itself happens in the client (D901).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self

from claudia_core import PageSetup

#: The layouts, in the order the print preview offers them.
LAYOUTS: tuple[str, ...] = ("slides", "handouts-2", "handouts-3", "handouts-4", "handouts-6", "handouts-9")


class PrintSetupError(ValueError):
    """A print setup that cannot be used; the message says which part."""


def _slide_page() -> PageSetup:
    return PageSetup.preset(
        "slide", orientation="landscape", margin_top=0, margin_right=0, margin_bottom=0, margin_left=0
    )


@dataclass(frozen=True)
class PrintSetup:
    """A layout and the page it is printed on. A new presentation prints its slides one to a page, slide-sized."""

    layout: str = "slides"
    page: PageSetup = field(default_factory=_slide_page)

    def __post_init__(self) -> None:
        if self.layout not in LAYOUTS:
            raise PrintSetupError(f"unknown layout {self.layout!r}: one of {', '.join(LAYOUTS)}")
        if not isinstance(self.page, PageSetup):
            raise PrintSetupError("the page is a PageSetup")

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {"layout": self.layout, "page": self.page.to_data()}

    @classmethod
    def from_data(cls, data: object) -> Self:
        """Read a setup sent by a client or stored in the log; :class:`~claudia_core.PageSetupError` or
        :class:`PrintSetupError` if it is not a usable one."""
        if not isinstance(data, dict) or not isinstance(data.get("layout"), str):
            raise PrintSetupError("a print setup is an object with a layout and a page")
        return cls(data["layout"], PageSetup.from_data(data.get("page")))

    def describe(self) -> str:
        """A few words for the history: ``slides on A4, landscape`` or ``6 slides a page on A4, portrait``."""
        what = "slides" if self.layout == "slides" else f"{self.layout.split('-')[1]} slides a page"
        return f"{what} on {self.page.describe()}"
