"""Which suggestions an export writes into the file, shared by the docx and the odt converter."""

from __future__ import annotations

from claudia_composes import Suggestion, TextModel


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
