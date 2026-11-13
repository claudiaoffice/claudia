"""Lists: what makes a paragraph an item, how bullets and numbers are derived, and the book of lists (E9.21).

A list item is *structure*, like a heading level: a paragraph has an :class:`~claudia_core.ListItem` (which list,
which level). Its look stays with its style. What a list adds is a **scheme**, a named recipe for how the markers
of each level are drawn and how far each level is indented. Markers are never characters of the text.

* A **list** is explicit: a :class:`ListDef` with an id, a scheme, the number to start at and an optional ``name``.
  Items that share a list id are one list, in document order, whatever lies between them; items of two different
  lists never count together, even when they are neighbours. The name is for people (the numbering manager and
  references of E9.22 will show it); nothing here needs it yet.
* **Labels are derived, never stored.** :func:`~claudia_core.numbering_labels` is one pure function from the items,
  in document order, to the label of each: the marker that is drawn (``•``, ``3.``, ``b.``) and, for numbers, the
  trail of counters (``(2, 1)``) that a reference to "section 2.1" will later need. It is total: a missing parent or an
  unknown list can never make it fail.
* The :class:`ListBook` is what an app's model holds (an attribute ``lists``); the commands below are the only
  ways to change it, so every change is in the log, can be undone and is seen by everybody. A model may have a
  method ``list_in_use(list_id) -> bool`` that tells :class:`RemoveList` whether an item uses a list.

Every app that has paragraphs can hold lists: the same functions count the items of a composes text and of the
paragraphs in a creates text box.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from .commands import Command, CommandRegistry, core_commands
from .paragraphs import MAX_LIST_LEVEL, ListItem

if TYPE_CHECKING:
    from .context import Context

_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_MAX_NAME = 60
_MAX_START = 999_999
_ROMAN = ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"), (10, "x"),
          (9, "ix"), (5, "v"), (4, "iv"), (1, "i"))  # fmt: skip


# --------------------------------------------------------------------------- schemes
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


_NUMBER_FORMATS: tuple[Callable[[int], str], ...] = (str, _alpha, _roman)
_BULLET_SIGNS = ("•", "◦", "▪")


@dataclass(frozen=True)
class Scheme:
    """How a list looks: ``kind`` says whether it counts, ``indent`` is how far each level moves the text in (in
    ``em``), and ``gap`` the space between two neighbouring items of one list (in ``em``). Schemes are code, like
    the built-in styles; the numbering manager of E9.22 will make them editable."""

    id: str
    name: str
    kind: str  # "bullet" | "number"
    indent: float = 1.6
    gap: float = 0.25

    @property
    def counts(self) -> bool:
        """Does this scheme count its items?"""
        return self.kind == "number"

    def marker(self, level: int, number: int) -> str:
        """What is drawn at ``level`` for the ``number``-th item (ignored by a scheme that does not count)."""
        if not self.counts:
            return _BULLET_SIGNS[level % len(_BULLET_SIGNS)]
        return f"{_NUMBER_FORMATS[level % len(_NUMBER_FORMATS)](number)}."

    def to_data(self) -> dict:
        """The plain-data form that is sent to clients."""
        return {"id": self.id, "name": self.name, "kind": self.kind, "indent": self.indent, "gap": self.gap}


#: The schemes there are: the id of a list's scheme is a key of this.
SCHEMES: dict[str, Scheme] = {
    "bullets": Scheme("bullets", "Bullets", "bullet"),
    "numbers": Scheme("numbers", "Numbers", "number"),
}


# --------------------------------------------------------------------------- the lists
@dataclass(frozen=True)
class ListDef:
    """One list: its ``id``, its ``scheme`` (an id), the number its first level starts at, and an optional ``name``."""

    id: str
    scheme: str
    start: int = 1
    name: str | None = None

    def to_data(self) -> dict:
        """The plain-data form that goes into snapshots, commands and events."""
        return {"id": self.id, "scheme": self.scheme, "start": self.start, "name": self.name}

    @classmethod
    def from_data(cls, data: dict) -> ListDef:
        """Inverse of ``to_data``."""
        return cls(data["id"], data["scheme"], data["start"], data["name"])

    def check(self) -> None:
        """``ValueError`` with a sentence if the list makes no sense."""
        if not _ID.fullmatch(self.id):
            raise ValueError(f"A list id is lower-case letters, digits and hyphens (up to 40), got {self.id!r}")
        if self.scheme not in SCHEMES:
            raise ValueError(f"There is no list scheme {self.scheme!r}; there are {', '.join(SCHEMES)}")
        if not isinstance(self.start, int) or not 1 <= self.start <= _MAX_START:
            raise ValueError(f"A list starts at a number from 1 to {_MAX_START}, got {self.start!r}")
        if self.name is not None and (
            not self.name.strip() or len(self.name) > _MAX_NAME or not self.name.isprintable()
        ):
            raise ValueError(f"A list name is one line of 1 to {_MAX_NAME} characters, got {self.name!r}")


class ListBook:
    """The lists of a document, in the order they were made."""

    def __init__(self, lists: Iterable[ListDef] = ()):
        self._lists: dict[str, ListDef] = {}
        #: Counts every change, so that whoever derives something from the book (the labels of a text) can tell
        #: whether it has to derive it again.
        self.version = 0
        for each in lists:
            self.add(each)

    def __contains__(self, list_id: object) -> bool:
        return list_id in self._lists

    def __iter__(self) -> Iterator[ListDef]:
        return iter(list(self._lists.values()))

    def __len__(self) -> int:
        return len(self._lists)

    def ids(self) -> list[str]:
        """The ids of all lists, in order."""
        return list(self._lists)

    def get(self, list_id: str) -> ListDef:
        """The list with this id; ``KeyError`` if there is none."""
        try:
            return self._lists[list_id]
        except KeyError:
            raise KeyError(f"no list {list_id!r}") from None

    def unique_id(self) -> str:
        """A free id for a new list: ``l1``, ``l2`` ... one more than the highest number a list has now."""
        numbers = [int(i[1:]) for i in self._lists if i[0] == "l" and i[1:].isdigit()]
        return f"l{max(numbers, default=0) + 1}"

    def to_data(self) -> list[dict]:
        """The book as plain data (for snapshots); ``from_data`` is the inverse."""
        return [each.to_data() for each in self._lists.values()]

    @classmethod
    def from_data(cls, items: Iterable[dict]) -> ListBook:
        """Build a book from ``to_data``'s output."""
        return cls(ListDef.from_data(item) for item in items)

    # -- changing (used by the commands) -----------------------------------------
    def add(self, each: ListDef) -> None:
        """Add a list with a new id, a known scheme and sensible numbers."""
        each.check()
        if each.id in self._lists:
            raise ValueError(f"The list {each.id!r} exists already")
        self._lists[each.id] = each
        self.version += 1

    def replace(self, each: ListDef) -> ListDef:
        """Give the list with this id another definition; returns the old one."""
        each.check()
        old = self.get(each.id)
        self._lists[each.id] = each
        self.version += 1
        return old

    def remove(self, list_id: str) -> ListDef:
        """Take a list out of the book and return it."""
        self.get(list_id)
        self.version += 1
        return self._lists.pop(list_id)


# --------------------------------------------------------------------------- counting
@dataclass(frozen=True)
class Label:
    """What an item shows: the ``marker`` that is drawn and, for a counting scheme, the ``path`` of counters from
    the outermost level down to the item's own (``(2, 1)`` is "2.a"); ``None`` for bullets."""

    marker: str
    path: tuple[int, ...] | None = None

    def to_data(self) -> dict:
        """The plain-data form that is sent to clients: ``{marker, path}``, ``path`` being ``None`` for a bullet."""
        return {"marker": self.marker, "path": None if self.path is None else list(self.path)}


def numbering_labels(entries: Iterable[tuple[str, ListItem | None]], lists: ListBook) -> dict[str, Label]:
    """The label of every list item, from ``(paragraph id, item)`` pairs in document order.

    Counters are per list and per level. An item of level *n* counts one up at level *n* and starts every deeper
    level over. A level nothing has counted yet starts at the list's ``start`` (level 0) or at 1; a missing parent
    counts as that start, so a deleted parent never makes numbering fail. Paragraphs that are not items, and items
    of a list the book does not have, get no label.
    """
    counters: dict[str, list[int]] = {}
    out: dict[str, Label] = {}
    for paragraph_id, item in entries:
        if item is None or item.list not in lists:
            continue
        definition = lists.get(item.list)
        scheme = SCHEMES[definition.scheme]
        if not scheme.counts:
            out[paragraph_id] = Label(scheme.marker(item.level, 0))
            continue
        seen = counters.setdefault(item.list, [0] * (MAX_LIST_LEVEL + 1))
        level = item.level
        seen[level] = seen[level] + 1 if seen[level] else (definition.start if level == 0 else 1)
        for deeper in range(level + 1, MAX_LIST_LEVEL + 1):
            seen[deeper] = 0
        path = tuple(seen[k] or (definition.start if k == 0 else 1) for k in range(level + 1))
        out[paragraph_id] = Label(scheme.marker(level, seen[level]), path)
    return out


# --------------------------------------------------------------------------- commands
@dataclass(frozen=True)
class ListsChanged:
    """The lists of the document changed: all of them (there are few)."""

    lists: tuple[dict, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "lists", "lists": list(self.lists)}


def _book(ctx: Context) -> ListBook:
    book = getattr(ctx.model, "lists", None)
    if not isinstance(book, ListBook):
        raise TypeError(f"The {ctx.model.app} model has no book of lists, so it cannot use list commands")
    return book


def _tell(ctx: Context, book: ListBook) -> None:
    ctx.emit(ListsChanged(tuple(book.to_data())))


def _known(book: ListBook, list_id: str) -> ListDef:
    try:
        return book.get(list_id)
    except KeyError as exc:
        raise ValueError(exc.args[0]) from None


@core_commands.register
@dataclass(frozen=True)
class CreateList(Command):
    """Start a list: it is in the book, and items can belong to it."""

    kind: ClassVar[str] = "core.CreateList"
    list: ListDef

    @property
    def label(self) -> str:
        return "New list"

    @property
    def summary(self) -> str:
        scheme = SCHEMES.get(self.list.scheme)
        return f"started a {'numbered' if scheme and scheme.counts else 'bulleted'} list"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        book.add(self.list)
        _tell(ctx, book)
        return RemoveList(self.list.id)

    def to_data(self) -> dict:
        return self.list.to_data()

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> CreateList:
        return cls(ListDef.from_data(data))


@core_commands.register
@dataclass(frozen=True)
class RemoveList(Command):
    """Take a list out again. Only the undo of :class:`CreateList`: it is refused while an item uses the list."""

    kind: ClassVar[str] = "core.RemoveList"
    list: str

    @property
    def label(self) -> str:
        return "Remove list"

    @property
    def summary(self) -> str:
        return f"took back the list {self.list}"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        known = _known(book, self.list)
        in_use = getattr(ctx.model, "list_in_use", None)
        if in_use is not None and in_use(self.list):
            raise ValueError(f"The list {self.list!r} is in use and cannot be taken back")
        book.remove(self.list)
        _tell(ctx, book)
        return CreateList(known)

    def to_data(self) -> dict:
        return {"list": self.list}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> RemoveList:
        return cls(data["list"])

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, ChangeList) and other.list.id == self.list else self


@core_commands.register
@dataclass(frozen=True)
class ChangeList(Command):
    """Give a list another definition (its scheme, its start, its name); the items keep their list and level."""

    kind: ClassVar[str] = "core.ChangeList"
    list: ListDef

    @property
    def label(self) -> str:
        return "Change list"

    @property
    def summary(self) -> str:
        return f"changed the list {self.list.id}"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        _known(book, self.list.id)
        old = book.replace(self.list)
        _tell(ctx, book)
        return ChangeList(old)

    def to_data(self) -> dict:
        return self.list.to_data()

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> ChangeList:
        return cls(ListDef.from_data(data))

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, ChangeList) and other.list.id == self.list.id else self
