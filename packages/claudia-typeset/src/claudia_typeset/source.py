"""The TeX source built around a formula or a page, and reading the engine's log afterwards (E3.4).

Fonts are chosen here, from the catalogue, by name: fontconfig aliases are not honoured by
XeTeX, so a substitution such as Times New Roman to Liberation Serif is applied in the source
(``Catalogue.resolve``) and the job's ``fonts.conf`` only decides where fonts are found.
"""

import re
from dataclasses import dataclass

from claudia_fonts import Catalogue

from .job import Job, Mode, is_plain_family

DEFAULT_TEXT_FONT = "Latin Modern Roman"
DEFAULT_MATH_FONT = "Latin Modern Math"

_PACKAGES = (
    r"\usepackage{amsmath}" "\n" r"\usepackage{amssymb}" "\n" r"\usepackage{fontspec}" "\n" r"\usepackage{unicode-math}"
)
_ERROR_WITH_LINE = re.compile(r"^(?P<file>[^\n:]*?):(?P<line>\d+): (?P<message>.+)$", re.MULTILINE)
_ERROR_BANG = re.compile(r"^! (?P<message>.+)$", re.MULTILINE)
_CONTEXT = re.compile(r"^l\.\d+ (?P<context>.*)$", re.MULTILINE)
_MAX_MESSAGE = 300


class FontUnavailable(ValueError):
    """The catalogue cannot provide a font the job needs; the message names it."""


@dataclass(frozen=True)
class Built:
    """A TeX source and where the user's own text starts in it (1-based) and how many lines it has."""

    text: str
    first_line: int
    line_count: int


@dataclass(frozen=True)
class TexError:
    """The first error of a run: what TeX said, the line of the user's text it is in (or None), and its context."""

    message: str
    line: int | None
    context: str = ""


def _family(catalogue: Catalogue, requested: str) -> str:
    provided = catalogue.resolve(requested).provided
    if provided is None:
        raise FontUnavailable(f"the font {requested!r} is not available on this server")
    if not is_plain_family(provided):
        raise FontUnavailable(f"the font {requested!r} is provided as {provided[:40]!r}, which is not a plain name")
    return provided


def _math_family(catalogue: Catalogue) -> str:
    if catalogue.fonts_of(DEFAULT_MATH_FONT):
        return _family(catalogue, DEFAULT_MATH_FONT)
    for font in catalogue.fonts():
        if font.math:
            return _family(catalogue, font.family)
    raise FontUnavailable("this server has no math font, so formulas cannot be set")


def build_source(job: Job, catalogue: Catalogue) -> Built:
    """The complete TeX source for ``job`` in math or page mode."""
    if job.mode is Mode.DOCUMENT:
        raise NotImplementedError("document mode is not available yet (E3.10)")
    text_font = _family(catalogue, job.font or DEFAULT_TEXT_FONT)
    math_font = _math_family(catalogue)
    if job.mode is Mode.MATH:
        options, before, after = "border=2pt", r"$\displaystyle", "$"
    else:
        options, before, after = f"border=4pt,varwidth={job.width_mm:g}mm", "", ""
    head = [
        rf"\documentclass[{options}]{{standalone}}",
        _PACKAGES,
        rf"\setmainfont{{{text_font}}}",
        rf"\setmathfont{{{math_font}}}",
        r"\begin{document}" + before,
    ]
    lines = job.source.split("\n")
    first_line = "\n".join(head).count("\n") + 2
    # the closing "$" is on a line of its own, so that a "%" at the end of the user's text cannot swallow it
    tail = [after, r"\end{document}"] if after else [r"\end{document}"]
    return Built("\n".join([*head, *lines, *tail]) + "\n", first_line, len(lines))


def _clean(text: str, job_folder: str | None) -> str:
    if job_folder:
        text = text.replace(job_folder.rstrip("/") + "/", "")
    return text.strip()[:_MAX_MESSAGE]


def parse_log(output: str, *, first_line: int, line_count: int, job_folder: str | None = None) -> TexError | None:
    """The first error in TeX's output, with its line in the user's text when it is inside it."""
    context = _CONTEXT.search(output)
    context_text = _clean(context["context"], job_folder) if context else ""
    located = _ERROR_WITH_LINE.search(output)
    if located:
        line = int(located["line"]) - first_line + 1
        inside = 1 <= line <= line_count
        return TexError(_clean(located["message"], job_folder), line if inside else None, context_text)
    bang = _ERROR_BANG.search(output)
    if bang:
        message = bang["message"]
        if message.startswith("fontspec error"):
            detail = re.search(r'The font "[^"]+" cannot be found', output)
            message = detail[0] if detail else message
        return TexError(_clean(message, job_folder), None, context_text)
    return None
