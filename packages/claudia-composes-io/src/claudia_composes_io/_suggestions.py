"""Which suggestions an export writes into the file, and when they were made (docx and odt converters)."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from claudia_composes import Suggestion, TextModel
from claudia_odf_io import odf_date

#: When a suggestion was made, as a UTC second (``None``: nobody knows).
type WhenMade = Callable[[Suggestion], str | None]


def when_made(change_times: Mapping[str, str] | None = None, fallback: str | None = None) -> WhenMade:
    """A function that says when a suggestion was made, for the date of its tracked change: the time ``change_times``
    has for its id (the server reads them from the log), else ``fallback`` (the day the document was last changed:
    the suggestion cannot be younger), else ``None``. Times come out as UTC to the second, the way both file formats
    want them (:func:`claudia_odf_io.odf_date`)."""
    times = change_times or {}

    def when(suggestion: Suggestion) -> str | None:
        found = times.get(suggestion.id) or fallback
        return odf_date(found) if found else None

    return when


def open_replacements(model: TextModel, *, track: bool = True) -> dict[str, list[Suggestion]]:
    """The suggestions to write as tracked changes, by the block they are in, each block's in the order of the text:
    the open ones that propose a replacement. A remark (nothing to track) and a suggestion that is resolved or
    withdrawn are left out; with ``track`` false, all are."""
    by_block: dict[str, list[Suggestion]] = {}
    if track:
        for suggestion in model.suggestions.values():
            if suggestion.state == "open" and suggestion.replacement is not None:
                by_block.setdefault(suggestion.anchor.block, []).append(suggestion)
    for found in by_block.values():
        found.sort(key=lambda s: s.anchor.start)
    return by_block
