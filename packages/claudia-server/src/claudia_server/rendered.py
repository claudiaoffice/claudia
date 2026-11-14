"""Rendered text containers on the wire: the methods every app that holds objects shares (D390, D395).

A container is a *definition* (the text a person writes, kept as the truth) and an object that shows it. The wire only
ever changes the text. The picture is made by the render service (``claudia-render``) and comes back into the document
as an ordinary edit (:meth:`RenderDesk.render_into`), so the picture is part of the document's history, opens on a
machine without the tool, and is exported like any other.

Wire methods here are synchronous like every other method of this server (one thread serves every document), and
rendering takes seconds, so they never render: ``add_rendering`` and ``set_rendering_source`` change the text and the
job that makes the picture is the server's business (the job path, D92/E3.4, runs :meth:`RenderDesk.render_into` off the
request). What this module guarantees already is that the document and the render service meet in one place.

``rendering_types`` tells a client and the AI what can be made (title, settings, an example, a hint on the syntax); it
says nothing about *how* a tool is run."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Any

from claudia_creates_io import Rasterise

from claudia_core import (
    AddObject,
    Batch,
    DefineImage,
    DefineRendering,
    DescribeObject,
    ForgetImage,
    ObjectBody,
    ObjectModel,
    ResizeObject,
    UpdateRendering,
    decode_image,
)
from claudia_core.renderings import RenderedDefinition
from claudia_render import RenderService, UnknownType, default_alt

from .i18n import msg
from .protocol import Context, MethodTable, RequestError

STYLE = "plain-image"
MAX_ALT = 500


class RenderDesk:
    """What a server offers for rendered containers: the types, and making a picture for a document.

    ``service`` is a :class:`~claudia_render.RenderService` (anything with its ``plugins`` and ``render``)."""

    def __init__(self, service: RenderService, rasteriser: Rasterise | None = None) -> None:
        self.service = service
        self.rasteriser = rasteriser  # draws an SVG as a PNG for office files; ``None``: they get the SVG alone (D394)

    def types(self) -> list[dict]:
        """What clients and the AI are told of each type (identity, settings, hints); never how it is run."""
        return [plugin.manifest.to_data() for plugin in self.service.plugins.plugins()]

    def check(self, kind: str, source: str, params: dict[str, Any]) -> dict[str, object]:
        """The settings of ``kind`` with defaults filled in, if ``source`` and ``params`` are acceptable; ``ValueError``
        (`UnknownType` is one) says what is wrong, in words for the person."""
        manifest = self.service.plugins.get(kind).manifest
        if len(source) > manifest.max_source_chars:
            raise ValueError(
                f"the text is too long for {manifest.title}: at most {manifest.max_source_chars} characters"
            )
        return manifest.check_params(params)

    async def render_into(self, document, user: str, rendering_id: str):  # noqa: ANN001, ANN201 - Document, Rendered
        """Make the picture of one container and take it into ``document`` as an edit of ``user``.

        Returns what the service made, or ``None`` if it no longer fits the document: the text or the settings changed
        while the tool ran (a newer job will make the picture of the newer text), or the container is gone. Nothing is
        changed then. An unchanged picture changes nothing. The picture it replaces is let go of if nobody else holds
        it, so that editing a diagram twenty times does not leave twenty pictures in the file."""
        model: ObjectModel = document.model
        definition = model.renderings[rendering_id]
        rendered = await self.service.render(definition.type, definition.source, dict(definition.params))
        current = model.renderings.get(rendering_id)
        if current is None or (current.source, dict(current.params)) != (definition.source, dict(definition.params)):
            return None
        asset = decode_image(rendered.svg.encode("utf-8"), checked_drawing=True)
        if (current.image, current.renderer) == (asset.id, rendered.renderer):
            return rendered
        steps: list = [] if asset.id in model.images else [DefineImage(asset)]
        steps.append(UpdateRendering(rendering_id, current.with_picture(asset.id, rendered.renderer).to_data()))
        old = current.image
        if old and old != asset.id and not self._held_elsewhere(model, old, rendering_id):
            steps.append(ForgetImage(old))
        for object_id in model.users_of_rendering(rendering_id):
            shown = model.get_object(object_id)
            if not shown.body.description and not shown.body.decorative:
                steps.append(DescribeObject(object_id, default_alt(current.type, current.source, rendered.svg), False))
            fitted = max(1, round(shown.body.w * asset.height / asset.width))
            if fitted != shown.body.h:  # the frame keeps its width and follows the picture's proportions
                steps.append(ResizeObject(object_id, shown.anchor.to_data(), shown.body.w, fitted))
        document.execute(Batch(tuple(steps), name="Render"), author=user)
        return rendered

    @staticmethod
    def _held_elsewhere(model: ObjectModel, image_id: str, rendering_id: str) -> bool:
        return bool(model.users_of_image(image_id)) or any(
            r.image == image_id for r in model.renderings.values() if r.id != rendering_id
        )


def _desk(ctx: Context) -> RenderDesk:
    if ctx.renderings is None:
        raise RequestError("unavailable", msg("this server does not make rendered containers"))
    return ctx.renderings


def _fresh(prefix: str, taken) -> str:
    while True:
        candidate = f"{prefix}{secrets.token_hex(4)}"
        if candidate not in taken:
            return candidate


def _types(ctx: Context) -> dict:
    """What can be made as a rendered container, as `{types}`; each is `{type, version, title, tier, requires, params,
    editor, max_source_chars}`: its settings (name, type, default, choices, bounds) and for an editor and the AI an
    `example` and a short `ai_hint` on the syntax. A server that makes none says `{types: []}`."""
    return {"types": [] if ctx.renderings is None else ctx.renderings.types()}


def _renderings(model_of: Callable[[Context], ObjectModel]):
    def renderings(ctx: Context) -> list[dict]:
        """The definitions of the rendered containers this document holds, each as `{format, id, type, source, params,
        image, renderer}`: the text is the truth, `image` the id of the picture last made from it (see `images`), and
        `renderer` says what made it. A container without a picture yet has `image: null`."""
        return [d.to_data() for _, d in sorted(model_of(ctx).renderings.items())]

    return renderings


def _add(model_of: Callable[[Context], ObjectModel], anchor_of: Callable[..., dict], ensure: Callable[..., None]):
    def add_rendering(ctx: Context, *, w, h, type, source, params, alt, base, **where):  # noqa: A002 - the wire name
        """Put a rendered container where the person points: `type` is one of `rendering_types`, `source` the text
        (the truth the picture is made from), `params` its settings (defaults fill the rest), `alt` a short description
        for whoever cannot see the picture (one is made from the text if left out). Returns the new `object`, its
        `rendering` and the revision. The text is not drawn yet: the picture arrives as a later edit."""
        desk, model = _desk(ctx), model_of(ctx)
        ensure(model, **where)
        settings = desk.check(type, source, params or {})
        rendering_id = _fresh("r", model.renderings)
        object_id = _fresh("o", model.objects)
        words = (alt or "")[:MAX_ALT]
        body = ObjectBody(object_id, "rendered", w, h, STYLE, rendered=rendering_id, description=words)
        definition = RenderedDefinition(rendering_id, type, source, settings)  # type: ignore[arg-type]
        command = Batch(
            (DefineRendering(definition.to_data()), AddObject(body, anchor_of(**where))), name="Add rendered container"
        )
        applied = ctx.document.execute(command, author=ctx.user, base=base)
        return {"object": object_id, "rendering": rendering_id, "revision": applied.revision.to_data()}

    return add_rendering


def _set_source(model_of: Callable[[Context], ObjectModel]):
    def set_rendering_source(ctx: Context, *, id, source, params, base):  # noqa: A002
        """Change the text of a rendered container (and, if `params` is given, its settings; the others keep their
        value). The picture stays as it is until the new one is made."""
        desk, model = _desk(ctx), model_of(ctx)
        if id not in model.renderings:
            raise RequestError("command_error", msg("this document has nothing rendered with the id {id!r}", id=id))
        current = model.renderings[id]
        settings = desk.check(current.type, source, {**dict(current.params), **(params or {})})
        changed = RenderedDefinition(id, current.type, source, settings, current.image, current.renderer)  # type: ignore[arg-type]
        applied = ctx.document.execute(UpdateRendering(id, changed.to_data()), author=ctx.user, base=base)
        return {"rendering": id, "revision": applied.revision.to_data()}

    return set_rendering_source


def add_rendering_methods(
    table: MethodTable,
    *,
    model_of: Callable[[Context], ObjectModel],
    anchor: tuple[str, Callable[..., dict], Callable[..., None]] | None,
) -> None:
    """Register ``rendering_types`` and ``renderings`` on ``table``, and unless ``anchor`` is ``None`` the methods that
    change containers too. ``anchor`` is how an app places an object: its parameters as a wire spec (``"slide:str x:int
    y:int"``), a function from them to the anchor's plain data, and a check that they name a real place."""
    table.method("rendering_types")(_types)
    table.method("renderings")(_renderings(model_of))
    if anchor is None:
        return
    spec, anchor_of, ensure = anchor
    table.method(
        "add_rendering",
        f"{spec} w:int h:int type:str source:text params:dict? alt:text? base:revision?",
        write=True,
    )(_add(model_of, anchor_of, ensure))
    table.method("set_rendering_source", "id:str source:text params:dict? base:revision?", write=True)(
        _set_source(model_of)
    )


__all__ = ["RenderDesk", "UnknownType", "add_rendering_methods"]
