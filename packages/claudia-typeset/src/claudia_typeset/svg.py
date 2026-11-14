"""Checking an SVG that a converter made from a PDF before it is stored and shown to other people (E3.4, D66).

The converter is trusted, the document that went into it is not: a PDF can carry links and
embedded content. The check is an allowlist of drawing elements, never a blacklist of bad ones,
and it refuses anything that could run code or fetch something from outside.

Some tools draw more than paths (a diagram has text, markers and a ``<style>``). A caller may widen the list of
*elements* for its own tool (``extra_elements``), but never the rules about what an element may refer to, and never
to an element that can run code or fetch (``NEVER_ALLOWED``).
"""

import re
import xml.etree.ElementTree as ET  # noqa: S405 - a DOCTYPE, the only source of entities, is refused first

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"

_ELEMENTS = frozenset(
    {
        "svg", "g", "defs", "use", "symbol", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
        "clipPath", "mask", "pattern", "linearGradient", "radialGradient", "stop", "image", "title", "desc",
    }
)  # fmt: skip
#: Elements no profile can allow: they run code, embed another document or animate attributes.
NEVER_ALLOWED = frozenset(
    {"script", "foreignObject", "iframe", "object", "embed", "a", "animate", "animateMotion", "animateTransform", "set",
     "video", "audio", "canvas"}
)  # fmt: skip
_HREFS = (f"{{{XLINK_NS}}}href", "href")
_ALLOWED_NAMESPACED = frozenset({f"{{{XLINK_NS}}}href", f"{{{XML_NS}}}space"})
_LOCAL_REFERENCE = re.compile(r"#[\w.\-]+")
_RASTER = re.compile(r"data:image/(?:png|jpeg|gif|webp);base64,[A-Za-z0-9+/=\s]*")
_URL_FUNCTION = re.compile(r"url\(\s*([^)]*)\)", re.IGNORECASE)
_LOCAL_URL = re.compile(r"""['"]?#[\w.\-]+['"]?""")


class UnsafeOutput(ValueError):
    """The engine's output is not something we are willing to show; the message says what was found."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _check_attribute(element: str, name: str, value: str) -> None:
    if name.startswith("{") and name not in _ALLOWED_NAMESPACED:
        raise UnsafeOutput(f"<{element}> has the attribute {name!r}, which is not allowed")
    if _local(name).lower().startswith("on"):
        raise UnsafeOutput(f"<{element}> has the event handler {name!r}")
    if name in _HREFS and not (_LOCAL_REFERENCE.fullmatch(value) or (element == "image" and _RASTER.fullmatch(value))):
        raise UnsafeOutput(f"<{element}> refers to something outside the picture: {value[:40]!r}")
    for target in _URL_FUNCTION.findall(value):
        if not _LOCAL_URL.fullmatch(target.strip()):
            raise UnsafeOutput(f"<{element}> refers to something outside the picture: url({target[:40]})")
    if re.search(r"@import|javascript:|expression\(", value, re.IGNORECASE):
        raise UnsafeOutput(f"<{element}> has active content in {name!r}")


def _check_style_text(element: ET.Element) -> None:
    """The text of a ``<style>``: no other elements in it, no import, no reference to anything outside the picture."""
    if len(element):
        raise UnsafeOutput("<style> holds something other than text")
    text = element.text or ""
    if "\\" in text:
        raise UnsafeOutput("<style> has an escape sequence, which could hide a reference")
    if re.search(r"@import|javascript:|expression\(|behavior\s*:|-moz-binding", text, re.IGNORECASE):
        raise UnsafeOutput("<style> has active content or an import")
    for target in _URL_FUNCTION.findall(text):
        if not _LOCAL_URL.fullmatch(target.strip()):
            raise UnsafeOutput(f"<style> refers to something outside the picture: url({target[:40]})")


def check_svg(svg: str, *, extra_elements: frozenset[str] = frozenset()) -> str:
    """Return ``svg`` unchanged when it is only drawing; raise `UnsafeOutput` otherwise.

    ``extra_elements`` are element names a tool's profile adds to the allowlist (for example ``text`` and ``style``
    for a diagram); `ValueError` if one of them is in `NEVER_ALLOWED`.
    """
    forbidden = extra_elements & NEVER_ALLOWED
    if forbidden:
        raise ValueError(f"<{sorted(forbidden)[0]}> is never allowed in a picture, whatever the profile says")
    allowed = _ELEMENTS | extra_elements
    if re.search(r"<!DOCTYPE|<!ENTITY", svg, re.IGNORECASE):
        raise UnsafeOutput("the picture has a DOCTYPE, which can expand entities without end")
    try:
        root = ET.fromstring(svg)  # noqa: S314 - no DTD, so no entities to expand
    except ET.ParseError as error:
        raise UnsafeOutput(f"the picture is not valid XML ({error})") from error
    if root.tag != f"{{{SVG_NS}}}svg":
        raise UnsafeOutput(f"the root is {root.tag!r}, not an svg")
    for element in root.iter():
        if not isinstance(element.tag, str) or not element.tag.startswith(f"{{{SVG_NS}}}"):
            raise UnsafeOutput(f"the element {element.tag!r} is not part of SVG")
        name = _local(element.tag)
        if name not in allowed:
            raise UnsafeOutput(f"<{name}> is not allowed in a typeset picture")
        if name == "style":
            _check_style_text(element)
        for attribute, value in element.attrib.items():
            _check_attribute(name, attribute, value)
    return svg
