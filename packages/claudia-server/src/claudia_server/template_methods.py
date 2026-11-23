"""What a presentation can do about templates (E10.4, E10.22, D1537, D1539): ``template`` says where it came from,
``save_as_template`` makes a template file of it, ``change_theme`` and ``change_template`` give it the look of a
template of the server, or the whole template (D1531)."""

from __future__ import annotations

import base64

from claudia_core.clock import utc_now
from claudia_creates.template import Template, TemplateInfo, plan_change_template, plan_change_theme

from .i18n import message_of, msg
from .protocol import Context, MethodTable, RequestError
from .template_library import SUFFIX, slug, template_file
from .wire import current_revision, done

#: What ``save_as_template`` answers as the ``format``; the audit says the same.
TEMPLATE_FORMAT = "claudia-template"


def add_template_methods(table: MethodTable, *, model_of) -> None:  # noqa: ANN001 - the app's own accessor
    """Add the template methods to the method table of presentations."""

    @table.method("template")
    def _template(ctx: Context):
        """The template this presentation was started from, or had its layouts changed to, as `{name, purpose,
        language}`; `null` when it came from none. Only a note of where it came from: nothing follows the template
        (D1531)."""
        note = model_of(ctx).template
        return None if note is None else note.to_data()

    @table.method("save_as_template", "name:str purpose:str language:str", leaves="export")
    def _save_as_template(ctx: Context, *, name, purpose, language):
        """File ▸ Save as template…: a Claudia export of this presentation without its slides, with their words,
        notes, times and pictures left out and the layouts, styles and colours kept, as a template called `name`,
        for `purpose`, in `language` (a tag like `en`, `de`, `en-GB`). Answers `{format: "claudia-template", filename,
        content_type, data (base64), parts}` and is recorded in the document as an export by you. `command_error`
        names what is wrong with the note. The assistant does not export."""
        if ctx.account.system:
            raise RequestError("forbidden", msg("the assistant does not export the document"))
        try:
            info = TemplateInfo(name, purpose, language)
        except ValueError as exc:
            raise RequestError("command_error", message_of(exc)) from None
        data = template_file(model_of(ctx), info, exporter=ctx.user, exported_at=utc_now())
        return {
            "format": TEMPLATE_FORMAT,
            "filename": f"{slug(info.name)}{SUFFIX}",
            "content_type": "application/zip",
            "data": base64.b64encode(data).decode("ascii"),
            "parts": ["content"],
        }

    @table.method("change_theme", "template:str base:revision?", write=True)
    def _change_theme(ctx: Context, *, template, base):
        """Change theme: give the presentation the styles and colours of the template `template` (an id from
        `GET /api/templates`). A built-in style is matched by its id, any other by its name in any letters; the
        colours of the theme replace those with the same id, new ones are added, and the presentation's own stay; its
        layouts and slides are not touched. One step, one Undo. Answers `{changed, revision}`; `changed` is false
        when it looked like that already. `command_error` for an unknown template."""
        command = plan_change_theme(model_of(ctx), _found(ctx, template))
        if command is None:
            return {"changed": False, "revision": current_revision(ctx)}
        return done(ctx, command, base, changed=True)

    @table.method("change_template", "template:str base:revision?", write=True)
    def _change_template(ctx: Context, *, template, base):
        """Change template: give the presentation the theme (as `change_theme`) and the layouts of the template
        `template`. A layout with the name of one of the template's (in any letters) keeps its slides and gets what
        is on the template's; a box bound to a placeholder follows the one with the same purpose; a layout the
        presentation lacks is added; nothing it has of its own is taken away. One step, one Undo; the presentation
        keeps a note of the template (`template`). Answers `{changed, revision}`. `command_error` for an unknown
        template."""
        return done(ctx, plan_change_template(model_of(ctx), _found(ctx, template)), base, changed=True)


def _found(ctx: Context, template_id: str) -> Template:
    """The template of this server with that id; ``command_error`` when there is none."""
    library = ctx.template_library()
    found = None if library is None else library.get(template_id)
    if found is None:
        raise RequestError("command_error", msg("there is no template {id!r} on this server", id=template_id))
    return found


__all__ = ["TEMPLATE_FORMAT", "add_template_methods"]
