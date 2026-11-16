"""Named styles: how things look, named by what they are for, written in CSS (E1.10, D62, D73, D75).

A ``StyleDef`` is a name, a sentence about its purpose, an optional parent (``based_on``), a *kind* and the CSS
properties in which it differs from that parent. The kind (``paragraph``, ``box`` or ``outline``) says which facets
of :mod:`claudia_core.facets` the style may hold, and so which slots it can be put into (D303-D305, D312); a style
and its parent are always of the same kind. The look of something is its *computed* style: the chain of parents,
resolved. The ``StyleBook`` is what an app's model holds; the commands below are the only ways to change it, so every
change is in the log, can be undone, and is seen by everybody.

An app's model that wants styles has a ``styles`` attribute (a ``StyleBook``) and may have a method
``style_in_use(style_id) -> bool`` that tells the commands whether anything refers to a style.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar, Literal

from .commands import Command, CommandRegistry, core_commands
from .css import resolve_css, validate_css
from .facets import check_kind

if TYPE_CHECKING:
    from .context import Context

_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_MAX_NAME = 60
_MAX_PURPOSE = 200
_CHANGED = re.compile(r" \(changed(?: \d+)?\)$")

#: The deepest heading level (E9.22): 0 is the document's title, 1 to 9 its sections, subsections and so on.
MAX_HEADING_LEVEL = 9

#: A style's own heading level: ``None`` is "as my parent", ``"body"`` is "no heading, whatever my parent is", and
#: 0 to :data:`MAX_HEADING_LEVEL` is a level (0: the title, which names the document and is never numbered or listed
#: in a table of contents).
type HeadingLevel = int | Literal["body"] | None

#: A style's own numbering that says "not numbered, whatever my parent is" (as ``"body"`` does for the heading level).
#: No list can have this id.
NO_NUMBERING = "none"


def _check_heading_level(style: StyleDef) -> None:
    level = style.heading_level
    if level is None or level == "body":
        pass
    elif not isinstance(level, int) or isinstance(level, bool) or not 0 <= level <= MAX_HEADING_LEVEL:
        raise ValueError(f"A heading level is 0 to {MAX_HEADING_LEVEL} or “body”, got {level!r}")
    if level is not None and style.kind != "paragraph":
        raise ValueError(f"Only a paragraph style can be a heading; “{style.name}” is a {style.kind} style")


def _check_numbering(style: StyleDef) -> None:
    if style.numbering is None:
        return
    if not isinstance(style.numbering, str) or not _ID.fullmatch(style.numbering):
        raise ValueError(f"A style's numbering is the id of a list, got {style.numbering!r}")
    if style.kind != "paragraph":
        raise ValueError(f"Only a paragraph style can be numbered; “{style.name}” is a {style.kind} style")


@dataclass(frozen=True)
class StyleDef:
    """One style: ``css`` holds only what differs from ``based_on``. ``to_name`` marks a style that was made by
    deviating and still has the provisional name it was given (E9.7). ``kind`` says which facets ``css`` may hold
    (:data:`claudia_core.facets.KINDS`); a style written without one is a ``paragraph`` style, which is what text
    has. ``number_format`` names one of the app's number formats (computes, D378): not CSS, but inherited the same
    way -- a style without one shows numbers as its parent does. ``heading_level`` makes the paragraphs that have the
    style headings of a level (E9.22, :data:`HeadingLevel`); it is inherited the same way, so a deviation from a
    heading stays one. It is the one place that decides what a heading is: no app, layout or client keeps a list of
    heading styles. ``numbering`` is the id of a list (:class:`~claudia_core.ListDef`) that numbers the paragraphs of
    a heading style, at the list level below their heading level (heading 1 at the list's first level); ``None`` is
    "as my parent", :data:`NO_NUMBERING` "not numbered"."""

    id: str
    name: str
    purpose: str
    based_on: str | None
    css: dict[str, str]
    to_name: bool = False
    kind: str = "paragraph"
    number_format: str | None = None
    heading_level: HeadingLevel = None
    numbering: str | None = None

    def to_data(self) -> dict:
        """The plain-data form that goes into snapshots and commands; ``number_format``, ``heading_level`` and
        ``numbering`` only when they are set, so a style that has none of them writes exactly what it wrote before."""
        data: dict[str, object] = {
            "id": self.id,
            "name": self.name,
            "purpose": self.purpose,
            "based_on": self.based_on,
            "css": dict(self.css),
            "to_name": self.to_name,
            "kind": self.kind,
        }
        if self.number_format is not None:
            data["number_format"] = self.number_format
        if self.heading_level is not None:
            data["heading_level"] = self.heading_level
        if self.numbering is not None:
            data["numbering"] = self.numbering
        return data

    @classmethod
    def from_data(cls, data: dict) -> StyleDef:
        """Inverse of ``to_data``. Data without a ``kind`` is refused (``KeyError``) rather than guessed at: there
        is no upcast of documents from before kinds existed (D308)."""
        return cls(
            data["id"],
            data["name"],
            data["purpose"],
            data["based_on"],
            dict(data["css"]),
            data["to_name"],
            data["kind"],
            data.get("number_format"),
            data.get("heading_level"),
            data.get("numbering"),
        )


def _clean_name(name: str) -> str:
    text = " ".join(name.split()) if "\n" not in name and "\r" not in name else ""
    if not text or len(text) > _MAX_NAME or not text.isprintable():
        raise ValueError(f"A style name is one line of 1 to {_MAX_NAME} characters, got {name!r}")
    return text


class StyleBook:
    """The styles of a document, in the order they were made (a parent always comes before its children)."""

    def __init__(self, styles: Iterable[StyleDef] = ()):
        self._styles: dict[str, StyleDef] = {}
        #: Counts every change, so that whoever derives something from the book (the numbers of headings) knows to
        #: derive it again.
        self.version = 0
        for style in styles:
            self.add(style)

    # -- reading -----------------------------------------------------------------
    def __contains__(self, style_id: object) -> bool:
        return style_id in self._styles

    def __iter__(self) -> Iterator[StyleDef]:
        return iter(list(self._styles.values()))

    def __len__(self) -> int:
        return len(self._styles)

    def ids(self) -> list[str]:
        """The ids of all styles, in order."""
        return list(self._styles)

    def get(self, style_id: str) -> StyleDef:
        """The style with this id; ``KeyError`` if there is none."""
        try:
            return self._styles[style_id]
        except KeyError:
            raise KeyError(f"no style {style_id!r}") from None

    def chain(self, style_id: str) -> list[StyleDef]:
        """The style and its parents, the root first."""
        found: list[StyleDef] = []
        current: str | None = style_id
        while current is not None:
            if any(s.id == current for s in found):
                raise ValueError(f"the style {current!r} is based on itself")
            style = self.get(current)
            found.insert(0, style)
            current = style.based_on
        return found

    def computed(self, style_id: str) -> dict[str, str]:
        """The CSS the style really has: its parents' properties, overridden by its own. A new dictionary."""
        result: dict[str, str] = {}
        for style in self.chain(style_id):
            result.update(style.css)
        return result

    def number_format(self, style_id: str) -> str | None:
        """The number format a style shows numbers with: its own, else the nearest parent's (D378)."""
        for style in reversed(self.chain(style_id)):
            if style.number_format is not None:
                return style.number_format
        return None

    def heading_level(self, style_id: str) -> int | None:
        """The heading level a style gives a paragraph: its own, else the nearest parent's; ``None`` for no heading
        (no level anywhere in the chain, or ``"body"`` before one is found)."""
        for style in reversed(self.chain(style_id)):
            if style.heading_level == "body":
                return None
            if style.heading_level is not None:
                return style.heading_level
        return None

    def numbering(self, style_id: str) -> str | None:
        """The list a style numbers its paragraphs in: its own, else the nearest parent's; ``None`` for none (no list
        anywhere in the chain, or :data:`NO_NUMBERING` before one is found)."""
        for style in reversed(self.chain(style_id)):
            if style.numbering == NO_NUMBERING:
                return None
            if style.numbering is not None:
                return style.numbering
        return None

    def children(self, style_id: str) -> list[str]:
        """The ids of the styles that are based directly on this one."""
        return [s.id for s in self._styles.values() if s.based_on == style_id]

    def name_taken(self, name: str, *, besides: str | None = None) -> bool:
        """Does another style (not ``besides``) already have this name, in any letters?"""
        wanted = " ".join(name.split()).casefold()
        return any(s.name.casefold() == wanted for s in self._styles.values() if s.id != besides)

    def unique_id(self, base: str) -> str:
        """A free id made from a name (``Heading (changed)`` -> ``heading-changed``, then ``-2``, ``-3``, ...)."""
        ascii_ = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode().lower()
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")[:36].strip("-") or "style"
        candidate, number = slug, 1
        while candidate in self._styles:
            number += 1
            candidate = f"{slug}-{number}"
        return candidate

    def provisional_name(self, parent_id: str) -> str:
        """The name a deviation from ``parent_id`` gets until its maker names it: ``Heading 1 (changed)``."""
        base = _CHANGED.sub("", self.get(parent_id).name)
        candidate, number = f"{base} (changed)", 1
        while self.name_taken(candidate):
            number += 1
            candidate = f"{base} (changed {number})"
        return candidate

    def resolved(self, style_id: str, colours: Mapping[str, str] | None = None) -> dict[str, str]:
        """One style's CSS with its parents taken in *and* its palette roles turned into literal colours (D200).

        What :meth:`computed` gives still names roles (``@accent``), which is right for a style menu and wrong for
        anything that paints: a browser drops a declaration it cannot read, and a file format has nowhere to put
        one. So everything that renders or exports asks for this form, not ``computed``.
        """
        return resolve_css(self.computed(style_id), colours or {})

    def views(self, colours: Mapping[str, str] | None = None) -> list[dict]:
        """Every style as sent to clients: the plain data, the ``computed`` CSS, and the ``resolved`` CSS.

        ``computed`` is the chain of parents resolved, and it still names the palette's roles (``@accent``), which
        is what a style menu shows a person. ``resolved`` is the same again with every role replaced by the literal
        colour ``colours`` gives for it — that is what a client draws with, so the CSS reaching a browser is always
        literal and the allow-list can go on refusing ``var()`` and ``calc()`` outright (D200).

        ``colours`` is the document's palette, as :meth:`claudia_core.Palette.colours` gives it. Without one, a
        declaration that names a role is left out of ``resolved``: a book is not the place to invent a colour.

        ``heading`` is :meth:`heading_level` worked out, so that no client, layout or exporter walks the parents to
        find out whether a paragraph is a heading (E9.22); ``numbered`` is :meth:`numbering` worked out the same way.
        """
        return [
            {
                **style.to_data(),
                "computed": self.computed(style.id),
                "resolved": self.resolved(style.id, colours),
                "heading": self.heading_level(style.id),
                "numbered": self.numbering(style.id),
            }
            for style in self._styles.values()
        ]

    def to_data(self) -> list[dict]:
        """The book as plain data (for snapshots); ``from_data`` is the inverse."""
        return [style.to_data() for style in self._styles.values()]

    @classmethod
    def from_data(cls, items: Iterable[dict]) -> StyleBook:
        """Build a book from ``to_data``'s output."""
        return cls(StyleDef.from_data(item) for item in items)

    # -- changing (used by the commands) -----------------------------------------
    def add(self, style: StyleDef) -> None:
        """Add a style: a new id and name, an existing parent of the same kind, CSS that is allowed and belongs to
        the style's kind. Stores the cleaned CSS."""
        if not _ID.fullmatch(style.id):
            raise ValueError(f"A style id is lower-case letters, digits and hyphens (up to 40), got {style.id!r}")
        if style.id in self._styles:
            raise ValueError(f"The style {style.id!r} exists already")
        name = _clean_name(style.name)
        if self.name_taken(name):
            raise ValueError(f"There is already a style named “{name}”")
        if style.based_on is not None and style.based_on not in self._styles:
            raise ValueError(f"The style {style.id!r} is based on {style.based_on!r}: no style {style.based_on!r}")
        check_kind(style.kind, style.css)
        _check_heading_level(style)
        if style.based_on is not None and (parent := self._styles[style.based_on]).kind != style.kind:
            raise ValueError(
                f"The {style.kind} style {style.id!r} cannot be based on “{parent.name}”, a {parent.kind} style: "
                "a style and its parent are of the same kind"
            )
        if len(style.purpose) > _MAX_PURPOSE or "\n" in style.purpose:
            raise ValueError(f"The purpose of a style is one line of up to {_MAX_PURPOSE} characters")
        _check_numbering(style)
        self._styles[style.id] = replace(style, name=name, css=validate_css(style.css))
        self.version += 1

    def set_css(self, style_id: str, css: dict[str, str]) -> None:
        """Give a style these own properties (instead of what it had); they must belong to its kind."""
        style = self.get(style_id)
        check_kind(style.kind, css)
        self._styles[style_id] = replace(style, css=validate_css(css))
        self.version += 1

    def set_number_format(self, style_id: str, format_id: str | None) -> None:
        """Make a style show numbers through the number format ``format_id`` (``None``: as its parent does). The
        book does not know the formats; the app that has them checks the id (D378)."""
        self._styles[style_id] = replace(self.get(style_id), number_format=format_id)
        self.version += 1

    def set_heading_level(self, style_id: str, level: HeadingLevel) -> None:
        """Give a style its own heading level (``None``: as its parent; ``"body"``: no heading)."""
        changed = replace(self.get(style_id), heading_level=level)
        _check_heading_level(changed)
        self._styles[style_id] = changed
        self.version += 1

    def set_numbering(self, style_id: str, numbering: str | None) -> None:
        """Make a style number its paragraphs in the list ``numbering`` (``None``: as its parent; :data:`NO_NUMBERING`:
        not at all). The book does not hold the lists; the command checks that the list exists."""
        changed = replace(self.get(style_id), numbering=numbering)
        _check_numbering(changed)
        self._styles[style_id] = changed
        self.version += 1

    def rename(self, style_id: str, name: str, *, to_name: bool = False) -> None:
        """Give a style another name that no other style has; ``to_name`` says whether it is still provisional."""
        style = self.get(style_id)
        clean = _clean_name(name)
        if self.name_taken(clean, besides=style_id):
            raise ValueError(f"There is already a style named “{clean}”")
        self._styles[style_id] = replace(style, name=clean, to_name=to_name)
        self.version += 1

    def remove(self, style_id: str) -> StyleDef:
        """Take a style out of the book and return it; refused while other styles are based on it."""
        style = self.get(style_id)
        if self.children(style_id):
            raise ValueError(f"The style “{style.name}” has styles based on it")
        self.version += 1
        return self._styles.pop(style_id)


@dataclass(frozen=True)
class StylesChanged:
    """The styles of the document changed: the whole book (it is small, and a parent's change reaches its children)."""

    styles: tuple[dict, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "styles", "styles": list(self.styles)}


# --------------------------------------------------------------------------- commands
def _book(ctx: Context) -> StyleBook:
    book = getattr(ctx.model, "styles", None)
    if not isinstance(book, StyleBook):
        raise TypeError(f"The {ctx.model.app} model has no style book, so it cannot use style commands")
    return book


def palette_colours(model: object) -> dict[str, str] | None:
    """The role colours of a model that has a palette, else ``None``.

    Asked of the model rather than imported, so that this module knows nothing of :mod:`claudia_core.palette` and
    the two can go on being used apart: an app may hold a style book and no palette.
    """
    colours = getattr(getattr(model, "palette", None), "colours", None)
    return colours() if callable(colours) else None


def _tell(ctx: Context, book: StyleBook) -> None:
    ctx.emit(StylesChanged(tuple(book.views(palette_colours(ctx.model)))))


def _known(book: StyleBook, style_id: str) -> StyleDef:
    try:
        return book.get(style_id)
    except KeyError as exc:
        raise ValueError(exc.args[0]) from None


def _same_style_touched(other: Command, style_id: str) -> bool:
    """Did ``other`` change, name or build on the style ``style_id``?"""
    if isinstance(other, ChangeStyle | RenameStyle | SetHeadingLevel):
        return other.style == style_id
    return isinstance(other, CreateStyle) and other.style.based_on == style_id


@core_commands.register
@dataclass(frozen=True)
class CreateStyle(Command):
    """Add a style to the document."""

    kind: ClassVar[str] = "core.CreateStyle"
    style: StyleDef

    @property
    def label(self) -> str:
        return "New style"

    @property
    def summary(self) -> str:
        return f"created the style “{self.style.name}”"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        book.add(self.style)
        _tell(ctx, book)
        return RemoveStyle(self.style.id)

    def to_data(self) -> dict:
        return self.style.to_data()

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> CreateStyle:
        return cls(StyleDef.from_data(data))


@core_commands.register
@dataclass(frozen=True)
class RemoveStyle(Command):
    """Take a style out again. Only the undo of ``CreateStyle`` (the deletion rules of E1.10 are another story): it is
    refused while another style is based on it or the app says something uses it."""

    kind: ClassVar[str] = "core.RemoveStyle"
    style: str

    @property
    def label(self) -> str:
        return "Remove style"

    @property
    def summary(self) -> str:
        return f"took back the style {self.style}"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        known = _known(book, self.style)
        in_use = getattr(ctx.model, "style_in_use", None)
        if in_use is not None and in_use(self.style):
            raise ValueError(f"The style “{known.name}” is in use and cannot be taken back")
        book.remove(self.style)
        _tell(ctx, book)
        return CreateStyle(known)

    def to_data(self) -> dict:
        return {"style": self.style}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> RemoveStyle:
        return cls(data["style"])

    def shifted_by(self, other: Command) -> Command | None:
        return None if _same_style_touched(other, self.style) else self


@core_commands.register
@dataclass(frozen=True)
class ChangeStyle(Command):
    """Set some of a style's own CSS properties and remove others. Everything that has the style changes with it."""

    kind: ClassVar[str] = "core.ChangeStyle"
    style: str
    set: dict[str, str]
    unset: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return "Change style"

    @property
    def summary(self) -> str:
        return f"changed the style {self.style}: {', '.join(sorted({*self.set, *self.unset}))}"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        known = _known(book, self.style)
        own = dict(known.css)
        was_set = {name: own[name] for name in (*self.set, *self.unset) if name in own}
        was_unset = tuple(name for name in self.set if name not in own)
        for name in self.unset:
            own.pop(name, None)
        own.update(self.set)
        book.set_css(self.style, own)
        _tell(ctx, book)
        return ChangeStyle(self.style, was_set, was_unset)

    def to_data(self) -> dict:
        return {"style": self.style, "set": dict(self.set), "unset": list(self.unset)}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> ChangeStyle:
        return cls(data["style"], dict(data["set"]), tuple(data["unset"]))

    def shifted_by(self, other: Command) -> Command | None:
        if isinstance(other, ChangeStyle) and other.style == self.style:
            touched = {*other.set, *other.unset}
            return None if touched & {*self.set, *self.unset} else self
        return self


@core_commands.register
@dataclass(frozen=True)
class RenameStyle(Command):
    """Give a style another name. ``to_name`` False says that the person has named it (the invitation of E9.7 ends)."""

    kind: ClassVar[str] = "core.RenameStyle"
    style: str
    name: str
    to_name: bool = False

    @property
    def label(self) -> str:
        return "Name style"

    @property
    def summary(self) -> str:
        return f"{'renamed' if self.to_name else 'named'} the style “{self.name}”"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        known = _known(book, self.style)
        book.rename(self.style, self.name, to_name=self.to_name)
        _tell(ctx, book)
        return RenameStyle(self.style, known.name, known.to_name)

    def to_data(self) -> dict:
        return {"style": self.style, "name": self.name, "to_name": self.to_name}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> RenameStyle:
        return cls(data["style"], data["name"], data["to_name"])

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, RenameStyle) and other.style == self.style else self


@core_commands.register
@dataclass(frozen=True)
class SetHeadingLevel(Command):
    """Make a style give its paragraphs a heading level (E9.22): ``None`` as its parent does, ``"body"`` none at all,
    0 the title, 1 to 9 a level. Every paragraph with the style, or a style based on it, changes with it."""

    kind: ClassVar[str] = "core.SetHeadingLevel"
    style: str
    level: HeadingLevel

    @property
    def label(self) -> str:
        return "Heading level"

    @property
    def summary(self) -> str:
        if self.level is None:
            return f"made the style {self.style} a heading as its parent is"
        if self.level == "body":
            return f"made the style {self.style} no heading"
        return f"made the style {self.style} a heading of level {self.level}"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        known = _known(book, self.style)
        book.set_heading_level(self.style, self.level)
        _tell(ctx, book)
        return SetHeadingLevel(self.style, known.heading_level)

    def to_data(self) -> dict:
        return {"style": self.style, "level": self.level}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetHeadingLevel:
        return cls(data["style"], data["level"])

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, SetHeadingLevel) and other.style == self.style else self


@core_commands.register
@dataclass(frozen=True)
class SetStyleNumbering(Command):
    """Make a heading style number its paragraphs in a list (E9.22): ``numbering`` is the list's id, ``None`` "as the
    parent does", :data:`NO_NUMBERING` "not numbered". A paragraph with the style is an item of that list at the level
    below its heading level, unless it is an item of its own; so all heading styles that name one list count together,
    as one outline (1, 1.1, 2 ...)."""

    kind: ClassVar[str] = "core.SetStyleNumbering"
    style: str
    numbering: str | None

    @property
    def label(self) -> str:
        return "Numbering"

    @property
    def summary(self) -> str:
        if self.numbering is None:
            return f"made the style {self.style} numbered as its parent is"
        if self.numbering == NO_NUMBERING:
            return f"made the style {self.style} unnumbered"
        return f"numbered the style {self.style} in the list {self.numbering}"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        known = _known(book, self.style)
        lists = getattr(ctx.model, "lists", None)
        if self.numbering not in (None, NO_NUMBERING) and (lists is None or self.numbering not in lists):
            raise ValueError(f"There is no list {self.numbering!r} to number the style “{known.name}” in")
        book.set_numbering(self.style, self.numbering)
        _tell(ctx, book)
        return SetStyleNumbering(self.style, known.numbering)

    def to_data(self) -> dict:
        return {"style": self.style, "numbering": self.numbering}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetStyleNumbering:
        return cls(data["style"], data["numbering"])

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, SetStyleNumbering) and other.style == self.style else self
