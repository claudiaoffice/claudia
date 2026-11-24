"""A file's tabs and drawings put into a workbook, the same for xlsx and ods (D462, D463, D1478, D1479).

Each format finds the drawings the model can hold (its charts, its pictures since CODE-67, and its text boxes and
shapes) and says of each where it is: the cell its corner is pinned to and its distance from the corner of the tab, in
pixels (:class:`FileObject`). What is done with them is the same for both: a tab the file's mark names
(:mod:`.slide_mark`) is a slide and its drawings are where they are on it, at the size the mark says, a box with the
styles the mark keeps for it (:func:`._boxes.styled`); on a sheet a chart or a picture hangs at its cell, and a box is
not held (a sheet has none, D1232). A sheet or a slide holds at most so many objects; what is beyond that stays in the
file and is reported.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace

from claudia_computes import CellAnchor, ChartSpec, ObjectBody, SheetId, VisualObject, WorkbookModel
from claudia_computes.model import MAX_OBJECTS_PER_SHEET, Sheet
from claudia_core import SLIDE_HEIGHT, SLIDE_WIDTH, ImageAsset, Slide, SlideAnchor, nudge_into, primitive
from claudia_odf_io import BoxLook

from ._boxes import styled
from ._placed import ONE_TO_ONE
from .slide_mark import SlideMark


@dataclass(frozen=True)
class FileObject:
    """A drawing of a file the model holds: on which tab, pinned to which cell, how far from the corner of the tab (in
    pixels: worked out when it is asked for, which only a slide needs), and the object it is, with the definition of a
    chart or the image of a picture."""

    tab: SheetId
    row: int
    col: int
    corner: Callable[[], tuple[float, float]]
    body: ObjectBody
    #: What the file's losses call it where the model does not hold it: ``chart``, ``picture``, ``shape``, ``object``.
    kind: str
    #: Its place among the drawings of the file: on a tab, the later is in front.
    order: int
    chart: ChartSpec | None = None
    image: ImageAsset | None = None
    #: For a text box or a shape: the look the file gives it.
    look: BoxLook | None = None


def within_limit(found: Iterable[FileObject]) -> list[FileObject]:
    """``found`` without what a tab cannot hold beyond :data:`MAX_OBJECTS_PER_SHEET` (the first are kept)."""
    count: Counter[SheetId] = Counter()
    kept = []
    for one in found:
        count[one.tab] += 1
        if count[one.tab] <= MAX_OBJECTS_PER_SHEET:
            kept.append(one)
    return kept


def found_objects[D](
    charts: Iterable[FileObject], drawn: Sequence[D], readers: Sequence[Callable[[D, str], FileObject | None]]
) -> list[FileObject]:
    """The drawings of a file the model may hold: ``charts`` first (their ids come first, for the patch), then, for each
    of ``readers`` in turn, what it makes of the ``drawn`` elements of the file (``None``: nothing the model holds),
    numbered on: ``o{n}`` for the ``n``-th."""
    found = list(charts)
    for read in readers:
        for each in drawn:
            one = read(each, f"o{len(found) + 1}")
            if one is not None:
                found.append(one)
    return found


def still_lost(kind: str, detail: str, count: int, held: Iterable[FileObject], tab: SheetId) -> int:
    """How many of what a file's tab has that the model does not show (``kind``, ``detail``, ``count``) are left
    when the drawings ``held`` of it are taken off: a chart, a picture, a box of the model is not lost."""
    return count if detail else count - sum(1 for one in held if one.tab == tab and one.kind == kind)


def _on_a_slide(one: FileObject, scale: float) -> tuple[ObjectBody, int, int] | None:
    """``one`` in units of a slide: its body at its size there, and its corner, nudged onto the slide where it reaches
    a little over its edge; ``None`` when it cannot be on a slide at all."""
    body = replace(one.body, w=round(one.body.w / scale), h=round(one.body.h / scale))
    x, y = (round(length / scale) for length in one.corner())
    place = nudge_into(x, y, body.w, body.h, body.rotation, SLIDE_WIDTH, SLIDE_HEIGHT)
    return None if place is None else (body, *place)


@dataclass(frozen=True)
class FileTabs:
    """What the tabs of a file are in the model: which are slides (by the tab, the slide's id), at what size, and
    what the mark of the slides says."""

    slides: dict[SheetId, str]
    scale: float
    mark: SlideMark | None


def file_tabs_of(sheets: Sequence[Sheet], found: Sequence[FileObject], mark: SlideMark | None) -> FileTabs:
    """Which of ``sheets`` (the tabs of a file, in order) are slides: those ``mark`` names that have no cells and
    whose drawings (``found``) can all be on a slide. The slides are ``p1``, ``p2``... in their order."""
    scale = (ONE_TO_ONE if mark is None else mark.size).px_per_unit
    named = set() if mark is None else set(mark.slide_tabs((s.id, s.name, bool(s.cells)) for s in sheets))
    fitting = [
        sheet.id
        for sheet in sheets
        if sheet.id in named and all(_on_a_slide(one, scale) is not None for one in found if one.tab == sheet.id)
    ]
    return FileTabs({tab: f"p{number}" for number, tab in enumerate(fitting, start=1)}, scale, mark)


def held_of(found: Iterable[FileObject], tabs: FileTabs) -> list[FileObject]:
    """What of ``found`` the model holds: a box only on a slide, and no more on a tab than it can hold."""
    return within_limit(one for one in found if one.look is None or one.tab in tabs.slides)


def _named(model: WorkbookModel, body: ObjectBody) -> ObjectBody:
    """``body`` with its name, unless another thing of ``model`` has it."""
    try:
        model.check_thing_name(body.id, body.name)
    except ValueError:
        return replace(body, name="")
    return body


def lost_looks(held: Iterable[FileObject], tabs: FileTabs) -> int:
    """How many boxes of ``held`` look otherwise in the file than their style says (``look``)."""
    model = WorkbookModel()
    return sum(styled(model, one.body, one.look, tabs.mark)[1] for one in held if one.look is not None)


def hold(model: WorkbookModel, sheets: Sequence[Sheet], held: Sequence[FileObject], tabs: FileTabs) -> None:
    """The tabs of a file put into ``model`` in their order, each a sheet or a slide as ``tabs`` says, and ``held`` on
    them: each chart's definition, each picture's image and each shape's outline, and the object, on a slide where it
    is (in units of the slide) or else hanging at its cell. A name the model cannot give it (another thing has it) is
    left out."""
    for sheet in sheets:
        if sheet.id in tabs.slides:
            model.add_slide(Slide(tabs.slides[sheet.id], sheet.name), None)
        else:
            model.add_sheet(sheet, None)
    for one in sorted(held, key=lambda each: each.order):
        if one.chart is not None:
            model.charts.define(one.chart)
        if one.image is not None and one.image.id not in model.images:
            model.images.define(one.image)
        body = _named(model, one.body)
        if one.look is not None:
            body = styled(model, body, one.look, tabs.mark)[0]
            if body.shape is not None and body.shape not in model.shapes:
                model.shapes.define(primitive(body.shape))
        slide = tabs.slides.get(one.tab)
        if slide is None:
            model.insert_object(VisualObject(body, CellAnchor(one.tab, one.row, one.col)))
            continue
        placed = _on_a_slide(replace(one, body=body), tabs.scale)
        assert placed is not None  # (file_tabs_of made it a slide because they all fit)
        body, x, y = placed
        model.insert_object(VisualObject(body, SlideAnchor(slide, x, y)))
