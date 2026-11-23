"""Numbering schemes: how the markers of a list are drawn, level by level, as part of the document (E9.22).

A list (:class:`~claudia_core.ListDef`) names a **scheme** by id. The scheme says what each of the nine levels shows
— a number format or a bullet, the text before and after it, and how much of the trail of counters above it — and how
far a level moves the text in. Schemes used to be code; they are document data now, as the styles and the palette
are (D200's reasoning): the numbering manager can change them, and a document looks the same on every server.

* :class:`LevelFormat` is one level, :class:`Scheme` nine of them with an indent and a gap.
* :class:`SchemeBook` is what an app's model holds (an attribute ``schemes``). Every new document starts with the
  built-in schemes: ``bullets`` (• ◦ ▪), ``numbers`` (1. a. i.) and ``chapters`` (1, 1.1, 1.1.1, the trail of all
  levels, without a full stop at the end, as DIN 5008 numbers sections).
* :class:`CreateScheme`, :class:`ChangeScheme` and :class:`RemoveScheme` are the only ways to change the book; they
  emit :class:`SchemesChanged` (wire type ``schemes``). A scheme a list uses cannot be removed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from .commands import Command, CommandRegistry, core_commands
from .errors import N_, Refusal
from .paragraphs import MAX_LIST_LEVEL

if TYPE_CHECKING:
    from .context import Context

LEVELS = MAX_LIST_LEVEL + 1
_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_MAX_NAME = 60
_MAX_AFFIX = 20
_MAX_INDENT = 10.0
_MAX_GAP = 5.0
_ROMAN = ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"), (10, "x"),
          (9, "ix"), (5, "v"), (4, "iv"), (1, "i"))  # fmt: skip
#: What the trail of a reference joins the counters of the levels with ("2.1.3").
TRAIL_SEPARATOR = "."


def _alpha(n: int) -> str:
    """1 -> a, 26 -> z, 27 -> aa, 28 -> ab ...: letters counted like spreadsheet columns."""
    out = ""
    while n > 0:
        n, rest = divmod(n - 1, 26)
        out = chr(ord("a") + rest) + out
    return out


def _roman(n: int) -> str:
    """Lower-case roman numerals up to 3999; after that plain digits, which stay correct and readable."""
    if not 1 <= n <= 3999:
        return str(n)
    out = ""
    for value, letters in _ROMAN:
        while n >= value:
            out += letters
            n -= value
    return out


def _upper_roman(n: int) -> str:
    return _roman(n).upper()


def _upper_alpha(n: int) -> str:
    return _alpha(n).upper()


#: How a counter is written, by the name of the format. ``bullet`` and ``none`` draw no counter.
COUNTER_FORMATS: dict[str, Callable[[int], str]] = {
    "decimal": str,
    "lower-alpha": _alpha,
    "upper-alpha": _upper_alpha,
    "lower-roman": _roman,
    "upper-roman": _upper_roman,
}
#: Every format a level can have.
FORMATS: tuple[str, ...] = (*COUNTER_FORMATS, "bullet", "none")


def _one_line(text: str, longest: int) -> bool:
    return len(text) <= longest and (not text or text.isprintable())


# --------------------------------------------------------------------------- one level
@dataclass(frozen=True)
class LevelFormat:
    """What one level of a list shows.

    ``format`` is one of :data:`FORMATS`. ``bullet`` is the sign a ``bullet`` level draws. ``before`` and ``after``
    are written around the counters ("Chapter ", "."). ``from_level`` is the first level whose counter the label
    carries: the level's own number shows only its counter ("b."), 0 the whole trail ("2.1.3")."""

    format: str = "decimal"
    bullet: str = ""
    before: str = ""
    after: str = ""
    from_level: int = 0

    @property
    def counts(self) -> bool:
        """Does this level write a counter?"""
        return self.format in COUNTER_FORMATS

    def counter(self, number: int) -> str:
        """``number`` in this level's format; a level that writes no counter writes it in digits (for the trail)."""
        return COUNTER_FORMATS.get(self.format, str)(number)

    def to_data(self) -> dict:
        """The plain-data form that goes into snapshots, commands and events."""
        return {
            "format": self.format,
            "bullet": self.bullet,
            "before": self.before,
            "after": self.after,
            "from_level": self.from_level,
        }

    @classmethod
    def from_data(cls, data: dict) -> LevelFormat:
        """Inverse of ``to_data``."""
        return cls(data["format"], data["bullet"], data["before"], data["after"], data["from_level"])

    def check(self, level: int) -> None:
        """``ValueError`` with a sentence if this cannot be level ``level`` of a scheme."""
        if self.format not in FORMATS:
            raise ValueError(f"A level's format is one of {', '.join(FORMATS)}, got {self.format!r}")
        if self.format == "bullet" and not (1 <= len(self.bullet) <= 4 and self.bullet.isprintable()):
            raise Refusal("A bullet is one sign (up to 4 characters), got {bullet!r}", bullet=self.bullet)
        for text in (self.before, self.after):
            if not isinstance(text, str) or not _one_line(text, _MAX_AFFIX):
                raise Refusal(
                    "The text before and after a number is one line of up to {max_affix} characters",
                    max_affix=_MAX_AFFIX,
                )
        if not isinstance(self.from_level, int) or not 0 <= self.from_level <= level:
            shown = self.from_level + 1 if isinstance(self.from_level, int) else self.from_level
            raise ValueError(f"Level {level + 1} shows the levels from 1 to {level + 1} on, got {shown!r}")


def _repeating(make: Callable[[int], LevelFormat]) -> tuple[LevelFormat, ...]:
    return tuple(make(level) for level in range(LEVELS))


_BULLET_SIGNS = ("•", "◦", "▪")
_NUMBER_FORMATS = ("decimal", "lower-alpha", "lower-roman")


# --------------------------------------------------------------------------- a scheme
@dataclass(frozen=True)
class Scheme:
    """How a list looks: ``kind`` says whether its items are counted ("number") or not ("bullet"), ``levels`` what
    each of the nine levels shows, ``indent`` how far each level moves the text in and ``gap`` the space between two
    neighbouring items of one list (both in ``em``)."""

    id: str
    name: str
    kind: str  # "bullet" | "number"
    levels: tuple[LevelFormat, ...] = field(default_factory=tuple)
    indent: float = 1.6
    gap: float = 0.25

    @property
    def counts(self) -> bool:
        """Does this scheme count its items?"""
        return self.kind == "number"

    def level(self, level: int) -> LevelFormat:
        """The format of ``level``; a scheme with fewer levels repeats its last one."""
        return self.levels[min(level, len(self.levels) - 1)] if self.levels else LevelFormat()

    def marker(self, path: tuple[int, ...]) -> str:
        """What is drawn for the item whose counters, outermost first, are ``path`` (its level is ``len(path) - 1``)."""
        level = len(path) - 1
        own = self.level(level)
        if own.format == "bullet":
            return f"{own.before}{own.bullet}{own.after}"
        if own.format == "none":
            return f"{own.before}{own.after}"
        trail = TRAIL_SEPARATOR.join(self.level(k).counter(path[k]) for k in range(own.from_level, level + 1))
        return f"{own.before}{trail}{own.after}"

    def number(self, path: tuple[int, ...]) -> str:
        """The whole trail, without the text around it: what a reference prints ("2.3", "2.b")."""
        return TRAIL_SEPARATOR.join(self.level(k).counter(n) for k, n in enumerate(path))

    def to_data(self) -> dict:
        """The plain-data form that goes into snapshots, commands and events, and is sent to clients."""
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "levels": [level.to_data() for level in self.levels],
            "indent": self.indent,
            "gap": self.gap,
        }

    @classmethod
    def from_data(cls, data: dict) -> Scheme:
        """Inverse of ``to_data``."""
        levels = tuple(LevelFormat.from_data(level) for level in data["levels"])
        return cls(data["id"], data["name"], data["kind"], levels, data["indent"], data["gap"])

    def check(self) -> None:
        """``ValueError`` with a sentence if the scheme makes no sense."""
        if not _ID.fullmatch(self.id):
            raise ValueError(f"A scheme id is lower-case letters, digits and hyphens (up to 40), got {self.id!r}")
        if not isinstance(self.name, str) or not self.name.strip() or not _one_line(self.name, _MAX_NAME):
            raise Refusal(
                "A scheme name is one line of 1 to {max_name} characters, got {name!r}",
                max_name=_MAX_NAME,
                name=self.name,
            )
        if self.kind not in ("bullet", "number"):
            raise ValueError(f"A scheme is a bullet or a number scheme, got {self.kind!r}")
        if len(self.levels) != LEVELS:
            raise ValueError(f"A scheme has {LEVELS} levels, got {len(self.levels)}")
        for level, each in enumerate(self.levels):
            each.check(level)
        for value, largest, what in (
            (self.indent, _MAX_INDENT, N_("A scheme's indent is from 0 to {largest:g} em, got {value!r}")),
            (self.gap, _MAX_GAP, N_("A scheme's gap is from 0 to {largest:g} em, got {value!r}")),
        ):
            if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= largest:
                raise Refusal(what, largest=largest, value=value)


def builtin_schemes() -> tuple[Scheme, ...]:
    """The schemes every document starts with. A person may change them; "Reset" brings back these."""
    return (
        Scheme(
            "bullets",
            "Bullets",
            "bullet",
            _repeating(lambda k: LevelFormat("bullet", _BULLET_SIGNS[k % 3], from_level=k)),
        ),
        Scheme(
            "numbers",
            "Numbers",
            "number",
            _repeating(lambda k: LevelFormat(_NUMBER_FORMATS[k % 3], after=".", from_level=k)),
        ),
        Scheme("chapters", "Chapters", "number", _repeating(lambda k: LevelFormat("decimal"))),
    )


def builtin_scheme(scheme_id: str) -> Scheme | None:
    """The built-in scheme with this id, or ``None``."""
    return next((s for s in builtin_schemes() if s.id == scheme_id), None)


# --------------------------------------------------------------------------- the book
class SchemeBook:
    """The schemes of a document, in the order they were made; a new book has the built-in ones."""

    def __init__(self, schemes: Iterable[Scheme] | None = None):
        self._schemes: dict[str, Scheme] = {}
        #: Counts every change, so that whoever derives something from the book (the labels) knows to do it again.
        self.version = 0
        for each in builtin_schemes() if schemes is None else schemes:
            self.add(each)

    def __contains__(self, scheme_id: object) -> bool:
        return scheme_id in self._schemes

    def __iter__(self) -> Iterator[Scheme]:
        return iter(list(self._schemes.values()))

    def __len__(self) -> int:
        return len(self._schemes)

    def ids(self) -> list[str]:
        """The ids of all schemes, in order."""
        return list(self._schemes)

    def get(self, scheme_id: str) -> Scheme:
        """The scheme with this id; ``KeyError`` if there is none."""
        try:
            return self._schemes[scheme_id]
        except KeyError:
            raise KeyError(f"no list scheme {scheme_id!r}; there are {', '.join(self._schemes)}") from None

    def unique_id(self) -> str:
        """A free id for a new scheme: ``scheme-1``, ``scheme-2`` ... one more than the highest number taken."""
        taken = [int(i[7:]) for i in self._schemes if i.startswith("scheme-") and i[7:].isdigit()]
        return f"scheme-{max(taken, default=0) + 1}"

    def to_data(self) -> list[dict]:
        """The book as plain data (for snapshots); ``from_data`` is the inverse."""
        return [each.to_data() for each in self._schemes.values()]

    @classmethod
    def from_data(cls, items: Iterable[dict] | None) -> SchemeBook:
        """Build a book from ``to_data``'s output; ``None`` (a document from before schemes were data) gives the
        built-in ones."""
        return cls(None if items is None else (Scheme.from_data(item) for item in items))

    def drawing(self, levels: Mapping[int, LevelFormat], counts: bool, name: str | None = None) -> str | None:
        """The id of a scheme that draws a list with these ``levels`` (by level number; the others as the built-in
        scheme of its kind draws them), adding one, named after ``name``, if the book has none. What a file's list is
        drawn with when it is read. ``None`` when the levels make no scheme (:meth:`Scheme.check` refuses it)."""
        said = {number: level for number, level in levels.items() if 0 <= number < LEVELS}
        kind = "number" if counts else "bullet"
        for scheme in self._schemes.values():
            if scheme.kind == kind and all(scheme.level(number) == level for number, level in said.items()):
                return scheme.id
        base = builtin_scheme("numbers" if counts else "bullets")
        assert base is not None  # a built-in scheme
        filled = tuple(said.get(number, base.level(number)) for number in range(LEVELS))
        made = Scheme(self.unique_id(), self._free_name(name), kind, filled, base.indent, base.gap)
        try:
            made.check()
        except ValueError:
            return None
        self.add(made)
        return made.id

    def _free_name(self, name: str | None) -> str:
        taken = {scheme.name for scheme in self._schemes.values()}
        base = name if name and name.strip() and len(name) <= _MAX_NAME - 4 and name.isprintable() else "Imported"
        candidate, number = base, 1
        while candidate in taken:
            number += 1
            candidate = f"{base} {number}"
        return candidate

    # -- changing (used by the commands) -----------------------------------------
    def add(self, each: Scheme) -> None:
        """Add a scheme with a new id."""
        each.check()
        if each.id in self._schemes:
            raise ValueError(f"The scheme {each.id!r} exists already")
        self._schemes[each.id] = each
        self.version += 1

    def replace(self, each: Scheme) -> Scheme:
        """Give the scheme with this id another definition; returns the old one."""
        each.check()
        old = self.get(each.id)
        self._schemes[each.id] = each
        self.version += 1
        return old

    def remove(self, scheme_id: str) -> Scheme:
        """Take a scheme out of the book and return it."""
        self.get(scheme_id)
        self.version += 1
        return self._schemes.pop(scheme_id)


# --------------------------------------------------------------------------- commands
@dataclass(frozen=True)
class SchemesChanged:
    """The schemes of the document changed: all of them (there are few)."""

    schemes: tuple[dict, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "schemes", "schemes": list(self.schemes)}


def schemes_of(model: object) -> SchemeBook:
    """The scheme book of ``model``; ``TypeError`` for a model that has none."""
    book = getattr(model, "schemes", None)
    if not isinstance(book, SchemeBook):
        raise TypeError(f"The {getattr(model, 'app', 'unknown')} model has no list schemes")
    return book


def _tell(ctx: Context, book: SchemeBook) -> None:
    ctx.emit(SchemesChanged(tuple(book.to_data())))


def _known(book: SchemeBook, scheme_id: str) -> Scheme:
    try:
        return book.get(scheme_id)
    except KeyError as exc:
        raise ValueError(exc.args[0]) from None


@core_commands.register
@dataclass(frozen=True)
class CreateScheme(Command):
    """Add a scheme to the document; lists can use it from then on."""

    kind: ClassVar[str] = "core.CreateScheme"
    scheme: Scheme

    @property
    def label(self) -> str:
        return "New numbering scheme"

    @property
    def summary(self) -> str:
        return f"made the numbering scheme {self.scheme.name}"

    def apply(self, ctx: Context) -> Command:
        book = schemes_of(ctx.model)
        book.add(self.scheme)
        _tell(ctx, book)
        return RemoveScheme(self.scheme.id)

    def to_data(self) -> dict:
        return self.scheme.to_data()

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> CreateScheme:
        return cls(Scheme.from_data(data))


@core_commands.register
@dataclass(frozen=True)
class RemoveScheme(Command):
    """Take a scheme out of the document; refused while a list uses it."""

    kind: ClassVar[str] = "core.RemoveScheme"
    scheme: str

    @property
    def label(self) -> str:
        return "Remove numbering scheme"

    @property
    def summary(self) -> str:
        return f"removed the numbering scheme {self.scheme}"

    def apply(self, ctx: Context) -> Command:
        book = schemes_of(ctx.model)
        known = _known(book, self.scheme)
        lists = getattr(ctx.model, "lists", ())
        users = [each.id for each in lists if each.scheme == self.scheme]
        if users:
            raise Refusal(
                "The scheme {scheme!r} is used by the list {users!r} and cannot be removed",
                scheme=self.scheme,
                users=users[0],
            )
        book.remove(self.scheme)
        _tell(ctx, book)
        return CreateScheme(known)

    def to_data(self) -> dict:
        return {"scheme": self.scheme}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> RemoveScheme:
        return cls(data["scheme"])

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, ChangeScheme) and other.scheme.id == self.scheme else self


@core_commands.register
@dataclass(frozen=True)
class ChangeScheme(Command):
    """Give a scheme another definition: every list that uses it, and so every item, is drawn the new way."""

    kind: ClassVar[str] = "core.ChangeScheme"
    scheme: Scheme

    @property
    def label(self) -> str:
        return "Change numbering scheme"

    @property
    def summary(self) -> str:
        return f"changed the numbering scheme {self.scheme.name}"

    def apply(self, ctx: Context) -> Command:
        book = schemes_of(ctx.model)
        _known(book, self.scheme.id)
        old = book.replace(self.scheme)
        _tell(ctx, book)
        return ChangeScheme(old)

    def to_data(self) -> dict:
        return self.scheme.to_data()

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> ChangeScheme:
        return cls(Scheme.from_data(data))

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, ChangeScheme) and other.scheme.id == self.scheme.id else self
