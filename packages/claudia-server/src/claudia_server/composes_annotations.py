"""What the text app writes about its paragraphs besides their words when it exports (E1.13, D1311, D1318).

A name a person *gave* is written as a bookmark; one the app worked out (a generic "Paragraph 4" in any language the
server speaks, a heading's title) is not. A description is written as a review comment when the person exporting asks
for it (A4), as that person, dated the day of the export (A6)."""

from __future__ import annotations

from datetime import UTC, datetime

from claudia_composes_io import Annotations

from claudia_composes import TextModel

from .thing_names import is_generic_name


def export_annotations(model: TextModel, author: str, *, comments: bool, now: datetime | None = None) -> Annotations:
    """The names and, when ``comments``, the descriptions of the paragraphs of ``model`` as an export writes them,
    the comments by ``author`` at ``now`` (the current time when ``None``)."""
    names = {
        paragraph.id: name
        for paragraph in model.paragraphs
        if paragraph.generated is None
        and not model.name_is_fixed(paragraph.id)
        and (name := model.paragraph_names.get(paragraph.id))
        and not is_generic_name(name)
    }
    notes = (
        {
            paragraph.id: text
            for paragraph in model.paragraphs
            if paragraph.generated is None and (text := model.paragraph_descriptions.get(paragraph.id))
        }
        if comments
        else {}
    )
    when = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return Annotations(names=names, comments=notes, author=author, when=when)
