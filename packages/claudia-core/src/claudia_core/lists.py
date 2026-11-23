"""Lists: what makes a paragraph an item, how bullets and numbers are derived, and the book of lists (E9.21).

A list item is *structure*, like a heading level: a paragraph has an :class:`~claudia_core.ListItem` (which list,
which level). Its look stays with its style. What a list adds is a **scheme** (:mod:`claudia_core.schemes`, part of
the document), a named recipe for how the markers of each level are drawn and how far each level is indented.
Markers are never characters of the text.

* A **list** is explicit: a :class:`ListDef` with an id, a scheme, the number to start at and an optional ``name``.
  Items that share a list id are one list, in document order, whatever lies between them; items of two different
  lists never count together, even when they are neighbours. The name is for people (the numbering manager and
  references of E9.22 will show it); nothing here needs it yet.
* **Labels are derived, never stored.** :func:`~claudia_core.numbering_labels` is one pure function from the items,
  in document order, to the label of each: the marker that is drawn (``•``, ``3.``, ``b.``) and, for numbers, the
  trail of counters (``(2, 1)``) and the number a reference to "section 2.1" prints. It is total: a missing parent,
  an unknown list or a missing scheme can never make it fail.
* The :class:`ListBook` is what an app's model holds (an attribute ``lists``); the commands below are the only
  ways to change it, so every change is in the log, can be undone and is seen by everybody. A model may have a
  method ``list_in_use(list_id) -> bool`` that tells :class:`RemoveList` whether an item uses a list.
* :class:`SetListItem` makes any paragraph an item: a paragraph of a composes text or the words of a text box on a
  slide. The model says how it finds the paragraph and what it tells the clients (:class:`ItemHost`).

Every app that has paragraphs can hold lists: the same functions count the items of a composes text and of the
paragraphs in a creates text box.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Protocol

from .commands import Command, CommandRegistry, core_commands
from .errors import Refusal
from .paragraphs import MAX_LIST_LEVEL, ListItem
from .schemes import SchemeBook, builtin_scheme, schemes_of
from .styles import NO_NUMBERING

if TYPE_CHECKING:
    from .context import Context
    from .region import Region

_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_MAX_NAME = 60
_MAX_START = 999_999


# --------------------------------------------------------------------------- the lists
@dataclass(frozen=True)
class ListDef:
    """One list: its ``id``, its ``scheme`` (the id of a :class:`~claudia_core.Scheme` of the document), the number
    its first level starts at, and an optional ``name``."""

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
        if self.id == NO_NUMBERING:
            raise ValueError(f"“{NO_NUMBERING}” says that a style is not numbered; no list can have it as its id")
        if not isinstance(self.scheme, str) or not _ID.fullmatch(self.scheme):
            raise ValueError(f"A list names its scheme by id, got {self.scheme!r}")
        if not isinstance(self.start, int) or not 1 <= self.start <= _MAX_START:
            raise Refusal(
                "A list starts at a number from 1 to {max_start}, got {start!r}", max_start=_MAX_START, start=self.start
            )
        if self.name is not None and (
            not self.name.strip() or len(self.name) > _MAX_NAME or not self.name.isprintable()
        ):
            raise Refusal(
                "A list name is one line of 1 to {max_name} characters, got {name!r}",
                max_name=_MAX_NAME,
                name=self.name,
            )


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
        """Add a list with a new id and sensible numbers. That its scheme exists is the commands' to check: the book
        does not hold the schemes."""
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
    the outermost level down to the item's own (``(2, 1)`` is "2.a") and the ``number`` a reference prints, the whole
    trail without the text around it ("2.a"); both ``None`` for bullets."""

    marker: str
    path: tuple[int, ...] | None = None
    number: str | None = None

    def to_data(self) -> dict:
        """The plain-data form that is sent to clients: ``{marker, path, number}``, the last two ``None`` for a
        bullet."""
        return {"marker": self.marker, "path": None if self.path is None else list(self.path), "number": self.number}


def numbering_labels(
    entries: Iterable[tuple[str, ListItem | None]], lists: ListBook, schemes: SchemeBook
) -> dict[str, Label]:
    """The label of every list item, from ``(paragraph id, item)`` pairs in document order.

    Counters are per list and per level. An item of level *n* counts one up at level *n* and starts every deeper
    level over. A level nothing has counted yet starts at the list's ``start`` (level 0) or at 1; a missing parent
    counts as that start, so a deleted parent never makes numbering fail. Paragraphs that are not items, items of a
    list the book does not have and items of a list whose scheme is gone get no label.
    """
    counters: dict[str, list[int]] = {}
    out: dict[str, Label] = {}
    for paragraph_id, item in entries:
        if item is None or item.list not in lists:
            continue
        definition = lists.get(item.list)
        if definition.scheme not in schemes:
            continue
        scheme = schemes.get(definition.scheme)
        if not scheme.counts:
            out[paragraph_id] = Label(scheme.marker((0,) * (item.level + 1)))
            continue
        seen = counters.setdefault(item.list, [0] * (MAX_LIST_LEVEL + 1))
        level = item.level
        seen[level] = seen[level] + 1 if seen[level] else (definition.start if level == 0 else 1)
        for deeper in range(level + 1, MAX_LIST_LEVEL + 1):
            seen[deeper] = 0
        path = tuple(seen[k] or (definition.start if k == 0 else 1) for k in range(level + 1))
        out[paragraph_id] = Label(scheme.marker(path), path, scheme.number(path))
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


def _scheme_exists(ctx: Context, each: ListDef) -> None:
    schemes = schemes_of(ctx.model)
    if each.scheme not in schemes:
        raise ValueError(f"There is no list scheme {each.scheme!r}; there are {', '.join(schemes.ids())}")


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
        scheme = builtin_scheme(self.list.scheme)  # a summary is read without the document at hand
        if scheme is None:
            return "started a list"
        return f"started a {'numbered' if scheme.counts else 'bulleted'} list"

    def apply(self, ctx: Context) -> Command:
        book = _book(ctx)
        _scheme_exists(ctx, self.list)
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
            raise Refusal("The list {list!r} is in use and cannot be taken back", list=self.list)
        numbered = [style.name for style in getattr(ctx.model, "styles", ()) if style.numbering == self.list]
        if numbered:
            raise Refusal(
                "The list {list!r} numbers the style “{numbered}” and cannot be taken back",
                list=self.list,
                numbered=numbered[0],
            )
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
        _scheme_exists(ctx, self.list)
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


# --------------------------------------------------------------------------- items
class ItemHost(Protocol):
    """What :class:`SetListItem` needs of a model: any of its paragraphs by id, whatever holds it."""

    lists: ListBook

    def item_of(self, paragraph_id: str) -> ListItem | None:
        """The paragraph's own item; ``KeyError`` if there is no such paragraph."""
        ...

    def put_item(self, paragraph_id: str, item: ListItem | None) -> object:
        """Make the paragraph an item as ``item`` says (``None``: no item), and return the event that tells the
        clients. The list exists; the host checks the paragraph does."""
        ...

    def item_regions(self, paragraph_id: str) -> tuple[Region, ...]:
        """What a change of the paragraph's item holds against others' edits."""
        ...


def _items(ctx: Context) -> ItemHost:
    model = ctx.model
    if not all(hasattr(model, name) for name in ("item_of", "put_item", "lists")):
        raise TypeError(f"The {model.app} model has no list items")
    return model


@core_commands.register
@dataclass(frozen=True)
class SetListItem(Command):
    """Make a paragraph an item of a list, at a level, or (``None``) a plain paragraph again (E9.21). Any paragraph:
    one of a composes text, or the words of a text box, so a list runs on across the text boxes of a presentation as
    it does across the paragraphs of a text."""

    kind: ClassVar[str] = "core.SetListItem"
    paragraph: str
    item: ListItem | None

    @property
    def label(self) -> str:
        return "List"

    @property
    def summary(self) -> str:
        return "no longer a list item" if self.item is None else f"list item, level {self.item.level + 1}"

    def apply(self, ctx: Context) -> Command:
        host = _items(ctx)
        if self.item is not None:
            self.item.check()
            _known(host.lists, self.item.list)
        old = host.item_of(self.paragraph)
        ctx.emit(host.put_item(self.paragraph, self.item))
        return SetListItem(self.paragraph, old)

    def to_data(self) -> dict:
        return {"paragraph": self.paragraph, "item": None if self.item is None else self.item.to_data()}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetListItem:
        item = data["item"]
        return cls(data["paragraph"], None if item is None else ListItem.from_data(item))

    def regions(self, model: object) -> tuple[Region, ...]:
        regions = getattr(model, "item_regions", None)
        return () if regions is None else regions(self.paragraph)

    def shifted_by(self, other: Command) -> Command | None:
        return None if other.ends_paragraph(self.paragraph) else self
