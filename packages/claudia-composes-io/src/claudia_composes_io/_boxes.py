"""Which objects of a text are boxes a converter writes (D465): a text box, and a shape that is a circle, a rectangle
or a triangle (the outlines an office file draws by name); and what such a box looks like in values a file holds."""

from __future__ import annotations

import re
from dataclasses import dataclass

from claudia_composes import TextModel
from claudia_core import PRIMITIVES, ObjectBody, VisualObject, colour_of
from claudia_odf_io import LossLog

#: A line is this many EMU to the point, and a pixel (the model's unit, 96 to the inch) is this many points.
EMU_PER_POINT = 12700
POINTS_PER_PIXEL = 0.75
_DEFAULT_LINE_PX = 1.0
_NUMBER = re.compile(r"[\d.]+")
#: The colour a file gives a fill or a line that is not a plain colour (a theme's, a gradient): it is not any colour.
UNKNOWN: tuple[int, int, int] = (-1, -1, -1)


def is_written(obj: VisualObject) -> bool:
    """Does a converter write ``obj``: a text box, or a shape that is one of the outlines every office format knows?"""
    body = obj.body
    return body.kind == "text" or (body.kind == "shape" and body.shape in PRIMITIVES)


def boxes_of(model: TextModel, block_id: str) -> list[VisualObject]:
    """The boxes hanging from the paragraph ``block_id`` a converter writes, the one in front last."""
    found = (model.get_object(object_id) for object_id in model.stack_of(block_id))
    return [obj for obj in found if is_written(obj)]


def all_boxes(model: TextModel) -> dict[str, VisualObject]:
    """Every box of the text a converter writes, by object id."""
    return {obj.id: obj for obj in model.objects.values() if is_written(obj)}


def box_losses(model: TextModel, losses: LossLog) -> None:
    """Say in ``losses`` what the files cannot keep of the boxes of ``model``: who wrote which words of one."""
    authored = sum(
        1
        for obj in all_boxes(model).values()
        if obj.body.paragraph is not None and any(run.author is not None for run in obj.body.paragraph.runs)
    )
    if authored:
        losses.add("authorship", count=authored)


@dataclass(frozen=True)
class BoxLook:
    """What a box looks like in a file: the colour that fills it and the colour and width (in EMU) of its line; ``None``
    for none."""

    fill: tuple[int, int, int] | None
    line: tuple[int, int, int] | None
    width: int

    def matches(self, other: BoxLook) -> bool:
        """Are the two looks the same to the eye (the widths within a hundredth of a point, which a file rounds)?"""
        return (self.fill, self.line) == (other.fill, other.line) and abs(
            self.width - other.width
        ) <= EMU_PER_POINT // 50


def look_of(model: TextModel, body: ObjectBody) -> BoxLook:
    """The look the styles of ``model`` give the box ``body``: a shape's ``fill``, ``stroke`` and ``stroke-width``, a
    text box's ``background-color`` and ``border`` (a translucent colour flattened over the page, which a solid fill
    cannot hold)."""
    colours = model.palette.colours()
    css = model.styles.resolved(body.style, colours)
    page = colours.get("page")
    if body.kind == "shape":
        fill, line = colour_of(css, "fill", page), colour_of(css, "stroke", page)
        width = _points(css.get("stroke-width"))
    else:
        fill = colour_of(css, "background-color", page)
        border = css.get("border")
        line = colour_of({"border": border}, "border", page) if border else None
        width = _points(border)
    return BoxLook(fill, line, round(width * EMU_PER_POINT) if line else 0)


def _points(value: str | None) -> float:
    """The width a style gives a line (CSS pixels, the first number of ``value``) as points."""
    found = _NUMBER.search(value) if value else None
    return (float(found.group()) if found else _DEFAULT_LINE_PX) * POINTS_PER_PIXEL
