"""A rendered text container's definition: the text a person writes and the picture last made from it (D390).

A LaTeX formula, a Mermaid diagram and a Typst page are the same thing to the document: *text is the truth*, and a
picture is made from it by something outside the document. This module is the whole of what the kernel knows about
that. It holds the text (``source``), says which kind of text it is (``type``, a plugin's id: the kernel never looks
inside it), keeps the settings the person chose (``params``) and names the picture last made (``image``, the id of an
:class:`~claudia_core.ImageAsset` the document keeps) with a note of what made it (``renderer``).

Nothing here runs a renderer or reads the source: rendering is a service of the server (``claudia-render``), and the
picture comes back into the document through the ordinary image path, so a document opens, prints and exports on a
machine where the renderer is not installed (D391).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

#: How much text a container may hold. The same bound as a typeset job's (``claudia_typeset.job.MAX_RENDERING_SOURCE``).
MAX_RENDERING_SOURCE = 200_000
MAX_PARAMS = 32
MAX_PARAM_TEXT = 200
MAX_RENDERER_CHARS = 200

#: The version of the plain-data form below.
FORMAT = 1

_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}")
_TYPE = re.compile(r"[a-z][a-z0-9-]{0,31}")
_PARAM_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
_IMAGE = re.compile(r"[0-9a-f]{64}")  # a sha256 digest: the id of an image asset (claudia_core.assets)

type Scalar = str | int | float | bool


def _check_params(params: Mapping[str, object]) -> None:
    if not isinstance(params, Mapping) or len(params) > MAX_PARAMS:
        raise ValueError(f"param: at most {MAX_PARAMS} settings, each with a plain name")
    for name, value in params.items():
        if not isinstance(name, str) or not _PARAM_NAME.fullmatch(name):
            raise ValueError(f"param {str(name)[:40]!r}: a lower-case name of letters, digits and '_'")
        if not isinstance(value, str | int | float | bool):
            raise ValueError(f"param {name!r}: a number, a truth value or a short text, nothing else")
        if isinstance(value, str) and len(value) > MAX_PARAM_TEXT:
            raise ValueError(f"param {name!r}: at most {MAX_PARAM_TEXT} characters")


@dataclass(frozen=True)
class RenderedDefinition:
    """The text of one rendered container, and the picture last made from it.

    ``id`` names it in the document and ``type`` says what kind of text it is (a plugin's id, such as ``mermaid``);
    both are plain names, and the type of a definition never changes. ``source`` is the text (it may be empty while
    somebody is still writing it). ``params`` are the settings the person chose, few and plain. ``image`` is the id of
    the picture's :class:`~claudia_core.ImageAsset`, or ``None`` while there is none, and ``renderer`` names what made
    it (the plugin's version and the tools behind it) so that a later run can tell the picture has aged. A picture and
    its ``renderer`` are only ever changed together.

    Identical in all three apps: unlike a chart's definition (a cell range, meaningful only to computes), this one
    needs no app to read it."""

    id: str
    type: str
    source: str
    params: Mapping[str, Scalar] = field(default_factory=dict)
    image: str | None = None
    renderer: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not _ID.fullmatch(self.id):
            raise ValueError(
                f"rendering id {str(self.id)[:40]!r}: lower-case letters, digits, '-' and '_', first a letter"
            )
        if not isinstance(self.type, str) or not _TYPE.fullmatch(self.type):
            raise ValueError(
                f"rendering type {str(self.type)[:40]!r}: a plain lower-case name of at most 32 characters"
            )
        if not isinstance(self.source, str) or len(self.source) > MAX_RENDERING_SOURCE:
            raise ValueError(f"rendering source: text of at most {MAX_RENDERING_SOURCE} characters")
        _check_params(self.params)
        if self.image is not None and (not isinstance(self.image, str) or not _IMAGE.fullmatch(self.image)):
            raise ValueError(f"rendering image {str(self.image)[:40]!r}: not the id of an image")
        if not isinstance(self.renderer, str) or len(self.renderer) > MAX_RENDERER_CHARS:
            raise ValueError(f"rendering renderer: text of at most {MAX_RENDERER_CHARS} characters")
        object.__setattr__(self, "params", MappingProxyType(dict(sorted(self.params.items()))))

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {
            "format": FORMAT,
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "params": dict(self.params),
            "image": self.image,
            "renderer": self.renderer,
        }

    @classmethod
    def from_data(cls, data: dict) -> RenderedDefinition:
        """Inverse of :meth:`to_data`; ``ValueError`` if the data is not a definition of a format this reads."""
        if data.get("format") != FORMAT:
            raise ValueError(f"a rendering of format {data.get('format')!r}: this server reads format {FORMAT}")
        known = {"format", "id", "type", "source", "params", "image", "renderer"}
        if set(data) != known:
            raise ValueError("a rendering has exactly these fields: " + ", ".join(sorted(known)))
        return cls(data["id"], data["type"], data["source"], data["params"], data["image"], data["renderer"])

    def with_picture(self, image: str | None, renderer: str) -> RenderedDefinition:
        """The same definition with a new picture (or none) and the note of what made it."""
        return RenderedDefinition(self.id, self.type, self.source, self.params, image, renderer)

    def redacted(self) -> RenderedDefinition:
        """The definition with its words gone (redaction, D21): what it is and where it sits stay, the text does not."""
        return RenderedDefinition(self.id, self.type, "", self.params, self.image, self.renderer)
