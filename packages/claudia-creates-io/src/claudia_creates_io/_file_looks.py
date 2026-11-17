"""How the objects of a file look, as styles of the model (IEW-20, D467).

A file says what a box or a line of words looks like (a fill, an outline, a colour, a size) in styles of its own. The
model has styles too, so the look of a file's object is read into one: the converters read the few properties the model
has (``fill``, ``stroke``, ``stroke-width``, ``color``, ``font-size``, ``font-weight``, ``font-style``,
``text-align``, ``font-family``) as CSS and hand them to a :class:`LookBook`, which makes a style for each look the
deck has -- once, however many objects share it -- based on the built-in style of the object's kind, so what the file
did not say stays what Claudia's own objects have. A fresh export of the deck then writes the same colours and sizes
the file had, and an edit patched onto the file is measured against the same model.

A property that cannot be read (a gradient, a font that is not a name, a size in a unit the converter does not know)
is left out and is the reader's to report as ``look``."""

from __future__ import annotations

from dataclasses import dataclass, field

from claudia_core import CssError, StyleDef, validate_css
from claudia_creates import SlideModel

from ._styling import colour_of, look, page_colour, points_of, written_family


@dataclass
class Look:
    """What an object looks like as properties of the model's styles: its outline's (a shape's) and its words'; and
    whether the file says more than that."""

    outline: dict[str, str] = field(default_factory=dict)
    words: dict[str, str] = field(default_factory=dict)
    unread: bool = False


_COLOURS = ("fill", "stroke", "color")
_SIZES = ("font-size", "stroke-width")


class LookBook:
    """The styles a file's looks became, in ``model``: each one made once, named for the person who will find it in the
    Format menu."""

    def __init__(self, model: SlideModel) -> None:
        self._model = model
        self._styles = model.styles
        self._made: dict[tuple[str, str, tuple[tuple[str, str], ...]], str] = {}

    def outline(self, base: str, css: dict[str, str]) -> str:
        """The id of the outline style that is ``base`` with ``css`` over it (``base`` when ``css`` is empty)."""
        return self._style("outline", "Imported outline", "an outline as the file drew it", base, css)

    def words(self, base: str, css: dict[str, str]) -> str:
        """The id of the paragraph style that is ``base`` with ``css`` over it (``base`` when ``css`` is empty)."""
        return self._style("paragraph", "Imported words", "words as the file set them", base, css)

    def _style(self, kind: str, name: str, purpose: str, base: str, css: dict[str, str]) -> str:
        clean = self._new(base, _clean(css))
        if not clean:
            return base
        key = (kind, base, tuple(sorted(clean.items())))
        found = self._made.get(key)
        if found is not None:
            return found
        number = 1 + sum(1 for style in self._styles if style.id.startswith(f"file-{kind}-"))
        style_id = f"file-{kind}-{number}"
        self._styles.add(StyleDef(style_id, f"{name} {number}", purpose, base, clean, kind=kind))
        self._made[key] = style_id
        return style_id

    def _new(self, base: str, css: dict[str, str]) -> dict[str, str]:
        """What ``css`` says that ``base`` does not already look like. A file that Claudia wrote says everything its
        styles say (the fill, the size), and reading that back must not make a style of every object."""
        have = look(self._model, base)
        page = page_colour(self._model)
        return {prop: value for prop, value in css.items() if not _same(prop, value, have, page)}


def _same(prop: str, value: str, have: dict[str, str], page: str | None) -> bool:
    """Does the resolved style ``have`` already say ``value`` for ``prop``?"""
    if prop not in have:
        return False
    if prop in _COLOURS:
        return colour_of(have, prop, page) == colour_of({prop: value}, prop)
    if prop in _SIZES:
        mine, theirs = points_of(have, prop, 1.0), points_of({prop: value}, prop, 1.0)
        return mine is not None and theirs is not None and abs(mine - theirs) < 0.3
    if prop == "font-family":
        return (written_family(have) or "") == (written_family({prop: value}) or "")
    return have[prop] == value


def _clean(css: dict[str, str]) -> dict[str, str]:
    """``css`` as the model accepts it: a value it refuses is left out, the rest stays."""
    clean: dict[str, str] = {}
    for prop, value in css.items():
        try:
            clean.update(validate_css({prop: value}))
        except CssError:
            continue
    return clean
