"""The text boxes and shapes of a workbook's slides in a file (E6.31, D1479), as both formats need them.

A slide's text boxes and shapes (those :func:`claudia_odf_io.is_written` names) are written on its tab, where they are,
in the look their style gives them (:func:`claudia_odf_io.look_of`) and their words in the look of their words' style;
a box on a sheet is not written (``object``, as before). A file says how a box looks, not which style gave it that
look, so the mark of the slides keeps, by the name of each box, its style and the style of its words
(:mod:`.slide_mark`): read back, a box gets them while the workbook has them and the file still shows the look of its
style. A box someone restyled in another program has the plain style (``plain-box``, ``plain-shape``) and says that
its look is lost (``look``), as a text's box does (D465).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from claudia_computes import ObjectBody, WorkbookModel
from claudia_odf_io import BoxLook, authored, is_written, look_of

from ._placed import Placed
from .slide_mark import SlideMark


def written_boxes(placed: Iterable[Placed]) -> tuple[Placed, ...]:
    """The text boxes and shapes among ``placed`` that a file gets: those on slides."""
    return tuple(one for one in placed if one.tab.is_slide and is_written(one.obj))


def box_styles(placed: Iterable[Placed]) -> dict[str, tuple[str, str]]:
    """What the mark of the slides keeps of their boxes: by the name of each box that has one, its style and the style
    of its words."""
    return {
        one.obj.body.name: (one.obj.body.style, one.obj.body.paragraph.style)
        for one in written_boxes(placed)
        if one.obj.body.name and one.obj.body.paragraph is not None
    }


def authorship_lost(placed: Iterable[Placed]) -> int:
    """How many boxes a file gets say who wrote which of their words: what no file keeps (``authorship``)."""
    return authored(one.obj for one in written_boxes(placed))


def words_css(model: WorkbookModel, body: ObjectBody) -> dict[str, str]:
    """What the style of the words of ``body`` says, with the palette's roles made colours."""
    assert body.paragraph is not None  # (a box always has its words, even none)
    return model.styles.resolved(body.paragraph.style, model.palette.colours())


def styled(model: WorkbookModel, body: ObjectBody, look: BoxLook, mark: SlideMark | None) -> tuple[ObjectBody, bool]:
    """The box ``body`` of a file (in the plain style a file's box comes in with), with the styles the mark keeps for
    its name where ``model`` has them: the style of its words always, its own style when the file shows the look that
    style gives. And whether the file's look is lost: the box looks otherwise than its style says (``look``)."""
    kept = None if mark is None or not body.name else mark.styles.get(body.name)
    if kept is not None and body.paragraph is not None:
        box, words = kept
        if words in model.styles:
            body = replace(body, paragraph=replace(body.paragraph, style=words))
        if box in model.styles and look.matches(look_of(model, replace(body, style=box))):
            return replace(body, style=box), False
    return body, not look.matches(look_of(model, body))
