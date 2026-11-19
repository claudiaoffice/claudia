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
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar, Literal

from .commands import Batch, Command, CommandRegistry, core_commands
from .css import INITIAL_CSS, resolve_css, validate_css
from .css import _split_families as split_families
from .facets import check_kind
from .stand_ins import GENERIC_ALIASES

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

#: Where a style can come from (:attr:`~claudia_core.StyleDef.origin`) and what to call it in a sentence. Only
#: ``"document"`` styles can be deleted (D226).
ORIGINS: Mapping[str, str] = {"document": "document", "builtin": "built-in", "template": "template"}


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
    "as my parent", :data:`NO_NUMBERING` "not numbered". ``origin`` says where the style comes from: ``"builtin"``
    (the app made it, every document starts with it), ``"template"`` (a template put it there) or ``"document"`` (a
    person made it, or a deviation did). Only a document style can be deleted; the other two can only be hidden
    (D226). ``hidden`` keeps a style out of the menus a person picks from; it still resolves, so nothing that has it
    looks any different. Neither is written when it has its default, so a style that has neither writes what it
    wrote before."""

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
    origin: str = "document"
    hidden: bool = False

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
        if self.origin != "document":
            data["origin"] = self.origin
        if self.hidden:
            data["hidden"] = True
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
            data.get("origin", "document"),
            data.get("hidden", False),
        )


def _clean_name(name: str) -> str:
    text = " ".join(name.split()) if "\n" not in name and "\r" not in name else ""
    if not text or len(text) > _MAX_NAME or not text.isprintable():
        raise ValueError(f"A style name is one line of 1 to {_MAX_NAME} characters, got {name!r}")
    return text


class StyleBook:
    """The styles of a document, in the order they were made. What is written (:meth:`to_data`) always has a parent
    before its children; in memory the order is the one a person sees in a menu, and re-basing a style under a style
    that was made later leaves it where it was."""

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

    def font_families(self) -> tuple[str, ...]:
        """The fonts the styles ask for by name, each once, sorted: the first family of every ``font-family`` that is
        not a generic one. Later families of a list are fall-backs, not requirements (E1.9, D1306)."""
        found: dict[str, str] = {}
        for style in self._styles.values():
            first = split_families(style.css.get("font-family", ""))[:1]
            name = first[0].strip("'\"").strip() if first else ""
            if name and name.lower() not in GENERIC_ALIASES:
                found.setdefault(name.casefold(), name)
        return tuple(sorted(found.values(), key=str.casefold))

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
        """The book as plain data (for snapshots); ``from_data`` is the inverse. A parent comes before its children,
        whatever order the styles were re-based into, so that ``from_data`` can add them one by one."""
        written: dict[str, StyleDef] = {}
        waiting = list(self._styles.values())
        while waiting:
            later = []
            for style in waiting:
                if style.based_on is None or style.based_on in written:
                    written[style.id] = style
                else:
                    later.append(style)
            if len(later) == len(waiting):  # pragma: no cover - a cycle, which ``rebase`` and ``add`` do not allow
                raise ValueError("the styles are based on each other in a circle")
            waiting = later
        return [style.to_data() for style in written.values()]

    @classmethod
    def from_data(cls, items: Iterable[dict]) -> StyleBook:
        """Build a book from ``to_data``'s output."""
        return cls(StyleDef.from_data(item) for item in items)

    # -- changing (used by the commands) -----------------------------------------
    def add(self, style: StyleDef, *, before: str | None = None) -> None:
        """Add a style: a new id and name, an existing parent of the same kind, CSS that is allowed and belongs to
        the style's kind. Stores the cleaned CSS. It goes last, or in front of the style ``before`` when that is
        there (which is how a style that was taken away returns to its place)."""
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
        if style.origin not in ORIGINS:
            raise ValueError(f"A style's origin is one of {', '.join(ORIGINS)}, got {style.origin!r}")
        cleaned = replace(style, name=name, css=validate_css(style.css))
        if before is not None and before in self._styles:
            items = list(self._styles.items())
            at = next(i for i, (key, _) in enumerate(items) if key == before)
            items.insert(at, (style.id, cleaned))
            self._styles = dict(items)
        else:
            self._styles[style.id] = cleaned
        self.version += 1

    def fallback(self, style_id: str) -> StyleDef | None:
        """The plain style of a style's kind, which a dialog offers first to take its place when it is deleted: the
        built-in root its own chain ends in (a style based on the plain image gets the plain image), else the first
        built-in root of its kind. ``None`` if the book has none. In Claudia a thing always has a style, and this is
        the one that says nothing of its own: the body style for text, the plain box, the plain shape (D785)."""
        style = self.get(style_id)
        root = self.chain(style_id)[0]
        if root.id != style_id and root.origin == "builtin" and root.kind == style.kind:
            return root
        return next(
            (
                other
                for other in self._styles.values()
                if other.based_on is None
                and other.origin == "builtin"
                and other.kind == style.kind
                and other.id != style_id
            ),
            None,
        )

    def next_after(self, style_id: str) -> str | None:
        """The id of the style that comes right after this one in the book, if there is one."""
        ids = list(self._styles)
        at = ids.index(style_id)
        return ids[at + 1] if at + 1 < len(ids) else None

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

    def set_hidden(self, style_id: str, hidden: bool) -> None:
        """Hide a style from the menus a person picks from, or show it again. It still resolves either way."""
        self._styles[style_id] = replace(self.get(style_id), hidden=hidden)
        self.version += 1

    def rebase(
        self,
        style_id: str,
        based_on: str | None,
        css: dict[str, str],
        number_format: str | None,
        heading_level: HeadingLevel,
        numbering: str | None,
    ) -> StyleDef:
        """Put a style under another parent of its kind, with these own properties (and own number format, heading
        level and numbering) instead of the ones it had; returns what it was. The parent may not be the style itself
        or one of the styles based on it, and has to be of the style's kind."""
        style = self.get(style_id)
        if based_on is not None:
            parent = self.get(based_on)
            if any(link.id == style_id for link in self.chain(based_on)):
                raise ValueError(
                    f"“{style.name}” cannot be based on itself"
                    if based_on == style_id
                    else f"“{style.name}” cannot be based on “{parent.name}”, which is based on it"
                )
            if parent.kind != style.kind:
                raise ValueError(
                    f"The {style.kind} style “{style.name}” cannot be based on “{parent.name}”, a {parent.kind} "
                    "style: a style and its parent are of the same kind"
                )
        check_kind(style.kind, css)
        changed = replace(
            style,
            based_on=based_on,
            css=validate_css(css),
            number_format=number_format,
            heading_level=heading_level,
            numbering=numbering,
        )
        _check_heading_level(changed)
        _check_numbering(changed)
        self._styles[style_id] = changed
        self.version += 1
        return style

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
    if isinstance(other, ChangeStyle | RenameStyle | SetHeadingLevel | SetStyleNumbering | RebaseStyle):
        return other.style == style_id
    return isinstance(other, CreateStyle) and other.style.based_on == style_id


@core_commands.register
@dataclass(frozen=True)
class CreateStyle(Command):
    """Add a style to the document."""

    kind: ClassVar[str] = "core.CreateStyle"
    style: StyleDef
    #: The style that comes right after this one in the book, when it is put back where it was (the undo of a
    #: removal); ``None`` for a new style, which goes last.
    before: str | None = None

    @property
    def label(self) -> str:
        return "New style"

    @property
    def summary(self) -> str:
        return f"created the style “{self.style.name}”"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        book.add(self.style, before=self.before)
        _tell(ctx, book)
        return RemoveStyle(self.style.id)

    def to_data(self) -> dict:
        data = self.style.to_data()
        if self.before is not None:
            data["before"] = self.before
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> CreateStyle:
        return cls(StyleDef.from_data(data), data.get("before"))


@core_commands.register
@dataclass(frozen=True)
class RemoveStyle(Command):
    """Take a style out again. It is the undo of ``CreateStyle`` and the last step of a deletion
    (:func:`~claudia_core.plan_delete_style`, which first moves everything off the style): it is refused while
    another style is based on it or the app says something uses it, which is also what refuses a deletion whose
    style somebody else began to use meanwhile (D226)."""

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
        after = book.next_after(self.style)
        book.remove(self.style)
        _tell(ctx, book)
        return CreateStyle(known, after)

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


@core_commands.register
@dataclass(frozen=True)
class RebaseStyle(Command):
    """Put a style under another parent (or none) and give it exactly these own properties, number format, heading
    level and numbering, in one step (D226). The properties are what the style must say itself so that it *looks the
    same* under its new parent (:func:`held_look`): changing the parent is never a change of look. The inverse is the
    same command with what the style had before."""

    kind: ClassVar[str] = "core.RebaseStyle"
    style: str
    based_on: str | None
    css: dict[str, str]
    number_format: str | None
    heading_level: HeadingLevel
    numbering: str | None

    @property
    def label(self) -> str:
        return "Change parent style"

    @property
    def summary(self) -> str:
        return f"based the style {self.style} on {self.based_on or 'nothing'}"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        _known(book, self.style)
        if self.numbering not in (None, NO_NUMBERING):
            lists = getattr(ctx.model, "lists", None)
            if lists is None or self.numbering not in lists:
                raise ValueError(f"There is no list {self.numbering!r} to number the style {self.style!r} in")
        was = book.rebase(self.style, self.based_on, self.css, self.number_format, self.heading_level, self.numbering)
        _tell(ctx, book)
        return RebaseStyle(self.style, was.based_on, dict(was.css), was.number_format, was.heading_level, was.numbering)

    def to_data(self) -> dict:
        return {
            "style": self.style,
            "based_on": self.based_on,
            "css": dict(self.css),
            "number_format": self.number_format,
            "heading_level": self.heading_level,
            "numbering": self.numbering,
        }

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> RebaseStyle:
        return cls(
            data["style"],
            data["based_on"],
            dict(data["css"]),
            data["number_format"],
            data["heading_level"],
            data["numbering"],
        )

    def shifted_by(self, other: Command) -> Command | None:
        return None if _same_style_touched(other, self.style) else self


@core_commands.register
@dataclass(frozen=True)
class SetStyleHidden(Command):
    """Hide a style from the menus a person picks a style from, or show it again (D226). A hidden style still
    resolves, so nothing that has it looks any different; this is the one thing that can be done to a built-in or
    template style that is not wanted."""

    kind: ClassVar[str] = "core.SetStyleHidden"
    style: str
    hidden: bool

    @property
    def label(self) -> str:
        return "Hide style" if self.hidden else "Show style"

    @property
    def summary(self) -> str:
        return f"{'hid' if self.hidden else 'showed'} the style {self.style}"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        known = _known(book, self.style)
        book.set_hidden(self.style, self.hidden)
        _tell(ctx, book)
        return SetStyleHidden(self.style, known.hidden)

    def to_data(self) -> dict:
        return {"style": self.style, "hidden": self.hidden}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetStyleHidden:
        return cls(data["style"], data["hidden"])

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, SetStyleHidden) and other.style == self.style else self


# --------------------------------------------------------------------------- deleting
def held_look(old: Mapping[str, str], base: Mapping[str, str]) -> dict[str, str]:
    """The properties a style must set itself to look as ``old`` says under a parent that looks as ``base`` says.

    Only what differs: a property both say the same is left to the parent. A property the parent sets and the old
    look did not gets the value of nothing (:data:`~claudia_core.css.INITIAL_CSS`), so that the new parent does not show
    through. ``ValueError`` names a property for which there is no such value, because that is the one place a look
    cannot be held without asking an app what "nothing" means there."""
    held: dict[str, str] = {}
    for prop in (*old, *(prop for prop in base if prop not in old)):
        if prop in old:
            wanted = old[prop]
        elif prop in INITIAL_CSS:
            wanted = INITIAL_CSS[prop]
        else:
            raise ValueError(
                f"The look cannot be kept: the new parent sets “{prop}” and nothing says what a style "
                "that does not set it looks like"
            )
        if base.get(prop) != wanted:
            held[prop] = wanted
    return held


@dataclass(frozen=True)
class _Look:
    """What a style looks like, everything its parents say taken in: the CSS and the three inherited settings."""

    css: dict[str, str]
    number_format: str | None
    heading_level: int | None
    numbering: str | None

    @classmethod
    def of(cls, book: StyleBook, style_id: str | None) -> _Look:
        if style_id is None:
            return cls({}, None, None, None)
        return cls(
            book.computed(style_id),
            book.number_format(style_id),
            book.heading_level(style_id),
            book.numbering(style_id),
        )


def _own_settings(old: _Look, base: _Look) -> tuple[dict[str, str], str | None, HeadingLevel, str | None]:
    """What a style must say itself to look as ``old`` under a parent that looks as ``base``: its CSS, its number
    format, heading level and numbering. A setting both agree on is left to the parent (``None``)."""
    css = held_look(old.css, base.css)
    number_format = None
    if old.number_format != base.number_format:
        if old.number_format is None:
            raise ValueError("The look cannot be kept: the new parent shows numbers in a format this style does not")
        number_format = old.number_format
    heading: HeadingLevel = None
    if old.heading_level != base.heading_level:
        heading = "body" if old.heading_level is None else old.heading_level
    numbering = None
    if old.numbering != base.numbering:
        numbering = NO_NUMBERING if old.numbering is None else old.numbering
    return css, number_format, heading, numbering


def _free_name(book: StyleBook, name: str) -> str:
    """``name (kept)``, or ``name (kept 2)`` and so on, whichever no style has."""
    candidate, number = f"{name} (kept)", 1
    while book.name_taken(candidate):
        number += 1
        candidate = f"{name} (kept {number})"
    return candidate


#: How a style can be deleted (:func:`~claudia_core.plan_delete_style`), in the order a dialog offers them (D785).
DELETE_HOWS: tuple[str, ...] = ("assign", "rebase")


def assign_changes_look(model: object, style_id: str, target: str) -> bool:
    """Whether deleting the style by *assigning* ``target`` would change how something looks: what has the style
    itself would look like ``target`` instead, and what is based on it is based on ``target`` and loses what the style
    said. ``False`` when nothing has it and nothing is based on it, or when what it said made no difference. Asked by
    the dialog for each style on offer, which says so in words (D785)."""
    book = getattr(model, "styles", None)
    if not isinstance(book, StyleBook):
        raise TypeError("This document has no style book")
    _known(book, style_id)
    _known(book, target)
    in_use = getattr(model, "style_in_use", None)
    if in_use is not None and in_use(style_id) and _Look.of(book, style_id) != _Look.of(book, target):
        return True
    children = book.children(style_id)
    if not children:
        return False
    after = StyleBook.from_data(book.to_data())
    for child in children:
        own = after.get(child)
        after.rebase(child, target, own.css, own.number_format, own.heading_level, own.numbering)
    after.remove(style_id)
    return any(_Look.of(book, child) != _Look.of(after, child) for child in _descendants(book, style_id))


def _descendants(book: StyleBook, style_id: str) -> list[str]:
    """The styles based on this one, directly or not."""
    found: list[str] = []
    for child in book.children(style_id):
        found.append(child)
        found.extend(_descendants(book, child))
    return found


def plan_delete_style(model: object, style_id: str, *, how: str = "assign", target: str | None = None) -> Batch:
    """The commands that delete a style, as one step that is undone as one, and that never leave anything pointing
    at it (D226). The person chooses ``how`` (:data:`~claudia_core.styles.DELETE_HOWS`, D785) and the style
    ``target``, one of the same kind, never the style itself or one based on it:

    - ``"assign"``: **assign another style.** Everything that has the style itself has ``target`` instead, and what is
      based on the style is based on ``target``, each as it is. Looks change, and the dialog says so
      (:func:`assign_changes_look`). The plain style of the kind, :meth:`StyleBook.fallback`, is what a dialog offers
      first: it is how "no style" reads in a document where everything always has one.
    - ``"rebase"``: **build it on another style, and keep how it looks.** What is based on the style moves under
      ``target`` and says only what differs from it; what has the style itself goes to a *stand-in* style under
      ``target``: a document style with the deleted style's purpose, named ``<name> (kept)`` and provisional until its
      maker names it (E9.7). The *look* is held (:func:`held_look`), so later changes to ``target`` reach everything
      that did not say otherwise. A deletion is refused (``ValueError``, nothing planned) if a look cannot be held.

    ``target`` may be left out only when nothing has the style and nothing is based on it: then the style just goes.

    The style goes last. If something else began to use it since the plan was made, that last step is refused, and so
    the whole deletion, and nothing changes: nobody's work is moved without their knowing.

    Built-in and template styles are refused: they can only be hidden (:class:`SetStyleHidden`).
    """
    if how not in DELETE_HOWS:
        raise ValueError(f"A style is deleted by one of {', '.join(DELETE_HOWS)}, not {how!r}")
    book = getattr(model, "styles", None)
    if not isinstance(book, StyleBook):
        raise TypeError("This document has no style book, so it cannot delete a style")
    style = _known(book, style_id)
    if style.origin != "document":
        raise ValueError(f"“{style.name}” is a {ORIGINS[style.origin]} style and can only be hidden, not deleted")
    in_use = getattr(model, "style_in_use", None)
    used = in_use is not None and in_use(style_id)
    restyle = getattr(model, "restyle_users", None)
    if used and restyle is None:
        raise ValueError(f"The app cannot move what has the style “{style.name}” to another style")
    children = book.children(style_id)
    if target is None:
        if used or children:
            raise ValueError(f"“{style.name}” is in use: say which style takes its place")
        return Batch((RemoveStyle(style_id),), f"Delete style “{style.name}”")
    parent = _checked_target(book, style, target, how)
    steps: list[Command] = []
    users: list[Command] = []
    if how == "assign":
        if used:
            users = list(_restyler(restyle)(style_id, target))
        for child_id in children:
            child = book.get(child_id)
            steps.append(
                RebaseStyle(
                    child_id, target, dict(child.css), child.number_format, child.heading_level, child.numbering
                )
            )
    else:
        base = _Look.of(book, target)
        if used:
            css, number_format, heading, numbering = _own_settings(_Look.of(book, style_id), base)
            name = _free_name(book, style.name)
            stand_in = StyleDef(
                book.unique_id(name),
                name,
                style.purpose,
                parent.id,
                css,
                to_name=True,
                kind=style.kind,
                number_format=number_format,
                heading_level=heading,
                numbering=numbering,
            )
            steps.append(CreateStyle(stand_in))
            users = list(_restyler(restyle)(style_id, stand_in.id))
        for child_id in children:
            css, number_format, heading, numbering = _own_settings(_Look.of(book, child_id), base)
            steps.append(RebaseStyle(child_id, target, css, number_format, heading, numbering))
    steps.extend(users)
    steps.append(RemoveStyle(style_id))
    return Batch(tuple(steps), f"Delete style “{style.name}”")


def _checked_target(book: StyleBook, style: StyleDef, target: str, how: str) -> StyleDef:
    """The style that takes the deleted one's place, if it can: of the same kind, and neither the style itself nor
    one based on it (that would be a cycle)."""
    verb = "replaced by" if how == "assign" else "re-based on"
    parent = _known(book, target)
    if target == style.id:
        raise ValueError(f"“{style.name}” cannot be {verb} itself")
    if any(link.id == style.id for link in book.chain(target)):
        raise ValueError(f"“{style.name}” cannot be {verb} “{parent.name}”, which is based on it")
    if parent.kind != style.kind:
        raise ValueError(
            f"“{style.name}” is a {style.kind} style and “{parent.name}” a {parent.kind} style: "
            "a style can only be taken over by one of the same kind"
        )
    return parent


def _restyler(restyle: object) -> Callable[[str, str], list[Command]]:
    """The model's ``restyle_users``, which is there whenever something uses the style (checked by the caller)."""
    if not callable(restyle):
        raise TypeError("The app cannot move what has the style to another style")
    return restyle
