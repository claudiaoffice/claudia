"""The page a text is printed on (E9.14 first step, D904): paper size, orientation, margins, page numbers.

Pages are laid out in the client, by the layout library (D901); the document only says which page to lay out on, so
that everybody's preview and PDF are the same. Every length is a whole number of *mpt* (thousandths of a point), the
unit of the layout library, so the stored value is exactly the one the layout uses. The paper is named by a preset
(``a4``, ``letter`` ...), or ``custom`` with its own size; either way width and height are stored, short side first.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Self

#: Paper presets, short side first, in mpt: ISO sizes from millimetres (rounded half up), US sizes exact.
PAPERS: dict[str, tuple[int, int]] = {
    "a3": (841890, 1190551),
    "a4": (595276, 841890),
    "a5": (419528, 595276),
    "a6": (297638, 419528),
    "b5": (498898, 708661),
    "letter": (612000, 792000),
    "legal": (612000, 1008000),
    "tabloid": (792000, 1224000),
    "executive": (522000, 756000),
}
ORIENTATIONS = ("portrait", "landscape")
MM = 72000 / 25.4  # mpt per millimetre (for limits only)
MIN_SIDE = round(25 * MM)  # the smallest page: 25 mm
MAX_SIDE = round(1200 * MM)  # the largest: 1.2 m
MIN_CONTENT = round(10 * MM)  # what the margins must leave for the text
DEFAULT_MARGIN = 70866  # 2.5 cm


class PageSetupError(ValueError):
    """A page setup that cannot be used; the message says which part."""


@dataclass(frozen=True)
class PageSetup:
    """Where the text goes: the paper, how it lies, the margins (mpt), and whether pages carry their number."""

    paper: str = "a4"
    width: int = PAPERS["a4"][0]
    height: int = PAPERS["a4"][1]
    orientation: str = "portrait"
    margin_top: int = DEFAULT_MARGIN
    margin_right: int = DEFAULT_MARGIN
    margin_bottom: int = DEFAULT_MARGIN
    margin_left: int = DEFAULT_MARGIN
    page_numbers: bool = False

    def __post_init__(self) -> None:
        if self.paper != "custom" and self.paper not in PAPERS:
            raise PageSetupError(f"unknown paper {self.paper!r}: one of {', '.join(PAPERS)} or custom")
        if self.paper != "custom" and (self.width, self.height) != PAPERS[self.paper]:
            raise PageSetupError(f"{self.paper} has the size {PAPERS[self.paper]}, not ({self.width}, {self.height})")
        if self.orientation not in ORIENTATIONS:
            raise PageSetupError("orientation is portrait or landscape")
        for name in ("width", "height", "margin_top", "margin_right", "margin_bottom", "margin_left"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise PageSetupError(f"{name} must be a whole, positive number of mpt")
        if type(self.page_numbers) is not bool:
            raise PageSetupError("page_numbers is true or false")
        if self.width > self.height:
            raise PageSetupError("width is the short side; landscape is said by orientation")
        if not MIN_SIDE <= self.width <= MAX_SIDE or not MIN_SIDE <= self.height <= MAX_SIDE:
            raise PageSetupError("a page side must be between 25 mm and 1200 mm")
        across, down = (self.height, self.width) if self.orientation == "landscape" else (self.width, self.height)
        if (
            across - self.margin_left - self.margin_right < MIN_CONTENT
            or down - self.margin_top - self.margin_bottom < MIN_CONTENT
        ):
            raise PageSetupError("the margins leave less than 10 mm for the text")

    @classmethod
    def preset(cls, paper: str, **changes: object) -> Self:
        """A setup on a preset paper (its size filled in), with any other field changed."""
        if paper not in PAPERS:
            raise PageSetupError(f"unknown paper {paper!r}")
        width, height = PAPERS[paper]
        return replace(cls(paper=paper, width=width, height=height), **changes)  # type: ignore[arg-type]

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {
            "paper": self.paper,
            "width": self.width,
            "height": self.height,
            "orientation": self.orientation,
            "margins": [self.margin_top, self.margin_right, self.margin_bottom, self.margin_left],
            "page_numbers": self.page_numbers,
        }

    @classmethod
    def from_data(cls, data: object) -> Self:
        """Read a setup sent by a client or stored in the log; :class:`PageSetupError` if it is not a usable one."""
        if not isinstance(data, dict):
            raise PageSetupError("a page setup is an object")
        margins = data.get("margins", [DEFAULT_MARGIN] * 4)
        if not isinstance(margins, list) or len(margins) != 4:
            raise PageSetupError("margins are four numbers: top, right, bottom, left")
        try:
            return cls(
                paper=data.get("paper", "a4"),
                width=data["width"],
                height=data["height"],
                orientation=data.get("orientation", "portrait"),
                margin_top=margins[0],
                margin_right=margins[1],
                margin_bottom=margins[2],
                margin_left=margins[3],
                page_numbers=data.get("page_numbers", False),
            )
        except KeyError as missing:
            raise PageSetupError(f"a page setup needs {missing.args[0]}") from None

    def describe(self) -> str:
        """A few words for the history: ``A4, portrait``."""
        name = (
            self.paper.upper()
            if self.paper.startswith(("a", "b")) and self.paper[1:].isdigit()
            else self.paper.capitalize()
        )
        if self.paper == "custom":
            name = f"{round(self.width / MM)} × {round(self.height / MM)} mm"
        return f"{name}, {self.orientation}" + (", page numbers" if self.page_numbers else "")
