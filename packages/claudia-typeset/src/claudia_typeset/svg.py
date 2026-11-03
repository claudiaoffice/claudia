"""Checking an SVG that a converter made from a PDF before it is stored and shown to other people (E3.4, D66).

The converter is trusted, the document that went into it is not: a PDF can carry links and
embedded content. The check is an allowlist of drawing elements, never a blacklist of bad ones,
and it refuses anything that could run code or fetch something from outside.
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


def check_svg(svg: str) -> str:
    """Return ``svg`` unchanged when it is only drawing; raise `UnsafeOutput` otherwise."""
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
        if name not in _ELEMENTS:
            raise UnsafeOutput(f"<{name}> is not allowed in a typeset picture")
        for attribute, value in element.attrib.items():
            _check_attribute(name, attribute, value)
    return svg
