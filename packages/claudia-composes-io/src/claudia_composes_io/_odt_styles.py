"""The styles of a text as odt styles: the look of every paragraph style of the model, written with the palette's
colours (D455).

A style of the model is CSS (:mod:`claudia_core.css`) that names palette roles; a file has neither. Each paragraph style
becomes a ``style:style`` of the paragraph family whose properties are the look of its own CSS
(:func:`~claudia_composes_io._style_look.look_of`) and which is based on the style the model bases it on. The built-in
styles keep the names that other programs know them by (``Standard``, ``Title``, ``Heading 1``...); the others are named
by their name. What a file cannot say of a style is returned with it, so that it can be reported."""

from __future__ import annotations

from collections.abc import Collection
from xml.sax.saxutils import quoteattr

from claudia_core import StyleBook, StyleDef
from claudia_odf_io import NS, encode_style_name

from ._style_look import Look, look_for

#: The built-in styles by the name that an OpenDocument program has for them.
BUILTIN_NAMES = {
    "body": "Standard",
    "title": "Title",
    "heading-1": "Heading_20_1",
    "heading-2": "Heading_20_2",
    "quote": "Quotations",
}
#: What a style of those is for a program: its class, the style the next paragraph has, and whether it is a heading.
_STRUCTURE = {
    "Standard": ' style:class="text"',
    "Title": ' style:next-style-name="Standard" style:class="chapter"',
    "Heading_20_1": ' style:next-style-name="Standard" style:default-outline-level="1" style:class="text"',
    "Heading_20_2": ' style:next-style-name="Standard" style:default-outline-level="2" style:class="text"',
    "Quotations": ' style:class="html"',
}
_SIDES = ("top", "right", "bottom", "left")
_KEEP_WITH_NEXT = ("Heading_20_1", "Heading_20_2")
_DECLARED = " ".join(f'xmlns:{prefix}="{NS[prefix]}"' for prefix in ("style", "fo", "text"))


def _pt(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") + "pt"


class StyleNames:
    """The odt name of each paragraph style of a book: the built-in ones by their well-known name, the others by their
    own name made safe for a file, and never two the same."""

    def __init__(self, book: StyleBook, taken: Collection[str] = ()) -> None:
        """``taken`` are names that a style of the book may not have besides the built-in ones: the names of the
        styles a file already has, when the book is written into it."""
        self.book = book
        self._names: dict[str, str] = {}
        taken = {*BUILTIN_NAMES.values(), *taken}
        for style in book:
            if style.kind != "paragraph":
                continue
            if style.id in BUILTIN_NAMES:
                self._names[style.id] = BUILTIN_NAMES[style.id]
                continue
            base = candidate = encode_style_name(style.name) or "Style"
            number = 1
            while candidate in taken:
                number += 1
                candidate = f"{base}_{number}"
            taken.add(candidate)
            self._names[style.id] = candidate

    def __contains__(self, style_id: object) -> bool:
        return style_id in self._names

    def of(self, style_id: str) -> str:
        """The name of the style, or ``Standard`` for one the book does not have."""
        return self._names.get(style_id, BUILTIN_NAMES["body"])


def style_xml(book: StyleBook, style: StyleDef, names: StyleNames, colours: dict[str, str]) -> tuple[bytes, list[str]]:
    """The ``style:style`` of ``style`` and the properties it sets that a file cannot say."""
    look = look_for(book, style.id, colours)
    name = names.of(style.id)
    parent = f" style:parent-style-name={quoteattr(names.of(style.based_on))}" if style.based_on else ""
    display = f" style:display-name={quoteattr(style.name)}" if encode_style_name(style.name) != name else ""
    head = f'style:name={quoteattr(name)}{display} style:family="paragraph"{parent}{_STRUCTURE.get(name, "")}'
    paragraph, text = _paragraph_properties(look, name), _text_properties(look)
    body = (f"<style:paragraph-properties{paragraph}/>" if paragraph else "") + (
        f"<style:text-properties{text}/>" if text else ""
    )
    return f"<style:style {_DECLARED} {head}>{body}</style:style>".encode(), look.unsaid


def _paragraph_properties(look: Look, name: str) -> str:
    said: list[tuple[str, str]] = []
    said += [(f"fo:margin-{side}", _pt(look.margins[side])) for side in _SIDES if side in look.margins]
    if look.align is not None:
        said.append(("fo:text-align", look.align))
    if look.line is not None:
        said.append(("fo:line-height", _pt(look.line) if look.line_fixed else f"{look.line * 100:.0f}%"))
    if look.hyphenate is not None:
        said.append(("fo:hyphenate", "true" if look.hyphenate else "false"))
    if look.background is not None:
        said.append(("fo:background-color", look.background))
    for side, border in look.borders.items():
        said.append(
            (f"fo:border-{side}", "none" if border is None else f"{_pt(border.width)} {border.line} {border.colour}")
        )
    for side, value in look.padding.items():
        said.append((f"fo:padding-{side}", _pt(value)))
    if name in _KEEP_WITH_NEXT:
        said.append(("fo:keep-with-next", "always"))
    return "".join(f" {key}={quoteattr(value)}" for key, value in said)


def _text_properties(look: Look) -> str:
    said: list[tuple[str, str]] = []
    if look.family is not None:
        said.append(("fo:font-family", look.family))
    if look.size is not None:
        said.append(("fo:font-size", _pt(look.size)))
    if look.weight is not None:
        said.append(("fo:font-weight", {400: "normal", 700: "bold"}.get(look.weight, str(look.weight))))
    if look.italic is not None:
        said.append(("fo:font-style", "italic" if look.italic else "normal"))
    if look.colour is not None:
        said.append(("fo:color", look.colour))
    if look.spacing is not None:
        said.append(("fo:letter-spacing", _pt(look.spacing)))
    if look.underline is not None:
        said.extend(
            [
                ("style:text-underline-style", "solid"),
                ("style:text-underline-width", "auto"),
                ("style:text-underline-color", "font-color"),
            ]
            if look.underline
            else [("style:text-underline-style", "none")]
        )
    if look.strike is not None:
        said.append(("style:text-line-through-style", "solid" if look.strike else "none"))
    return "".join(f" {key}={quoteattr(value)}" for key, value in said)
