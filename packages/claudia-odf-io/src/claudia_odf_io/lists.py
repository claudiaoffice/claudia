"""The levels of a list in OpenDocument, both ways: what a level of a numbering scheme of the model is in a list style
(or the outline style), and what one of those says as a level of a scheme (E9.22). Shared by the text and the
presentation app, whose lists are written the same way.

A level of the model writes its counter in a format, or a bullet, with text before and after, and shows the counters
from some level on (``2.1.3`` or ``c``). OpenDocument says the same with ``style:num-format``, ``style:num-prefix``,
``style:num-suffix`` and ``text:display-levels``, or ``text:bullet-char``. What a level of the model cannot say (a
picture bullet, a format such as ``１, ２, ３``) reads as ``None``: the reader keeps a built-in scheme and reports the
look.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from lxml import etree

from claudia_core import MAX_LIST_LEVEL, LevelFormat, ListDef, Scheme

from .names import NS

#: A model format and what OpenDocument calls it (a bullet is a level style of its own kind there).
ODF_FORMATS = {
    "decimal": "1",
    "lower-alpha": "a",
    "upper-alpha": "A",
    "lower-roman": "i",
    "upper-roman": "I",
    "none": "",
}
_FROM_ODF = {odf: model for model, odf in ODF_FORMATS.items()}
_MAX_AFFIX = 20
#: How far each level moves the text in: a scheme says it in em, a list style wants a length.
CM_PER_EM = 0.4


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


LEVEL_NUMBER, LEVEL_BULLET = _q("text", "list-level-style-number"), _q("text", "list-level-style-bullet")
OUTLINE_LEVEL = _q("text", "outline-level-style")


def _affix(text: str) -> bool:
    return len(text) <= _MAX_AFFIX and (not text or text.isprintable())


def _attribute(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def odf_level(level: LevelFormat, number: int) -> dict[str, str]:
    """The attributes (by local name) that draw ``level`` at level ``number`` (0 the outermost): ``num-format``,
    ``num-prefix``, ``num-suffix`` and ``display-levels``, or for a bullet ``bullet-char`` and the prefix and suffix."""
    if level.format == "bullet":
        return {"bullet-char": level.bullet, "num-prefix": level.before, "num-suffix": level.after}
    return {
        "num-format": ODF_FORMATS[level.format],
        "num-prefix": level.before,
        "num-suffix": level.after,
        "display-levels": str(number - level.from_level + 1),
    }


def read_odf_level(attributes: Mapping[str, str | None], number: int, *, bullet: bool) -> LevelFormat | None:
    """The level the attributes of a level style say (by their local names), at level ``number``; ``None`` when a
    level of the model cannot say it."""
    before, after = attributes.get("num-prefix") or "", attributes.get("num-suffix") or ""
    if not (_affix(before) and _affix(after)):
        return None
    if bullet:
        sign = attributes.get("bullet-char") or ""
        drawable = 1 <= len(sign) <= 4 and sign.isprintable()
        return LevelFormat("bullet", sign, before, after, number) if drawable else None
    model = _FROM_ODF.get(attributes.get("num-format") or "")
    try:
        shown = int(attributes.get("display-levels") or "1")
    except ValueError:
        return None
    if model is None or not 1 <= shown <= number + 1:
        return None
    return LevelFormat(model, before=before, after=after, from_level=number - shown + 1 if model != "none" else number)


def level_style(kind: str, level: LevelFormat, number: int, inner: str = "", start: int | None = None) -> str:
    """One level of a list style (``kind`` ``list-level-style``) or of the outline style (``outline-level-style``),
    drawing ``level`` at level ``number``, with ``inner`` (its positions) inside; the outline draws a bullet as none."""
    if kind != "list-level-style" and level.format == "bullet":
        level = LevelFormat("none", before=level.before, after=level.after, from_level=number)
    said = odf_level(level, number)
    attributes = f' text:level="{number + 1}"'
    if level.format == "bullet":
        attributes += f' text:bullet-char="{_attribute(said["bullet-char"])}"'
        tag = f"text:{kind}-bullet"
    else:
        attributes += f' style:num-format="{said["num-format"]}"'
        if said["display-levels"] != "1":
            attributes += f' text:display-levels="{said["display-levels"]}"'
        tag = f"text:{kind}-number" if kind == "list-level-style" else f"text:{kind}"
    for key in ("num-prefix", "num-suffix"):
        if said.get(key):
            attributes += f' style:{key}="{_attribute(said[key])}"'
    if start is not None:
        attributes += f' text:start-value="{start}"'
    return f"<{tag}{attributes}>{inner}</{tag}>"


def list_style(definition: ListDef, scheme: Scheme, name: str) -> bytes:
    """The ``text:list-style`` that makes a list of the model look as its ``scheme`` draws it: ``name`` is what the
    lists in the text call it, and every level (the model has nine) its marker and its indent. It declares the
    prefixes it uses, so that it can go into a part that does not."""
    step = f"{round(scheme.indent * CM_PER_EM, 3):g}"
    declared = " ".join(f'xmlns:{prefix}="{NS[prefix]}"' for prefix in ("text", "style", "fo"))
    display = f' style:display-name="{_attribute(definition.name)}"' if definition.name else ""
    levels = []
    for level in range(MAX_LIST_LEVEL + 1):
        indent = f"{round(scheme.indent * CM_PER_EM * (level + 1), 3):g}"
        position = (
            '<style:list-level-properties text:list-level-position-and-space-mode="label-alignment">'
            f'<style:list-level-label-alignment text:label-followed-by="listtab" '
            f'text:list-tab-stop-position="{indent}cm" fo:text-indent="-{step}cm" fo:margin-left="{indent}cm"/>'
            "</style:list-level-properties>"
        )
        start = definition.start if level == 0 and scheme.counts and definition.start != 1 else None
        levels.append(level_style("list-level-style", scheme.level(level), level, position, start))
    return f'<text:list-style {declared} style:name="{name}"{display}>{"".join(levels)}</text:list-style>'.encode()


def read_levels(style: etree._Element, tags: Iterable[str]) -> dict[int, LevelFormat | None]:
    """What each level of a list style (or the outline style) draws, as a level of a scheme; ``None`` where none can
    say it. ``tags`` are the level styles to read (``LEVEL_NUMBER``, ``LEVEL_BULLET``, ``OUTLINE_LEVEL``)."""
    wanted = set(tags)
    found: dict[int, LevelFormat | None] = {}
    for element in style:
        try:
            number = int(element.get(_q("text", "level")) or "")
        except ValueError:
            continue
        if element.tag not in wanted or not 1 <= number <= MAX_LIST_LEVEL + 1:
            continue
        attributes = {etree.QName(key).localname: str(value) for key, value in element.attrib.items()}
        found[number - 1] = read_odf_level(attributes, number - 1, bullet=element.tag == LEVEL_BULLET)
    return found


def counts(style: etree._Element | None) -> bool:
    """Does the first level of a list style count (a number level style), or is it a bullet?"""
    if style is None:
        return False
    levels = (e for e in style if e.tag in (LEVEL_NUMBER, LEVEL_BULLET))
    first = next((e for e in levels if e.get(_q("text", "level")) == "1"), None)
    return first is not None and first.tag == LEVEL_NUMBER
