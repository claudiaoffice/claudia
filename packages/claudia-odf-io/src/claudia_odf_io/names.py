"""Names in OpenDocument: the namespaces every part uses, and how a style's name is spelled (D401)."""

from __future__ import annotations

import re

#: The namespaces of ODF 1.3 that this layer touches, by the prefixes producers use for them (LibreOffice, Apache
#: OpenOffice and odfdo all write these same ones, but a file may bind another prefix to a URI: code that reads a
#: file goes by the URI, never by the prefix).
NS: dict[str, str] = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "presentation": "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "number": "urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xml": "http://www.w3.org/XML/1998/namespace",
}

_ESCAPE = re.compile(r"_(?:x)?([0-9A-Fa-f]{2,6})_")


def qname(prefixed: str) -> str:
    """``"text:p"`` as the Clark name ``{uri}p`` that lxml uses. ``KeyError`` for a prefix this layer does not know."""
    prefix, _, name = prefixed.partition(":")
    return f"{{{NS[prefix]}}}{name}"


def local_name(tag: str) -> str:
    """The name without its namespace, from a Clark name (or from a plain name, unchanged)."""
    return tag.rpartition("}")[2]


def _plain(char: str, position: int) -> bool:
    """Whether ``char`` may stand as it is in a style name (an XML name without the underscore, which the escape
    uses): a letter anywhere, a digit, a dot or a hyphen anywhere but first."""
    return char.isalpha() or (position > 0 and (char.isdigit() or char in ".-"))


def encode_style_name(display_name: str) -> str:
    """A style's ``style:name`` for its display name, the way LibreOffice spells it: a character an XML name cannot
    hold becomes its code point in hex between underscores (``Heading 1`` is ``Heading_20_1``). The display name
    itself goes in ``style:display-name``; the encoded one is what a paragraph's ``text:style-name`` points at."""
    return "".join(c if _plain(c, i) else f"_{ord(c):02x}_" for i, c in enumerate(display_name))


def decode_style_name(name: str) -> str:
    """The display name a ``style:name`` spells: the inverse of :func:`encode_style_name`. The escape of other
    producers (``_x0020_``) is understood as well; an underscore that is not an escape stays what it was."""
    return _ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), name)
