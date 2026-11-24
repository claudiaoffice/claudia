"""The templates of a server, and the file a template is (E10.4, E10.22, D1537).

A template file is a Claudia export (:mod:`claudia_document_file.export_file`) of a presentation without slides, with
the note of what it is: no history, no chat, nothing of the slides. :func:`template_file` writes one and
:func:`read_template_file` reads one, or refuses it with a sentence.

A server offers the built-in **Basic** template and those its administrators added: each is a file of that kind under
``STATE_DIR/templates``, named after the template. :class:`TemplateLibrary` keeps them; what is stored is rebuilt from
what was checked, so a file that came with a history or a chat keeps neither.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from claudia_core import N_
from claudia_core.clock import utc_now
from claudia_creates import SlideModel
from claudia_creates.template import (
    Template,
    TemplateInfo,
    TemplateRefused,
    basic_template,
    check_template,
    template_state,
)
from claudia_document_file import DocumentFileError, read_export, write_export

from .i18n import translate

log = logging.getLogger(__name__)

BASIC_ID = "basic"
SUFFIX = ".claudia-export.zip"
MAX_TEMPLATE_BYTES = 16 * 1024 * 1024
"""Largest a template file may be: a few layouts with a logo are a few hundred kilobytes."""
#: What the built-in template says about itself, said in the language of whoever asks.
BASIC_NAME = N_("Basic")
BASIC_PURPOSE = N_("Slides with nothing prepared: a layout without placeholders")


@dataclass(frozen=True)
class Listed:
    """A template of the library: the id it is known by, the template, and whether it is the built-in one."""

    id: str
    template: Template
    builtin: bool = False


def template_file(model: SlideModel, info: TemplateInfo, *, exporter: str, exported_at: str) -> bytes:
    """The file of ``model`` as the template ``info``: its content as
    :func:`~claudia_creates.template.template_state` makes it, and nothing else. ``model`` is not changed."""
    return write_export(
        model.app,
        model.state_schema,
        template_state(model, info),
        exporter=exporter,
        exported_at=exported_at,
    )


def read_template_file(data: bytes) -> Template:
    """The template a file holds. :class:`~claudia_document_file.ExportRefused` for a file that is no export;
    ``TemplateRefused`` for an export of another app or version, or of a presentation that is no template."""
    exported = read_export(data)
    if exported.app != SlideModel.app:
        raise TemplateRefused(N_("this is not a presentation"))
    if exported.state_schema != SlideModel.state_schema:
        raise TemplateRefused(N_("this template was made by another version of Claudia"))
    return check_template(exported.state)


def offered_layouts(template: Template) -> list[str]:
    """The names of the layouts of ``template`` that a person can choose for a slide: the hidden ones are left out."""
    return [layout.name for layout in template.model.layouts if not layout.hidden]


def describe(entry: Listed, locale: str) -> dict:
    """What a list of templates says of one: its id, name, what it is for, its language, whether it is the built-in
    one, and the names of its layouts. The built-in one is said in ``locale``."""
    info = entry.template.info
    name, purpose = (info.name, info.purpose)
    if entry.builtin:
        name, purpose = translate(BASIC_NAME, locale), translate(BASIC_PURPOSE, locale)
    return {
        "id": entry.id,
        "name": name,
        "purpose": purpose,
        "language": info.language,
        "builtin": entry.builtin,
        "layouts": offered_layouts(entry.template),
    }


def slug(name: str) -> str:
    """A name as a file name and an id: ASCII letters and digits in lower case, joined by hyphens; ``template`` if
    nothing is left."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:40].strip("-") or "template"


class TemplateLibrary:
    """The built-in template and the templates added to ``folder``, one file each."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self._basic = Listed(BASIC_ID, basic_template(), builtin=True)
        self._added: dict[str, Template] = {}
        self.reload()

    def reload(self) -> None:
        """Read the folder again; a file that is no template is left out and logged, never fatal."""
        self._added = {}
        if not self.folder.is_dir():
            return
        for path in sorted(self.folder.glob(f"*{SUFFIX}")):
            template_id = path.name.removesuffix(SUFFIX)
            try:
                template = read_template_file(path.read_bytes())
                if template_id == BASIC_ID or self._has_name(template.info.name):
                    raise ValueError("its id or its name is another template's")
            except (OSError, ValueError, DocumentFileError) as error:
                log.warning("template %s is not used: %s", path.name, error)
                continue
            self._added[template_id] = template

    def entries(self) -> list[Listed]:
        """Basic first, then the added templates by name."""
        added = sorted(self._added.items(), key=lambda item: item[1].info.name.casefold())
        return [self._basic, *(Listed(id, template) for id, template in added)]

    def get(self, template_id: str) -> Template | None:
        """The template with this id, or ``None`` when there is none."""
        if template_id == BASIC_ID:
            return self._basic.template
        return self._added.get(template_id)

    def check(self, data: bytes) -> Template:
        """The template ``data`` holds, if the library could take it: whatever :func:`read_template_file` refuses, and
        ``TemplateRefused`` for a name another template has, in any letters (Basic's too)."""
        template = read_template_file(data)
        if self._has_name(template.info.name):
            raise TemplateRefused(N_("there is a template called {name} already"), name=template.info.name)
        return template

    def _has_name(self, name: str) -> bool:
        return any(entry.template.info.name.casefold() == name.casefold() for entry in self.entries())

    def add(self, data: bytes, *, added_by: str) -> str:
        """Check ``data`` and keep it as a template; its id. The file is written afresh from what was checked, so
        that nothing else it held stays."""
        template = self.check(data)
        template_id = self._free_id(slug(template.info.name))
        kept = template_file(template.model, template.info, exporter=added_by, exported_at=utc_now())
        self.folder.mkdir(parents=True, exist_ok=True)
        _write(self.folder / f"{template_id}{SUFFIX}", kept)
        self._added[template_id] = template
        return template_id

    def remove(self, template_id: str) -> None:
        """Remove an added template and its file. ``TemplateRefused`` for the built-in one, ``KeyError`` for an id
        nobody has."""
        if template_id == BASIC_ID:
            raise TemplateRefused(N_("the basic template cannot be removed"))
        if template_id not in self._added:
            raise KeyError(template_id)
        (self.folder / f"{template_id}{SUFFIX}").unlink(missing_ok=True)
        del self._added[template_id]

    def _free_id(self, wanted: str) -> str:
        taken = {BASIC_ID, *self._added}
        candidate, number = wanted, 1
        while candidate in taken:
            number += 1
            candidate = f"{wanted}-{number}"
        return candidate


def _write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` all at once: a file is there whole or not at all."""
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".template-")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
