"""A description as a review comment in a docx (E1.13, D1318, A5/A6): the comment is by the person exporting, dated the
day of the export, and covers the words of the paragraph it describes."""

from __future__ import annotations

from typing import Any

from docx.oxml.ns import qn

from ._annotations import Annotations


def write_comment(document: Any, paragraph: Any, text: str, notes: Annotations) -> None:  # noqa: ANN401
    """Comment on the words of the python-docx ``paragraph``: ``text`` by ``notes.author`` at ``notes.when``."""
    runs = paragraph.runs or [paragraph.add_run("")]  # a paragraph with no words has an empty one to hold the range
    initials = "".join(part[0] for part in notes.author.split()[:2]).upper()
    comment = document.add_comment(runs, text=text, author=notes.author, initials=initials)
    if notes.when:
        comment._comment_elm.set(qn("w:date"), notes.when)  # python-docx dates a comment now; the export day is wanted
