"""What a step with a chart takes along (E6.31, D1472, D1475): one place decides it, so that the server, cut and delete
and later the ai do not repeat it. Every function returns one :class:`~claudia_core.Batch`, one undo step.

A chart is an object with a definition of its own (one :class:`~claudia_computes.ChartSpec` per chart object): it is
made with it, and removing the chart forgets it. A slide comes into existence only for a chart, right after the tab
the person is on, and goes with its last object. The ids and names are the caller's to choose: a slide made for a
chart is the next free "Slide n" in the person's language, and the chart keeps the name it is given.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from claudia_core import (
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    AddObject,
    Batch,
    Command,
    DefineAsset,
    ForgetAsset,
    MoveObject,
    ObjectBody,
    Refusal,
    RemoveObject,
    ResizeObject,
    SlideAnchor,
)
from claudia_core.asset_store import DIAGRAM

from .commands import AddSlide, RemoveSlide
from .model import CellAnchor, WorkbookModel

#: The style of a chart object: it carries its own colours, as a picture does.
CHART_STYLE = "plain-image"


@dataclass(frozen=True)
class NewChart:
    """A chart about to be made: the ids of its definition and of its object, its name, and its definition as plain
    data (the format of :class:`~claudia_computes.ChartSpec`, without its id)."""

    spec_id: str
    object_id: str
    name: str
    definition: dict

    def made(self, anchor: dict, w: int, h: int) -> tuple[Command, Command]:
        """Its definition and its object at ``anchor``, ``w`` by ``h``."""
        body = ObjectBody(self.object_id, "diagram", w, h, CHART_STYLE, ref=self.spec_id, name=self.name)
        definition = DefineAsset(DIAGRAM.name, {**self.definition, "id": self.spec_id, "format": 1})
        return definition, AddObject(body, anchor)


def as_new_slide(model: WorkbookModel, chart: NewChart, *, slide_id: str, slide_name: str, after: str) -> Batch:
    """The chart on a new slide right after the tab ``after``, filling the frame."""
    slide = AddSlide(slide_id, slide_name, model.tab_index(after) + 1)
    define, add = chart.made(SlideAnchor(slide_id, 0, 0).to_data(), SLIDE_WIDTH, SLIDE_HEIGHT)
    return Batch((define, slide, add), "Insert chart")


def on_slide(model: WorkbookModel, chart: NewChart, slide_id: str) -> Batch:
    """The chart on the slide ``slide_id``, half the frame in its middle (the slide may hold a chart already)."""
    if slide_id not in model.slides:
        raise ValueError(f"{slide_id!r} is not a slide")
    w, h = SLIDE_WIDTH // 2, SLIDE_HEIGHT // 2
    return Batch(chart.made(SlideAnchor(slide_id, w // 2, h // 2).to_data(), w, h), "Insert chart")


def on_sheet(model: WorkbookModel, chart: NewChart, anchor: CellAnchor, w: int, h: int) -> Batch:
    """The chart floating on a sheet at ``anchor``, ``w`` by ``h``."""
    if str(anchor.sheet) not in model.sheets:
        raise ValueError(f"{anchor.sheet!r} is not a sheet")
    return Batch(chart.made(anchor.to_data(), w, h), "Insert chart")


def to_new_slide(model: WorkbookModel, object_id: str, *, slide_id: str, slide_name: str) -> Batch:
    """ "Move to Slide": a new slide right after the sheet the chart ``object_id`` is on, the chart moved onto it and
    filling the frame. The chart keeps its name and its definition. Undo puts it back; the slide goes with the undo
    while it is empty, and stays when a colleague has put something on it."""
    obj = model.get_object(object_id)
    if obj.body.diagram is None or not isinstance(obj.anchor, CellAnchor):
        raise Refusal("Only a chart on a sheet moves to a slide.")
    at = SlideAnchor(slide_id, 0, 0).to_data()
    return Batch(
        (
            AddSlide(slide_id, slide_name, model.tab_index(obj.holder) + 1),
            MoveObject(object_id, at),
            ResizeObject(object_id, at, SLIDE_WIDTH, SLIDE_HEIGHT),
        ),
        "Move to slide",
    )


def removal(model: WorkbookModel, object_ids: Iterable[str]) -> Batch:
    """Taking the objects ``object_ids`` away, with the definition of each chart among them and every slide that is
    left empty (Q11, Q20 of the review of 2026-11-22)."""
    ids = list(dict.fromkeys(object_ids))
    gone = set(ids)
    objects = [model.get_object(object_id) for object_id in ids]
    steps: list[Command] = [RemoveObject(object_id) for object_id in ids]
    for obj in objects:
        spec = obj.body.diagram
        if spec is not None and set(model.users_of(DIAGRAM, spec)) <= gone:
            steps.append(ForgetAsset(DIAGRAM.name, spec))
    holders = dict.fromkeys(obj.holder for obj in objects if obj.holder in model.slides)
    steps += [RemoveSlide(slide) for slide in holders if set(model.stack_of(slide)) <= gone]
    return Batch(tuple(steps), "Delete")
