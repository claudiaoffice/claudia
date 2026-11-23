"""A theme: styles and colours that can exist outside a document (E10.4, E10.23, D1531).

A template carries one, and a document may be given one. :func:`theme_commands` says what giving it to a document
comes to, as commands with final values, so that one Undo takes it all back and nobody consults the theme again. It
only changes how things look: the structure of the document's own styles (what they are based on, their heading levels,
their numbering) stays, and nothing the document has of its own is taken away.

* A built-in style is matched with the style of the document that has the same id: that is what it is for, whatever
  it is called in the language of the person. Any other style is matched by its name, in any letters.
* A matched style gets the CSS of the theme's. A style only the theme has is added, as a style of the template.
* A colour role of the theme replaces the document's role with the same id; a role only the theme has is added, and a
  role only the document has stays, because styles of its own may use it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .commands import Command
from .palette import ColourRole, Palette, ReplacePalette
from .styles import ChangeStyle, CreateStyle, StyleBook, StyleDef


@dataclass(frozen=True)
class Theme:
    """A named set of styles together with the palette they refer to."""

    name: str
    styles: StyleBook
    palette: Palette


def theme_commands(styles: StyleBook, palette: Palette, theme: Theme) -> tuple[Command, ...]:
    """What to do to a document with these ``styles`` and ``palette`` so that it looks as ``theme`` says: the palette
    first, then the styles. Nothing, as a tuple, when it looks like that already."""
    steps: list[Command] = []
    roles = _roles(palette, theme.palette)
    if roles != tuple(palette):
        steps.append(ReplacePalette(roles))
    became: dict[str, str] = {}  # the id of a style of the theme -> the id of the style of the document it became
    taken: set[str] = set()
    for given in theme.styles:
        if (mine := _matching(styles, given)) is not None:
            became[given.id] = mine.id
            if step := _look_of(mine, given):
                steps.append(step)
            continue
        new_id = _free_id(styles, taken, given.id)
        taken.add(new_id)
        became[given.id] = new_id
        parent = became.get(given.based_on) if given.based_on else None
        steps.append(CreateStyle(replace(given, id=new_id, based_on=parent, origin="template", numbering=None)))
    return tuple(steps)


def _roles(mine: Palette, theirs: Palette) -> tuple[ColourRole, ...]:
    given = {role.id: role for role in theirs}
    kept = [given.get(role.id, role) for role in mine]
    return (*kept, *(role for role in theirs if role.id not in mine))


def _matching(styles: StyleBook, given: StyleDef) -> StyleDef | None:
    if given.origin == "builtin" and given.id in styles:
        found = styles.get(given.id)
        return found if found.kind == given.kind else None
    wanted = " ".join(given.name.split()).casefold()
    return next((s for s in styles if s.kind == given.kind and " ".join(s.name.split()).casefold() == wanted), None)


def _look_of(mine: StyleDef, given: StyleDef) -> ChangeStyle | None:
    changed = {name: value for name, value in given.css.items() if mine.css.get(name) != value}
    gone = tuple(name for name in mine.css if name not in given.css)
    return ChangeStyle(mine.id, changed, gone) if changed or gone else None


def _free_id(styles: StyleBook, taken: set[str], wanted: str) -> str:
    number, candidate = 1, wanted
    while candidate in styles or candidate in taken:
        number += 1
        candidate = f"{wanted}-{number}"
    return candidate
