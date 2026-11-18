"""How the text flows round a floating object, in a docx and in an odt (D1061, D1066).

The model has four modes (:data:`claudia_composes.WRAPS`) and a gap, how far the words keep from the object, in CSS
pixels. Each office format has its own words for them:

* ``over``: docx ``wrapNone`` with ``behindDoc="0"``; odt ``wrap="run-through"`` with ``run-through="foreground"``;
* ``around``: docx ``wrapSquare`` and distances all round; odt ``wrap="parallel"`` and margins all round;
* ``above-below``: docx ``wrapTopAndBottom`` and distances above and below; odt ``wrap="none"`` and margins above and
  below;
* ``behind``: docx ``wrapNone`` with ``behindDoc="1"``; odt ``wrap="run-through"`` with
  ``run-through="background"``.

(ODF's ``wrap="none"`` is *not* "nothing wraps": it keeps the words off both sides of the frame, which is
*above and below*. Until D1066 the export wrote it for every picture and box, and a program that reads it as the
standard says pushed the text down.) What a file says that these words cannot hold (tight wrapping along an outline,
text only on the left or the right) reads as the nearest mode, ``around``."""

from __future__ import annotations

from collections.abc import Mapping

from lxml import etree

from claudia_composes import DEFAULT_WRAP_GAP, MAX_WRAP_GAP, BlockAnchor
from claudia_odf_io import NS

EMU = 9525  # one CSS pixel
_NS_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_WRAP_TAGS = ("wrapNone", "wrapSquare", "wrapTight", "wrapThrough", "wrapTopAndBottom")
_AROUND_TAGS = ("wrapSquare", "wrapTight", "wrapThrough")


def _wp(name: str) -> str:
    return f"{{{_NS_WP}}}{name}"


def clamped(pixels: int) -> int:
    """``pixels`` as a gap the model accepts."""
    return max(0, min(MAX_WRAP_GAP, pixels))


# ------------------------------------------------------------------------------------------------------------- docx
def _distances(anchor: BlockAnchor) -> dict[str, str]:
    """The ``distT`` ``distB`` ``distL`` ``distR`` of a ``wp:anchor`` (EMU): how far the words keep away."""
    around, above_below = anchor.wrap == "around", anchor.wrap == "above-below"
    side = anchor.gap * EMU if around else 0
    vertical = anchor.gap * EMU if around or above_below else 0
    return {"distT": str(vertical), "distB": str(vertical), "distL": str(side), "distR": str(side)}


def docx_wrap_element(anchor: BlockAnchor) -> str:
    """The ``wp:wrap…`` element of ``anchor``, written as XML."""
    return {
        "around": '<wp:wrapSquare wrapText="bothSides"/>',
        "above-below": "<wp:wrapTopAndBottom/>",
    }.get(anchor.wrap, "<wp:wrapNone/>")


def docx_frame_open(anchor: BlockAnchor, number: int) -> str:
    """The opening tag of the ``wp:anchor`` of a drawing numbered ``number`` that floats as ``anchor`` says."""
    distances = " ".join(f'{name}="{value}"' for name, value in _distances(anchor).items())
    behind = "1" if anchor.wrap == "behind" else "0"
    return (
        f'<wp:anchor {distances} simplePos="0" relativeHeight="{number}" '
        f'behindDoc="{behind}" locked="0" layoutInCell="1" allowOverlap="1">'
    )


def docx_wrap_of(frame: etree._Element) -> tuple[str, int]:
    """``(wrap, gap)`` a ``wp:anchor`` (or a ``wp:inline``, which floats over the text in the model) says."""
    if frame.tag != _wp("anchor"):
        return "over", DEFAULT_WRAP_GAP
    kind = next((child.tag for child in frame if child.tag in {_wp(each) for each in _WRAP_TAGS}), _wp("wrapNone"))
    local = etree.QName(kind).localname
    if local in _AROUND_TAGS:
        return "around", clamped(round(_int(frame.get("distL")) / EMU))
    if local == "wrapTopAndBottom":
        return "above-below", clamped(round(_int(frame.get("distT")) / EMU))
    behind = frame.get("behindDoc") in ("1", "true")
    return ("behind" if behind else "over"), DEFAULT_WRAP_GAP


def docx_set_wrap(frame: etree._Element, anchor: BlockAnchor) -> None:
    """Make an existing ``wp:anchor`` say what ``anchor`` says about its wrapping: its distances, ``behindDoc`` and its
    ``wp:wrap…`` element, which stays where it is among the others (the schema orders them)."""
    if frame.tag != _wp("anchor"):
        return
    for name, value in _distances(anchor).items():
        frame.set(name, value)
    frame.set("behindDoc", "1" if anchor.wrap == "behind" else "0")
    fresh = etree.fromstring(docx_wrap_element(anchor).replace("/>", f' xmlns:wp="{_NS_WP}"/>'))
    old = [child for child in frame if child.tag in {_wp(each) for each in _WRAP_TAGS}]
    if old:
        frame.replace(old[0], fresh)
        for extra in old[1:]:
            frame.remove(extra)
        return
    after = frame.find(_wp("effectExtent"))
    after = after if after is not None else frame.find(_wp("extent"))
    frame.insert(len(frame) if after is None else list(frame).index(after) + 1, fresh)


def _int(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


# -------------------------------------------------------------------------------------------------------------- odt
#: ``style:wrap`` and ``style:run-through`` of each mode.
_ODF = {
    "over": ("run-through", "foreground"),
    "around": ("parallel", "foreground"),
    "above-below": ("none", "foreground"),
    "behind": ("run-through", "background"),
}
_ODF_AROUND = {"parallel", "dynamic", "left", "right", "biggest"}


def odf_name(base: str, anchor: BlockAnchor) -> str:
    """The name of the graphic style that ``base`` (the style of a picture or a box) is given to wrap as ``anchor``
    says: ``base`` itself where the words stay over the text, else ``base`` and the mode, and the gap if it is not the
    usual one."""
    if anchor.wrap == "over":
        return base
    gap = "" if anchor.gap == DEFAULT_WRAP_GAP else f"_{anchor.gap}"
    return f"{base}_{anchor.wrap.replace('-', '_')}{gap}"


def odf_attributes(anchor: BlockAnchor) -> str:
    """``style:wrap``, ``style:run-through`` and the margins of the graphic properties for ``anchor``."""
    wrap, through = _ODF[anchor.wrap]
    cm = f"{anchor.gap / 96 * 2.54:.3f}cm"
    margins = ""
    if anchor.wrap == "around":
        margins = f'fo:margin-left="{cm}" fo:margin-right="{cm}" fo:margin-top="{cm}" fo:margin-bottom="{cm}"'
    elif anchor.wrap == "above-below":
        margins = f'fo:margin-left="0cm" fo:margin-right="0cm" fo:margin-top="{cm}" fo:margin-bottom="{cm}"'
    return f'style:wrap="{wrap}" style:run-through="{through}" {margins}'.strip()


def odf_wrap_of(properties: Mapping[str, str]) -> tuple[str, int]:
    """``(wrap, gap)`` the graphic properties of a frame say (by ``prefix:name``, as the readers collect them)."""
    wrap = properties.get("style:wrap")
    if wrap in _ODF_AROUND:
        return "around", clamped(round(_length_px(properties.get("fo:margin-left", properties.get("fo:margin")))))
    if wrap == "none":
        return "above-below", clamped(round(_length_px(properties.get("fo:margin-top", properties.get("fo:margin")))))
    if wrap == "run-through" and properties.get("style:run-through") == "background":
        return "behind", DEFAULT_WRAP_GAP
    return "over", DEFAULT_WRAP_GAP


def _length_px(text: str | None) -> float:
    """A length of an odf attribute (``0.212cm``, ``2mm``, ``0.1in``, ``6pt``, ``8px``; the first of several) in CSS
    pixels."""
    if not text:
        return 0.0
    first = text.split()[0]
    for unit, per_inch in (("cm", 2.54), ("mm", 25.4), ("in", 1.0), ("pt", 72.0), ("px", 96.0)):
        if first.endswith(unit):
            try:
                return float(first[: -len(unit)]) / per_inch * 96
            except ValueError:
                return 0.0
    return 0.0


def odf_properties(element: etree._Element, graphics: Mapping[str, etree._Element]) -> dict[str, str]:
    """What the graphic style of ``element`` (and the styles it is based on) says, by ``prefix:name``; what the
    element's own style says wins over what its parents say."""
    found: dict[str, str] = {}
    name: str | None = element.get(f"{{{NS['draw']}}}style-name")
    seen: set[str] = set()
    while name and name in graphics and name not in seen:
        seen.add(name)
        style = graphics[name]
        for properties in style.findall("style:graphic-properties", NS):
            for key, value in properties.attrib.items():
                uri, local = etree.QName(key).namespace, etree.QName(key).localname
                short = next((each for each, known in NS.items() if known == uri), "")
                found.setdefault(f"{short}:{local}", str(value))
        name = style.get(f"{{{NS['style']}}}parent-style-name")
    return found


def odf_wrap_style_xml(name: str, anchor: BlockAnchor, parent: str | None = None) -> str:
    """A graphic style called ``name`` that says only how the words flow round a frame as ``anchor`` says, on top of
    its ``parent``'s look (a file's own style for a frame it has, kept as it is)."""
    inherits = f' style:parent-style-name="{parent}"' if parent else ""
    return (
        f'<style:style xmlns:style="{NS["style"]}" xmlns:fo="{NS["fo"]}" style:name="{name}" '
        f'style:family="graphic"{inherits}><style:graphic-properties {odf_attributes(anchor)}/></style:style>'
    )


class WrapStyles:
    """The graphic styles a kept file needs for frames whose wrapping changed: one for each wrapping and each style
    the frame had, based on that style, so its look stays as it was."""

    def __init__(self, taken: set[str] | None = None) -> None:
        self.taken = taken if taken is not None else set()
        self.new: dict[str, bytes] = {}  # by name

    def give(self, element: etree._Element, anchor: BlockAnchor) -> None:
        """Make ``element`` (a frame or a shape, a copy of the file's) wrap as ``anchor`` says."""
        key = f"{{{NS['draw']}}}style-name"
        parent = element.get(key)
        name = f"{parent or 'Claudia_20_wrap'}_{anchor.wrap.replace('-', '_')}_{anchor.gap}"
        if name not in self.taken:
            self.taken.add(name)
            self.new[name] = odf_wrap_style_xml(name, anchor, parent).encode()
        element.set(key, name)


__all__ = [
    "clamped",
    "docx_frame_open",
    "docx_set_wrap",
    "docx_wrap_element",
    "docx_wrap_of",
    "WrapStyles",
    "odf_attributes",
    "odf_name",
    "odf_properties",
    "odf_wrap_of",
    "odf_wrap_style_xml",
]
