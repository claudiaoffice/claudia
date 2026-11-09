"""The edits a catalogued case makes to a model, written once (D177, D181).

A case's ``modify`` step changes one thing and leaves the rest alone, which is the whole point of the Tier 3
"preserve" check. The shapes those edits take stopped being obvious when the three apps started sharing an object
layer: an object is a body plus a per-app anchor, its words are a frozen ``Paragraph`` with a style of their own,
and a paragraph's runs have to cover its text exactly. Doing that arithmetic in every ``spec.py`` would put the
same four lines in each of them and invite each to get it subtly wrong.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any


def worded(paragraph: Any, text: str) -> Any:
    """``paragraph`` with other words in it, its runs laid over the new text by one author."""
    return paragraph.with_text(text, ()).written_by(None)


def retext_block(model: Any, index: int, text: str) -> Any:
    """Give the ``index``-th paragraph of a text other words. A block is frozen, so it is replaced, not poked."""
    model.blocks[index] = worded(model.blocks[index], text)
    return model


def retext_object(model: Any, object_id: str, text: str) -> Any:
    """Give an object's one paragraph other words (D181: the words are the paragraph's, not the body's)."""
    obj = model.get(object_id)
    model.replace_object(obj.with_body(paragraph=worded(obj.body.paragraph, text)))
    return model


def place_object(model: Any, object_id: str, x: int, y: int, w: int, h: int) -> Any:
    """Move and resize an object: the size is the body's, the position the anchor's (D177)."""
    obj = model.get(object_id)
    model.replace_object(replace(obj.with_body(w=w, h=h), anchor=replace(obj.anchor, x=x, y=y)))
    return model


def flat(obj: Any) -> dict[str, Any]:
    """An object's fields as a case wants to assert them: what it is, what it says, and where it sits."""
    body, anchor = obj.body, obj.anchor
    return {
        "id": body.id,
        "kind": body.kind,
        "style": body.style,
        "text": body.paragraph.text if body.paragraph else "",
        "shape": body.shape,
        "x": anchor.x,
        "y": anchor.y,
        "w": body.w,
        "h": body.h,
    }
