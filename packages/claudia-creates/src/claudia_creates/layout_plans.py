"""What a person's wish about layouts comes to, as commands with final values (E10.4, E10.5, D1530).

A plan looks at the document as it is and returns the command (often a :class:`~claudia_core.Batch`) that does it, so
that the command itself decides nothing and undo, replay and every client end the same way."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import NamedTuple

from claudia_core import AddObject, Batch, Command, MoveObject, RemoveObject, ResizeObject, RotateObject, SetObjectStyle

from .layout_commands import DefineLayout, RemoveLayout, SetSlideLayout
from .model import SlideModel, is_empty

#: The changes to an object that belong to the layout when the object does (E10.5): its place and size, its look, its
#: turn, and taking it away. What is written in it is not among them.
_DEVIATIONS = (MoveObject, ResizeObject, RotateObject, SetObjectStyle, RemoveObject)


def set_layout_command(model: SlideModel, slide: str, layout: str) -> SetSlideLayout:
    """The command that lets a slide follow ``layout``: what is bound to a placeholder follows the placeholder with
    the same purpose on the new layout, and where there is none it becomes a free box where it stands (E10.4)."""
    model.layout_of(slide)  # raises for an unknown slide
    by_purpose = {obj.anchor.purpose: obj.id for obj in model.objects_on(layout) if obj.anchor.purpose}
    rebind = tuple(
        (obj.id, by_purpose.get(model.objects[obj.anchor.bound_to_placeholder].anchor.purpose, ""))
        for obj in model.objects_on(slide)
        if obj.anchor.bound_to_placeholder in model.objects
    )
    return SetSlideLayout(slide, layout, rebind)


def deviate_layout(model: SlideModel, slide: str, change: Command) -> Command:
    """The command that makes ``change`` to something the slide gets from its layout, and lets the slide follow a new,
    provisional layout that has the change, instead of changing the layout for every other slide (E10.5).

    The new layout is a whole copy of the layout the slide follows, named after it ("Two lists 2"); the slide's bound
    objects are bound to its placeholders, and the change is made there. One step, one undo. ``ValueError`` if the
    change is not one of those that belong to a layout, or the thing is not the layout's."""
    parent, on_slide, layout_object = _belonging(model, slide, change)
    removing = isinstance(change, RemoveObject)

    layout_id, name = _next_layout(model, parent)
    kept = [obj for obj in model.objects_on(parent) if not (removing and obj.id == layout_object)]
    copies: dict[str, str] = {}
    for obj in kept:
        copies[obj.id] = _free_id(model, obj.id, set(copies.values()))
    steps: list[Command] = [DefineLayout(layout_id, name, to_name=True)]
    for obj in kept:
        body = obj.body
        if body.paragraph is not None:
            body = replace(body, paragraph=replace(body.paragraph, id=copies[obj.id]))
        anchor = replace(obj.anchor, slide=layout_id)
        steps.append(AddObject(replace(body, id=copies[obj.id], name=""), anchor.to_data()))
    rebind = tuple(
        (obj.id, copies.get(obj.anchor.bound_to_placeholder, ""))
        for obj in model.objects_on(slide)
        if obj.anchor.bound_to_placeholder
    )
    steps.append(SetSlideLayout(slide, layout_id, rebind))
    if removing:
        if on_slide:
            steps.append(change)
    else:
        steps.append(_retargeted(change, copies[layout_object], layout_id))
    return Batch(tuple(steps))


def update_layout(model: SlideModel, slide: str, change: Command) -> Command:
    """The command that makes ``change`` to something the slide gets from its layout, on the layout itself, so that
    every slide that follows it gets the change (E10.5). Taking a placeholder away takes the empty objects bound to it
    away with it; what is filled stays on its slide as a free box where it stands. ``ValueError`` as for
    :func:`deviate_layout`."""
    parent, _, layout_object = _belonging(model, slide, change)
    if not isinstance(change, RemoveObject):
        return _retargeted(change, layout_object, parent)
    empty = [
        obj.id
        for follower in model.slides_following(parent)
        for obj in model.objects_on(follower)
        if obj.anchor.bound_to_placeholder == layout_object and is_empty(obj)
    ]
    return Batch((*(RemoveObject(object_id) for object_id in empty), RemoveObject(layout_object)))


def delete_layout(model: SlideModel, layout: str, move_to: str) -> Command:
    """The command that takes a layout away: the slides that follow it follow ``move_to`` instead (their objects go to
    the placeholders with the same purpose, or stay as free boxes), and what is on the layout goes with it (E10.4)."""
    if move_to == layout:
        raise ValueError("the slides cannot move to the layout that is taken away")
    model.layouts.require(move_to)
    steps: list[Command] = [set_layout_command(model, slide, move_to) for slide in model.slides_following(layout)]
    steps += [RemoveObject(obj.id) for obj in model.objects_on(layout)]
    steps.append(RemoveLayout(layout))
    return Batch(tuple(steps))


class _Belonging(NamedTuple):
    """What a change to an object of a slide is about (see :func:`_belonging`)."""

    layout: str  # the layout the slide follows
    own: bool  # a slide's own object bound to the layout, not an object of the layout seen on the slide
    layout_object: str  # the object of the layout the change belongs to


def _belonging(model: SlideModel, slide: str, change: Command) -> _Belonging:
    """What a change to an object of a slide is about: the layout the slide follows, whether the object is a slide's
    own object that is bound to the layout (not an object of the layout seen on the slide), and the object of the
    layout it belongs to. ``ValueError`` if the change is not one that belongs to a layout, or the object is not the
    layout's."""
    if not isinstance(change, _DEVIATIONS):
        raise ValueError("this change does not belong to a layout")
    parent = model.layout_of(slide)
    target = model.get_object(change.id)
    on_slide = target.holder == slide and target.anchor.bound_to_placeholder in model.stack_of(parent)
    if not on_slide and target.holder != parent:
        raise ValueError("this object does not belong to the layout of its slide")
    return _Belonging(parent, on_slide, target.anchor.bound_to_placeholder if on_slide else target.id)


def _retargeted(change: Command, object_id: str, layout_id: str) -> Command:
    """``change`` as made to the object ``object_id`` of the layout ``layout_id``."""
    if isinstance(change, MoveObject | ResizeObject):
        return replace(change, id=object_id, anchor={**change.anchor, "holder": layout_id})
    if isinstance(change, RotateObject) and change.anchor is not None:
        return replace(change, id=object_id, anchor={**change.anchor, "holder": layout_id})
    return replace(change, id=object_id)  # type: ignore[type-var]  # every change here is a dataclass with an id


def _next_layout(model: SlideModel, parent: str) -> tuple[str, str]:
    """The id and the name of the layout that deviates from ``parent``: the next free id ``l1``, ``l2``…, and the name
    of the layout with a number, the first that is free. A deviation that nobody named yet is counted on from the layout
    it came from ("Two lists 2" gives "Two lists 3"); a name a person gave stays whole ("Top 10" gives "Top 10 2")."""
    layout = model.layouts[parent]
    base_name = re.sub(r" \d+$", "", layout.name) if layout.to_name else layout.name
    taken = {other.name.casefold() for other in model.layouts}
    number = 2
    while f"{base_name} {number}".casefold() in taken:
        number += 1
    return _free_id(model, "l", set(), start=1), f"{base_name} {number}"


def _free_id(model: SlideModel, base: str, chosen: set[str], start: int = 2) -> str:
    """An id of the form ``base-N`` (``baseN`` for the layouts' ``l``) that no object, slide or layout has and that is
    not one of ``chosen`` already."""
    stem = re.sub(r"-\d+$", "", base)
    joint = "" if base == "l" else "-"
    number = start
    while (
        (candidate := f"{stem}{joint}{number}") in model.objects
        or candidate in model.slides
        or candidate in model.layouts
        or candidate in chosen
    ):
        number += 1
    return candidate
