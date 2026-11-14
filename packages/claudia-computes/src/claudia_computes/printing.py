"""How the sheets of a workbook are printed (E6.19, D1001–D1009).

The *page* — paper, margins, page numbers — is the kernel's :class:`~claudia_core.PageSetup`, the one composes and
creates print on, and belongs to the whole workbook. What belongs to a *sheet* is :class:`SheetPrintSetup`: how the
page lies, how big the cells are drawn, in which order the pages run, which rows and columns repeat on every page,
and what is printed besides the cells. A chart tab has one too, of which only the orientation counts (the chart is
scaled to the page). A sheet without a setup of its own prints with :data:`DEFAULT_SHEET_PRINT`, so the workbook
stores only the sheets that differ.

Pages are laid out in the client, by the layout library (D901); the document only says how, so that everybody's
preview and PDF are the same.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from .refs import SheetId

ORIENTATIONS: tuple[str, ...] = ("portrait", "landscape")
SCALE_KINDS: tuple[str, ...] = ("fit-width", "fit-page", "percent")
ORDERS: tuple[str, ...] = ("down-then-across", "across-then-down")
MIN_PERCENT = 10
MAX_PERCENT = 400
_FLAGS: tuple[str, ...] = ("gridlines", "headings", "purposes", "footer_name", "objects", "skip_empty")
_LINES = 16384 * 64  # more than any sheet has rows or columns: a limit against absurd numbers only


class PrintSetupError(ValueError):
    """A print setup that cannot be used; the message says which part."""


def _lines(value: object, what: str) -> tuple[int, int] | None:
    if value is None:
        return None
    ok = isinstance(value, (list, tuple)) and len(value) == 2 and all(type(v) is int for v in value)
    if not ok or not 0 <= value[0] <= value[1] < _LINES:  # type: ignore[index]
        raise PrintSetupError(f"{what} is null or two whole numbers, first and last, counted from 0")
    return (value[0], value[1])  # type: ignore[index]


@dataclass(frozen=True)
class SheetPrintSetup:
    """How one sheet is printed; the defaults are what a sheet nobody set up prints like (D1001–D1009).

    ``scale`` is ``"fit-width"`` (the default: every column of a page's worth fits across, never above 100 %),
    ``"fit-page"`` (the whole used range on one page) or ``"percent"`` with ``percent`` (10 to 400). ``repeat_rows``
    and ``repeat_cols`` are ``(first, last)`` zero-based lines repeated on every page, or ``None``.
    """

    orientation: str = "portrait"
    scale: str = "fit-width"
    percent: int = 100
    order: str = "down-then-across"
    repeat_rows: tuple[int, int] | None = None
    repeat_cols: tuple[int, int] | None = None
    gridlines: bool = False
    headings: bool = False
    purposes: bool = False  #: tint the cells by their purpose (input, output, ...), off unless asked (D1005)
    footer_name: bool = True  #: the sheet's name at the foot of every page (D1006)
    objects: bool = True  #: pictures, shapes and charts that float over the cells
    skip_empty: bool = True  #: leave out pages with nothing on them

    def __post_init__(self) -> None:
        if self.orientation not in ORIENTATIONS:
            raise PrintSetupError("orientation is portrait or landscape")
        if self.scale not in SCALE_KINDS:
            raise PrintSetupError(f"unknown scale {self.scale!r}: one of {', '.join(SCALE_KINDS)}")
        if type(self.percent) is not int or not MIN_PERCENT <= self.percent <= MAX_PERCENT:
            raise PrintSetupError(f"the scale is between {MIN_PERCENT} % and {MAX_PERCENT} %")
        if self.order not in ORDERS:
            raise PrintSetupError(f"unknown page order {self.order!r}: one of {', '.join(ORDERS)}")
        _lines(self.repeat_rows, "repeat_rows")
        _lines(self.repeat_cols, "repeat_cols")
        for name in _FLAGS:
            if type(getattr(self, name)) is not bool:
                raise PrintSetupError(f"{name} is true or false")

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        scale: dict = {"kind": self.scale}
        if self.scale == "percent":
            scale["percent"] = self.percent
        return {
            "orientation": self.orientation,
            "scale": scale,
            "order": self.order,
            "repeat_rows": list(self.repeat_rows) if self.repeat_rows else None,
            "repeat_cols": list(self.repeat_cols) if self.repeat_cols else None,
            **{name: getattr(self, name) for name in _FLAGS},
        }

    @classmethod
    def from_data(cls, data: object) -> Self:
        """Read a setup sent by a client or stored in the log; a part that is left out keeps its default.
        :class:`PrintSetupError` if the data is not a usable setup."""
        if not isinstance(data, dict):
            raise PrintSetupError("a sheet's print setup is an object")
        known = {"orientation", "scale", "order", "repeat_rows", "repeat_cols", *_FLAGS}
        if unknown := sorted(set(data) - known):
            raise PrintSetupError(f"unknown part of a print setup: {unknown[0]}")
        scale = data.get("scale", {"kind": "fit-width"})
        if not isinstance(scale, dict) or not isinstance(scale.get("kind"), str):
            raise PrintSetupError('scale is {"kind": "fit-width" | "fit-page" | "percent", "percent": 10..400}')
        defaults = cls()
        return cls(
            orientation=data.get("orientation", defaults.orientation),
            scale=scale["kind"],
            percent=scale.get("percent", 100) if scale["kind"] == "percent" else 100,
            order=data.get("order", defaults.order),
            repeat_rows=_lines(data.get("repeat_rows"), "repeat_rows"),
            repeat_cols=_lines(data.get("repeat_cols"), "repeat_cols"),
            **{name: data.get(name, getattr(defaults, name)) for name in _FLAGS},
        )

    def describe(self) -> str:
        """A few words for the history: ``landscape, fit to width`` or ``portrait, 80 %, with gridlines``."""
        scale = {"fit-width": "fit to width", "fit-page": "fit to one page", "percent": f"{self.percent} %"}[self.scale]
        parts = [self.orientation, scale]
        if self.repeat_rows:
            parts.append("repeating rows")
        if self.repeat_cols:
            parts.append("repeating columns")
        parts += [text for flag, text in (("gridlines", "gridlines"), ("headings", "headings")) if getattr(self, flag)]
        return ", ".join(parts)


#: What a sheet nobody has set up prints like.
DEFAULT_SHEET_PRINT = SheetPrintSetup()


def sheet_print_to_data(setups: dict[SheetId, SheetPrintSetup]) -> dict[str, dict]:
    """The sheets that differ from the default, as plain data (the workbook stores nothing for the others)."""
    return {str(key): setup.to_data() for key, setup in setups.items() if setup != DEFAULT_SHEET_PRINT}
