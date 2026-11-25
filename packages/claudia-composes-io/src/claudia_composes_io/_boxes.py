"""Which objects of a text are boxes a converter writes (D465): the text boxes and shapes of
:func:`claudia_odf_io.is_written`, by the paragraph they hang from, and what the files cannot keep of them. What such a
box looks like in a file is shared with the other apps (:mod:`claudia_odf_io.boxes`, D1479)."""

from __future__ import annotations

from claudia_composes import TextModel
from claudia_core import FIELD_CHAR, Paragraph, VisualObject
from claudia_odf_io import LossLog, authored, is_written


def boxes_of(model: TextModel, paragraph_id: str) -> list[VisualObject]:
    """The boxes hanging from the paragraph ``paragraph_id`` a converter writes, the one in front last."""
    found = (model.get_object(object_id) for object_id in model.stack_of(paragraph_id))
    return [obj for obj in found if is_written(obj)]


def all_boxes(model: TextModel) -> dict[str, VisualObject]:
    """Every box of the text a converter writes, by object id."""
    return {obj.id: obj for obj in model.objects.values() if is_written(obj)}


def box_losses(model: TextModel, losses: LossLog) -> None:
    """Say in ``losses`` what the files cannot keep of the boxes of ``model``: who wrote which words of one."""
    if count := authored(all_boxes(model).values()):
        losses.add("authorship", count=count)


def shown_words(model: TextModel, words: Paragraph) -> str:
    """The words of a box as a file gets them: each reference as what it reads as now (step H)."""
    if not words.fields:
        return words.text
    shown = iter(model.structure.shown().get(words.id, ()))
    return "".join(next(shown).text if char == FIELD_CHAR else char for char in words.text)


def has_references(model: TextModel) -> bool:
    """Do the words of any box of the text hold a reference? (A kept file with one is written anew.)"""
    return any(obj.body.paragraph is not None and obj.body.paragraph.fields for obj in model.objects.values())
