"""State events the creates model raises through ``Context.emit`` (the kernel adds its own).

``ObjectsChanged``, ``ShapesChanged`` and ``ImagesChanged`` are the same events in all three apps and live in
:mod:`claudia_core.objects` (E10.16); they are re-exported here, where they have always been imported from. What
is only a presentation's own is below.
"""

from __future__ import annotations

from dataclasses import dataclass

from claudia_core import ImagesChanged, ObjectsChanged, ShapesChanged  # noqa: F401  (re-exported)


@dataclass(frozen=True)
class SlidesChanged:
    """Slides were added, removed or reordered: a view asks for the list again."""

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "slides"}


@dataclass(frozen=True)
class PrintSetupChanged:
    """How the presentation is printed changed (D917): the whole new setup."""

    setup: dict

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "print_setup", "setup": self.setup}
