"""The page a text is printed on (D904): :class:`~claudia_core.PageSetup`, which moved to the kernel so that
presentations print on the same pages (D917). Re-exported here, where it was first imported from."""

from claudia_core.page import (
    DEFAULT_MARGIN,
    MAX_SIDE,
    MIN_CONTENT,
    MIN_SIDE,
    MM,
    ORIENTATIONS,
    PAPERS,
    PageSetup,
    PageSetupError,
)

__all__ = [
    "DEFAULT_MARGIN",
    "MAX_SIDE",
    "MIN_CONTENT",
    "MIN_SIDE",
    "MM",
    "ORIENTATIONS",
    "PAPERS",
    "PageSetup",
    "PageSetupError",
]
