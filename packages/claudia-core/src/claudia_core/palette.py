"""The document's palette: colours named by what they *mean* (E1.10, D200, D201, D202).

A style says what a piece of text or a shape is **for** — a heading, a caption, a plain shape — and holds the CSS in
which it differs from its parent. A palette is the same idea one axis over: a *role* says what a colour means, and
everything that means the same thing shares it. Change ``accent`` once and every style that pointed at it follows,
across all three apps, because colour cuts across styles in a way :class:`~claudia_core.StyleBook` cannot express on
its own: one accent can be a shape's ``fill``, another style's border and a heading's ``color``.

A style names a role as ``@accent``, or ``@accent/55`` for that role at 55% opacity (see ``claudia_core.css``). The
token never reaches a browser: ``resolve_css`` turns it into a literal colour on the way out, which is what lets the
allow-list keep refusing ``var()`` and ``calc()`` outright.

The palette is part of the document, not of the server or the client, so a document looks the same wherever it is
opened (D200). It is changed only by the commands below, so every change is in the log, can be undone, and is seen by
everybody.

Roles are a set that will grow
------------------------------
:data:`claudia_core.BUILTIN_ROLES` is the nine roles a new document starts with, and the apps' built-in styles are
written entirely in terms of them — a fresh document holds no literal colour anywhere, so replacing its palette
really does recolour it. The container is a general, ordered mapping all the same: :class:`Palette` can hold any role
a document cares to define, and ``ReplacePalette`` can bring a different set. What is deliberately *not* here yet is
a command for a person to add one role of their own; that waits for the menu that would offer it.

Contrast
--------
:data:`claudia_core.PAIRINGS` says which roles are read *against* which, and the floor each pairing has to clear:
4.5:1 where it is words and 3:1 where it is a border or a rule, the same WCAG figures the suite's own tokens are
built on. :meth:`claudia_core.Palette.readings` works the ratios out. Nothing here prevents anything — a person may
set any colour they like, and is told in plain words what it will cost (D202).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar

from .commands import Command, CommandRegistry, core_commands
from .css import rgb_of, roles_used
from .styles import StylesChanged, palette_colours

if TYPE_CHECKING:
    from .context import Context

_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_MAX_NAME = 60
_MAX_PURPOSE = 200

#: A document may not hold more roles than this. Generous: a palette is a vocabulary, not a colour picker.
MAX_ROLES = 64

#: The contrast a pairing of roles has to reach: words need more than a border does (WCAG 2.2, AA).
TEXT_FLOOR = 4.5
UI_FLOOR = 3.0


@dataclass(frozen=True)
class ColourRole:
    """One role: an id a style names (``@accent``), a name and a purpose for the person, and one definite colour.

    The colour is hexadecimal on purpose. A role is a single colour so that opacity (``@accent/55``) and contrast can
    both be worked out from it exactly; a translucent or named colour would make both approximate.
    """

    id: str
    name: str
    purpose: str
    colour: str

    def to_data(self) -> dict:
        """The plain-data form that goes into snapshots and commands."""
        return {"id": self.id, "name": self.name, "purpose": self.purpose, "colour": self.colour}

    @classmethod
    def from_data(cls, data: dict) -> ColourRole:
        """Inverse of ``to_data``."""
        return cls(data["id"], data["name"], data["purpose"], data["colour"])


@dataclass(frozen=True)
class Reading:
    """How one role reads against another: the ratio, the floor it had to clear, and whether it did."""

    foreground: str
    background: str
    ratio: float
    floor: float

    @property
    def ok(self) -> bool:
        """Does this pairing clear its floor?"""
        return self.ratio >= self.floor

    @property
    def words(self) -> bool:
        """Is this pairing about words, which need a ratio of 4.5, rather than a border or a rule, which need 3?"""
        return self.floor >= TEXT_FLOOR

    def to_data(self) -> dict:
        """The plain-data form of the reading, as sent to clients.

        No verdict text: a client says what it means in its own words and its own language, and never shows the
        ratio — a figure tells a reader nothing about whether they can read the page (D202).
        """
        return {
            "foreground": self.foreground,
            "background": self.background,
            "ratio": round(self.ratio, 2),
            "floor": self.floor,
            "ok": self.ok,
            "words": self.words,
        }


#: The roles a new document has. Nine, because the apps' own built-in styles need nine to say what they already say:
#: three distinct accents (iris, rose, apricot) carry different meanings in composes and flattening them would lose a
#: distinction the design has today.
#: The colours are the suite's own (ink, paper, iris, rose, apricot), not new ones, so that writing the built-in
#: styles in terms of roles changed what they *mean* and not what they look like. A document that was opened
#: yesterday is the same colour today.
BUILTIN_ROLES: tuple[ColourRole, ...] = (
    ColourRole("text", "Text", "the words you read", "#1F1A33"),
    ColourRole("muted", "Muted", "captions and secondary words", "#6B6578"),
    ColourRole("page", "Page", "the page, slide or sheet itself", "#F7F3EC"),
    ColourRole("surface", "Surface", "the fill of a box or a shape", "#FFFFFF"),
    ColourRole("structure", "Structure", "borders, rules and dividers", "#8A82A0"),
    ColourRole("accent", "Accent", "the one thing to notice", "#5B4BC4"),
    ColourRole("accent-text", "Accent text", "words on top of the accent", "#FFFFFF"),
    ColourRole("attention", "Attention", "something addressed to the reader", "#D6477A"),
    ColourRole("highlight", "Highlight", "a passage set apart from the rest", "#F2A057"),
)

#: Which roles are read against which, and the floor each has to clear. A role with no pairing is simply not checked,
#: which is what lets a document define roles this table has never heard of.
#:
#: ``attention`` and ``highlight`` are deliberately absent. They are decorative in the built-in styles — the bar down
#: the side of a Remark, of a Quote — and WCAG's 3:1 is for what a reader must be able to make out to use or
#: understand the page, not for an ornament. Pairing them anyway would have had a brand-new document report its own
#: Highlight as too faint (apricot on paper is 1.99:1), which is how a warning teaches people to ignore warnings. The
#: day either role carries words or a boundary, it gets a pairing here and the check comes with it.
PAIRINGS: tuple[tuple[str, str, float], ...] = (
    ("text", "page", TEXT_FLOOR),
    ("text", "surface", TEXT_FLOOR),
    ("muted", "page", TEXT_FLOOR),
    ("muted", "surface", TEXT_FLOOR),
    ("accent-text", "accent", TEXT_FLOOR),
    ("structure", "page", UI_FLOOR),
    ("structure", "surface", UI_FLOOR),
    ("accent", "page", UI_FLOOR),
    ("accent", "surface", UI_FLOOR),
)


def luminance(colour: str) -> float:
    """The relative luminance of a hexadecimal colour (WCAG 2.2), between 0 for black and 1 for white."""
    channels = [value / 255 for value in rgb_of(colour)]
    linear = [value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(one: str, other: str) -> float:
    """The contrast ratio between two hexadecimal colours (WCAG 2.2): 1 for the same colour, 21 at most."""
    first, second = luminance(one), luminance(other)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def _clean_name(name: str) -> str:
    text = " ".join(name.split()) if "\n" not in name and "\r" not in name else ""
    if not text or len(text) > _MAX_NAME or not text.isprintable():
        raise ValueError(f"A role name is one line of 1 to {_MAX_NAME} characters, got {name!r}")
    return text


class Palette:
    """The colour roles of a document, in the order they were defined."""

    def __init__(self, roles: Iterable[ColourRole] = ()):
        self._roles: dict[str, ColourRole] = {}
        for role in roles:
            self.add(role)

    # -- reading -----------------------------------------------------------------
    def __contains__(self, role_id: object) -> bool:
        return role_id in self._roles

    def __iter__(self) -> Iterator[ColourRole]:
        return iter(list(self._roles.values()))

    def __len__(self) -> int:
        return len(self._roles)

    def ids(self) -> list[str]:
        """The ids of all roles, in order."""
        return list(self._roles)

    def get(self, role_id: str) -> ColourRole:
        """The role with this id; ``KeyError`` if there is none."""
        try:
            return self._roles[role_id]
        except KeyError:
            raise KeyError(f"no colour role {role_id!r}") from None

    def colours(self) -> dict[str, str]:
        """Role id to literal colour — what ``resolve_css`` needs. A new dictionary."""
        return {role.id: role.colour for role in self._roles.values()}

    def readings(self) -> list[Reading]:
        """How the roles read against each other, for every pairing both of whose roles this palette has."""
        return [
            Reading(fore, back, contrast(self._roles[fore].colour, self._roles[back].colour), floor)
            for fore, back, floor in PAIRINGS
            if fore in self._roles and back in self._roles
        ]

    def missing_from(self, css: Mapping[str, str]) -> set[str]:
        """The roles this CSS names that the palette does not have."""
        return roles_used(css) - set(self._roles)

    def views(self) -> list[dict]:
        """Every role as sent to clients. The readings travel beside them, from :meth:`readings`."""
        return [role.to_data() for role in self._roles.values()]

    def to_data(self) -> list[dict]:
        """The palette as plain data (for snapshots); ``from_data`` is the inverse."""
        return [role.to_data() for role in self._roles.values()]

    @classmethod
    def from_data(cls, items: Iterable[dict]) -> Palette:
        """Build a palette from ``to_data``'s output."""
        return cls(ColourRole.from_data(item) for item in items)

    # -- changing (used by the commands) -----------------------------------------
    def add(self, role: ColourRole) -> None:
        """Define a role: a new id and name, and a colour that is hexadecimal. Stores the cleaned role."""
        if not _ID.fullmatch(role.id):
            raise ValueError(f"A role id is lower-case letters, digits and hyphens (up to 40), got {role.id!r}")
        if role.id in self._roles:
            raise ValueError(f"The colour role {role.id!r} exists already")
        if len(self._roles) >= MAX_ROLES:
            raise ValueError(f"A palette holds at most {MAX_ROLES} colour roles")
        name = _clean_name(role.name)
        if any(other.name.casefold() == name.casefold() for other in self._roles.values()):
            raise ValueError(f"There is already a colour role named “{name}”")
        if len(role.purpose) > _MAX_PURPOSE or "\n" in role.purpose:
            raise ValueError(f"The purpose of a colour role is one line of up to {_MAX_PURPOSE} characters")
        self._roles[role.id] = replace(role, name=name, colour=_clean_colour(role.colour))

    def set_colour(self, role_id: str, colour: str) -> None:
        """Give a role another colour. Everything that means this role changes with it."""
        self._roles[role_id] = replace(self.get(role_id), colour=_clean_colour(colour))

    def remove(self, role_id: str) -> ColourRole:
        """Take a role out of the palette and return it."""
        self.get(role_id)  # so that an unknown id says so, rather than popping nothing
        return self._roles.pop(role_id)

    def replace_all(self, roles: Iterable[ColourRole]) -> None:
        """Put these roles in place of every role the palette has — or, if any of them is refused, change nothing.

        The replacement is built as a whole palette first, so a bad role in the middle of a new set cannot leave this
        one half-replaced. A command has to be able to fail without changing anything (E1.3).
        """
        fresh = Palette(roles)
        self._roles = fresh._roles


def _clean_colour(colour: str) -> str:
    """``colour`` as ``#rrggbb`` in upper case; ``ValueError`` if it is not hexadecimal."""
    red, green, blue = rgb_of(colour)
    return f"#{red:02X}{green:02X}{blue:02X}"


def builtin_palette() -> Palette:
    """A new palette with the roles every document starts with."""
    return Palette(BUILTIN_ROLES)


@dataclass(frozen=True)
class PaletteChanged:
    """The palette of the document changed: the whole of it, which is small, and every style follows from it."""

    roles: tuple[dict, ...]
    readings: tuple[dict, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "palette", "roles": list(self.roles), "readings": list(self.readings)}


# --------------------------------------------------------------------------- commands
def _palette(ctx: Context) -> Palette:
    palette = getattr(ctx.model, "palette", None)
    if not isinstance(palette, Palette):
        raise TypeError(f"The {ctx.model.app} model has no palette, so it cannot use palette commands")
    return palette


def _tell(ctx: Context, palette: Palette) -> None:
    """Tell the clients the new palette — and the styles with it.

    Every style's ``resolved`` CSS is now different, and a client is deliberately not able to work that out for
    itself: the role grammar lives here so that what reaches a browser is always a literal colour (D200). So the
    styles travel again, exactly as they do when a parent style changes and its children follow.
    """
    ctx.emit(PaletteChanged(tuple(palette.views()), tuple(r.to_data() for r in palette.readings())))
    book = getattr(ctx.model, "styles", None)
    if book is not None:
        ctx.emit(StylesChanged(tuple(book.views(palette_colours(ctx.model)))))


def _styles_still_fit(ctx: Context, palette: Palette) -> None:
    """Refuse a palette that a style of this document already points past.

    Dropping a role a style names would not corrupt anything — ``resolve_css`` leaves such a declaration out and the
    parent's value shows through — but it would change how the document looks without saying so, which is exactly
    what a palette is supposed to prevent.
    """
    book = getattr(ctx.model, "styles", None)
    if book is None:
        return
    for style in book:
        missing = palette.missing_from(style.css)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"The style “{style.name}” uses the colour role(s) {names}, which this palette has not")


@core_commands.register
@dataclass(frozen=True)
class SetRole(Command):
    """Give one colour role another colour. Everything in the document that meant that role changes with it."""

    kind: ClassVar[str] = "core.SetRole"
    role: str
    colour: str

    @property
    def label(self) -> str:
        return "Change colour"

    @property
    def summary(self) -> str:
        return f"set the colour {self.role} to {self.colour}"

    def apply(self, ctx: Context) -> Command:
        palette = _palette(ctx)
        try:
            was = palette.get(self.role)
        except KeyError as exc:
            raise ValueError(exc.args[0]) from None
        palette.set_colour(self.role, self.colour)
        _tell(ctx, palette)
        return SetRole(self.role, was.colour)

    def to_data(self) -> dict:
        return {"role": self.role, "colour": self.colour}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetRole:
        return cls(data["role"], data["colour"])

    def shifted_by(self, other: Command) -> Command | None:
        touched = (isinstance(other, SetRole) and other.role == self.role) or isinstance(other, ReplacePalette)
        return None if touched else self


@core_commands.register
@dataclass(frozen=True)
class ReplacePalette(Command):
    """Put a whole palette in place of the one the document has — what "replace palette" offers, and what a template
    will bring with it. Refused while a style of this document names a role the new palette does not have."""

    kind: ClassVar[str] = "core.ReplacePalette"
    roles: tuple[ColourRole, ...]

    @property
    def label(self) -> str:
        return "Replace palette"

    @property
    def summary(self) -> str:
        return f"replaced the palette ({len(self.roles)} colours)"

    def apply(self, ctx: Context) -> Command:
        palette = _palette(ctx)
        was = tuple(palette)
        _styles_still_fit(ctx, Palette(self.roles))
        palette.replace_all(self.roles)
        _tell(ctx, palette)
        return ReplacePalette(was)

    def to_data(self) -> dict:
        return {"roles": [role.to_data() for role in self.roles]}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> ReplacePalette:
        return cls(tuple(ColourRole.from_data(item) for item in data["roles"]))

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, SetRole | ReplacePalette) else self
