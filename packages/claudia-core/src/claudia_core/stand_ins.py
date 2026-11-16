"""What a document is shown with when it names a generic family or a font the server lacks (E3.13, D905).

This module is the one source of these facts for every client: the font each CSS generic family stands for
(:data:`GENERIC_FONTS`), the names CSS uses for one (:data:`GENERIC_ALIASES`) and the open fonts that take exactly the
room of a common office font (:data:`SAME_WIDTHS`). ``claudia_fonts`` builds its catalogue's stand-ins on them, the
server sends them to clients (``GET /api/fonts``), and the layout library gets a generated copy
(``scripts/generate_font_stand_ins.py``; a test fails when it is stale).

An office file can only name a font, not a generic family, so an export names the font a style is shown with when the
style starts with a generic family (:func:`file_font`); otherwise it names the font the style asks for, and the stand-in
stays out of the file (CODE-42).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType

#: A font name CSS takes without quotes; any other is quoted (one with a space, a digit first, other letters).
_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9-]*")

GENERIC_FONTS: Mapping[str, str] = MappingProxyType(
    {
        "serif": "Fraunces",
        "sans-serif": "Inter",
        "monospace": "JetBrains Mono",
        "fallback": "Inter",
    }
)
"""The font of each CSS generic family (``serif``, ``sans-serif``, ``monospace``) and of the last resort
(``fallback``): the suite's own fonts."""

GENERIC_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "serif": "serif",
        "sans-serif": "sans-serif",
        "monospace": "monospace",
        "system-ui": "sans-serif",
        "ui-sans-serif": "sans-serif",
        "ui-serif": "serif",
        "ui-monospace": "monospace",
        "cursive": "serif",
        "fantasy": "serif",
    }
)
"""Every name CSS uses for a generic family (``system-ui``, ``ui-monospace``, ``cursive`` ...), lower case, by the one
of ``serif``, ``sans-serif`` and ``monospace`` it is shown as."""

SAME_WIDTHS: Mapping[str, str] = MappingProxyType(
    {
        "Arial": "Arimo",
        "Helvetica": "Arimo",
        "Liberation Sans": "Arimo",
        "Times New Roman": "Tinos",
        "Times": "Tinos",
        "Liberation Serif": "Tinos",
        "Courier New": "Cousine",
        "Courier": "Cousine",
        "Liberation Mono": "Cousine",
        "Calibri": "Carlito",
        "Cambria": "Caladea",
        "Georgia": "Gelasio",
    }
)
"""Open fonts that take exactly the room of a common office font, by the office font (``Arial`` → ``Arimo``), so lines
and pages break as in the original. Every one of them is in ``claudia_fonts``' shipped starter set (a test there
checks it); a font is only stood in for when the server does not have it."""


SERIF_FONTS: frozenset[str] = frozenset(
    {
        "cambria",
        "times new roman",
        "times",
        "georgia",
        "garamond",
        "book antiqua",
        "liberation serif",
        "caladea",
        "tinos",
    }
)
"""Office fonts with serifs, lower case: the generic family :func:`css_family` gives them is ``serif``."""

MONOSPACE_FONTS: frozenset[str] = frozenset(
    {"courier new", "courier", "consolas", "lucida console", "liberation mono", "dejavu sans mono", "cousine"}
)
"""Office fonts whose letters all take the same room, lower case: their generic family is ``monospace``."""


def css_family(name: str) -> str:
    """The CSS ``font-family`` for a font a file names (E3.13): the name, quoted unless it is a plain word, then its
    generic family (``Times New Roman`` → ``'Times New Roman', serif``). The stand-in for a font the server lacks is
    not written here: it is chosen where the document is shown, so a document keeps asking for the font its file
    asked for."""
    plain = name.strip().strip("'\"").strip()
    low = plain.casefold()
    generic = "serif" if low in SERIF_FONTS else "monospace" if low in MONOSPACE_FONTS else "sans-serif"
    named = plain if _IDENTIFIER.fullmatch(plain) else f"'{plain}'"
    return f"{named}, {generic}"


def generic_font(name: str) -> str | None:
    """The font a generic family name (any case) is shown with; ``None`` for a name that is not one."""
    family = GENERIC_ALIASES.get(name.strip().casefold())
    return GENERIC_FONTS[family] if family else None


def file_font(css_family: str) -> str | None:
    """The font an office file names for a CSS ``font-family`` list: its first family, unquoted, or the font a generic
    family is shown with when it starts with one. ``None`` for a list that names nothing."""
    for part in css_family.split(","):
        name = part.strip().strip("'\"").strip()
        if name:
            return generic_font(name) or name
    return None
