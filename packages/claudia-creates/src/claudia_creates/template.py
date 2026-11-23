"""A template, and what a presentation does with one (E10.4, E10.22, D1530, D1536).

A template is a presentation without slides: its layouts, the objects on them, its styles and its colours, and a note
of what it is. It is no class of its own in a document; :class:`Template` is only the view of a state that was checked.

* :func:`template_state` writes a presentation as a template: nothing of the slides stays (their words, notes, planned
  times and pictures), what the layouts show does, with the pictures it needs.
* :func:`check_template` reads a state that is claimed to be a template, or refuses it with a sentence.
* :func:`start_from_template` makes a new presentation: a copy, with one slide on the first layout that is shown.
  The two share nothing and keep no link; the new one only keeps a note of the name.
* :func:`plan_change_theme` and :func:`plan_change_template` give a finished presentation the look of a template, or
  the whole template: the command (one step, one Undo) with final values, as every plan does (D1531).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

from claudia_core import (
    ASSET_KINDS,
    N_,
    AddObject,
    Batch,
    Command,
    Context,
    DefineAsset,
    Refusal,
    RemoveObject,
    Theme,
    theme_commands,
)

from .events import TemplateChanged
from .layout_commands import DefineLayout, SetSlideLayout
from .layout_plans import free_id
from .model import FIRST_SLIDE, SlideModel, SlideObject
from .template_info import TemplateInfo

register = SlideModel.registry.register


class TemplateRefused(Refusal):
    """The state is not a template; the message says why, as a sentence for the person."""


@dataclass(frozen=True)
class Template:
    """A template that was checked: what it says about itself, and the presentation without slides it is."""

    info: TemplateInfo
    model: SlideModel

    @property
    def theme(self) -> Theme:
        """Its styles and its colours."""
        return Theme(self.info.name, self.model.styles, self.model.palette)


@register
@dataclass(frozen=True)
class SetTemplate(Command):
    """Note which template the presentation came from, or that it came from none. Nothing follows the note."""

    kind: ClassVar[str] = "creates.SetTemplate"
    template: TemplateInfo | None

    @property
    def label(self) -> str:
        return "Template"

    @property
    def summary(self) -> str:
        return "noted the template" if self.template else "removed the note of the template"

    def apply(self, ctx: Context[SlideModel]) -> Command:
        was, ctx.model.template = ctx.model.template, self.template
        ctx.emit(TemplateChanged(self.template.to_data() if self.template else None))
        return SetTemplate(was)

    def to_data(self) -> dict:
        return {"template": self.template.to_data() if self.template else None}

    @classmethod
    def from_data(cls, data, registry) -> SetTemplate:
        return cls(TemplateInfo.from_data(data["template"]) if data["template"] else None)


def template_state(model: SlideModel, info: TemplateInfo) -> dict:
    """The state of ``model`` written as a template called ``info``: no slides, no notes, no planned times, and the
    pictures, shapes and the like that only the slides used are left out. ``model`` is not changed."""
    copy = SlideModel.restore(model.serialize())
    for slide in list(copy.order):
        for obj in copy.objects_on(slide):
            copy.delete_object(obj.id)
        copy.delete_slide(slide)
    for kind in reversed(ASSET_KINDS):  # a container uses a picture: the containers go first
        store = copy.assets[kind.name]
        for asset_id in [asset_id for asset_id in store if not store.users(asset_id)]:
            store.forget(asset_id)
    copy.template = info
    return copy.serialize()


def check_template(state: dict) -> Template:
    """``state`` as a template. :class:`TemplateRefused` if it is no presentation, has slides, has no layout or does
    not say what it is for."""
    try:
        model = SlideModel.restore(state)
    except Exception:  # noqa: BLE001 - a state anybody may have written: whatever restoring it raises, it is no deck
        raise TemplateRefused(N_("this is not a presentation")) from None
    if model.order:
        raise TemplateRefused(N_("a template has no slides, and this presentation has {count}"), count=len(model.order))
    if not len(model.layouts):
        raise TemplateRefused(N_("a template has at least one layout"))
    if model.template is None:
        raise TemplateRefused(N_("this presentation is not a template: choose Save as template… in it first"))
    return Template(model.template, model)


def basic_template() -> Template:
    """The template every server has: one layout without placeholders, the styles and colours a presentation starts
    with."""
    info = TemplateInfo("Basic", "Slides with nothing prepared: a layout without placeholders", "en")
    model = SlideModel()
    model.template = info
    return Template(info, model)


def start_from_template(template: Template) -> SlideModel:
    """A new presentation that is a copy of ``template``, with one slide on its first layout that is not hidden."""
    deck = SlideModel.restore(template.model.serialize())
    deck.insert_slide(FIRST_SLIDE)
    return deck


def plan_change_theme(model: SlideModel, template: Template) -> Command | None:
    """The command that gives ``model`` the styles and the colours of ``template``, matched as
    :func:`claudia_core.theme_commands` says; its layouts and slides stay as they are. ``None`` when it looks like
    that already."""
    steps = theme_commands(model.styles, model.palette, template.theme)
    return _one(steps)


def plan_change_template(model: SlideModel, template: Template) -> Command:
    """The command that gives ``model`` the theme and the layouts of ``template`` and notes where they came from.

    A layout of the presentation that has the name of one of the template's (in any letters) keeps its id, its name and
    its slides and gets what is on the template's layout; each box that was bound to a placeholder follows the one
    with the same purpose, and where there is none it stays a free box where it stands. A layout the presentation
    lacks is added. Everything the template does not have stays (D1531, D1539)."""
    plan = _Plan(model, template)
    steps: list[Command] = list(theme_commands(model.styles, model.palette, template.theme))
    mine = {_name(layout.name): layout for layout in model.layouts}
    for given in template.model.layouts:
        if (layout := mine.get(_name(given.name))) is None:
            steps += plan.added(given)
        else:
            steps += plan.replaced_by(given.id, layout.id)
    steps.append(SetTemplate(template.info))
    return Batch(tuple(steps))


class _Plan:
    """The steps of one change of template. It remembers the ids and the assets it has given so far, so that no two
    steps of the plan take the same."""

    def __init__(self, model: SlideModel, template: Template) -> None:
        self.model, self.template = model, template
        self.chosen: set[str] = set()  # the ids this plan gives
        self.defined: set[tuple[str, str]] = set()  # the assets this plan defines

    def added(self, given) -> list[Command]:  # noqa: ANN001 - a layout of the template
        """A layout the presentation lacks: defined as a layout of the template, then what is on it."""
        layout_id = free_id(self.model, given.id, self.chosen)
        self.chosen.add(layout_id)
        define = DefineLayout(layout_id, given.name, None, False, given.purpose, "template", given.hidden)
        return [define, *self.copied_onto(given.id, layout_id)]

    def replaced_by(self, source: str, layout: str) -> list[Command]:
        """What puts what is on the template's layout ``source`` on the presentation's layout ``layout``, in place of
        what is there. The boxes bound to its placeholders are set free first, so that nothing points at what goes;
        then the old objects go and the new come; then each box is bound to the new placeholder with the same purpose,
        if any, and takes its place. Undo runs it backwards, and every step of it is valid (a layout has each purpose
        once)."""
        model = self.model
        old_ids = {obj.id for obj in model.objects_on(layout)}
        bound = {
            slide: [
                (obj.id, model.objects[obj.anchor.bound_to_placeholder].anchor.purpose)
                for obj in model.objects_on(slide)
                if obj.anchor.bound_to_placeholder in old_ids
            ]
            for slide in model.slides_following(layout)
        }
        bound = {slide: boxes for slide, boxes in bound.items() if boxes}
        new = self.copied_onto(source, layout)
        placeholders = {
            step.anchor["purpose"]: step.body.id
            for step in new
            if isinstance(step, AddObject) and step.anchor.get("purpose")
        }
        return [
            *(SetSlideLayout(slide, layout, tuple((box, "") for box, _ in boxes)) for slide, boxes in bound.items()),
            *(RemoveObject(object_id) for object_id in old_ids),
            *new,
            *(
                SetSlideLayout(
                    slide,
                    layout,
                    tuple((box, placeholders[purpose]) for box, purpose in boxes if purpose in placeholders),
                )
                for slide, boxes in bound.items()
                if any(purpose in placeholders for _, purpose in boxes)
            ),
        ]

    def copied_onto(self, source: str, layout: str) -> list[Command]:
        """What puts a copy of everything on the template's layout ``source`` on ``layout``: first the assets the
        objects need and the presentation lacks, then the objects with ids nobody has."""
        model, template = self.model, self.template
        objects: list[Command] = []
        needed: set[tuple[str, str]] = set()
        for obj in template.model.objects_on(source):
            new_id = free_id(model, obj.id, self.chosen)
            self.chosen.add(new_id)
            body = obj.body
            if body.paragraph is not None:
                body = replace(body, paragraph=replace(body.paragraph, id=new_id))
            needed |= _assets_of(template.model, obj)
            objects.append(AddObject(replace(body, id=new_id, name=""), replace(obj.anchor, slide=layout).to_data()))
        wanted = [
            (kind.name, asset_id) for kind in ASSET_KINDS for name, asset_id in sorted(needed) if name == kind.name
        ]
        assets: list[Command] = [
            DefineAsset(kind, template.model.assets[kind][asset_id].to_data())
            for kind, asset_id in wanted
            if asset_id not in model.assets[kind] and (kind, asset_id) not in self.defined
        ]
        self.defined.update(wanted)
        return [*assets, *objects]


def _assets_of(source: SlideModel, obj: SlideObject) -> set[tuple[str, str]]:
    """The assets of ``source`` that an object shows: its picture, shape, table, diagram or container, and the picture
    of the container."""
    found = {(kind.name, ref) for kind in ASSET_KINDS if (ref := getattr(obj.body, kind.name, None))}
    for name, ref in list(found):
        if name == "container" and (image := source.containers[ref].image):
            found.add(("image", image))
    return found


def _one(steps: tuple[Command, ...]) -> Command | None:
    """The one command the ``steps`` come to: none, the step itself, or a batch."""
    return steps[0] if len(steps) == 1 else Batch(steps) if steps else None


def _name(name: str) -> str:
    """A name as layouts are compared: without extra spaces, in no particular letters."""
    return " ".join(name.split()).casefold()
