"""The text boxes and shapes of an office file, as the model holds them (D465): an object of kind ``text`` or ``shape``
with its one paragraph.

A box comes in when the model can show it as it is: one paragraph of plain words (a text box, or the label of a shape
that is a circle, a rectangle or a triangle), a size of at least the smallest an object has, turned by nothing but a
rotation. What the file says of it (its description, whether it is decorative, the style of its words) becomes the
object's; its colours and line are not read (the model takes the look of its styles, as a slide does, D407) and are
reported as ``look`` where they differ. Everything else stays in the file and is reported as ``frame``.
"""

from __future__ import annotations

from .assets import MAX_ALT_CHARS
from .objects import ObjectBody, paragraph_for

#: The style a text box comes in with (its box: no background and no border) and the one of a shape (its outline).
TEXT_BOX_STYLE = "plain-box"
SHAPE_STYLE = "plain-shape"
#: The style of the words of a shape, when the file's own style is not one the model has.
SHAPE_LABEL_STYLE = "shape-label"


def box_body(  # noqa: PLR0913 (what a file says of a box is this much)
    object_id: str,
    size: tuple[int, int],
    text: str,
    words: str,
    *,
    shape: str | None = None,
    description: str = "",
    decorative: bool = False,
    rotation: int = 0,
) -> ObjectBody:
    """The body of the text box (``shape`` is ``None``) or the shape of a file: its size, its words in the style
    ``words``, what the file says of it and how it is turned."""
    return ObjectBody(
        object_id,
        "text" if shape is None else "shape",
        size[0],
        size[1],
        TEXT_BOX_STYLE if shape is None else SHAPE_STYLE,
        paragraph=paragraph_for(object_id, words, text),
        ref=shape,
        rotation=rotation,
        description="" if decorative else description[:MAX_ALT_CHARS],
        decorative=decorative,
    )
