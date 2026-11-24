"""Commands for names (E6.5, D600): define, remove, rename — and the one that puts names back, which is what every
other command that changes a name (a structural edit, growing a table, removing a sheet) hands to its undo.

Like every command they carry final values and return their exact inverse."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

from claudia_core import Batch, Command, Context, Refusal

from .commands import SetCells, register
from .events import NamesChanged
from .model import WorkbookModel
from .names import NamedRange, NameKey, key_of
from .refs import SheetId
from .region import CellRegion


def _data(key: NameKey, named: NamedRange | None) -> dict:
    return {"scope": key[0], "name": key[1], "was": None if named is None else named.to_data()}


@WorkbookModel.registry.upcaster("computes.DefineName", 1)
@WorkbookModel.registry.upcaster("computes.RenameName", 1)
def _names_not_yet_shared(data: dict) -> dict:
    """Schema 1 named ranges before they shared the namespace with sheets, charts and objects (D552): replay them under
    the old rule, which let a range and a sheet have one text."""
    return {**data, "legacy_names": True}


@register
@dataclass(frozen=True)
class DefineName(Command):
    """Give cells a name (or, with a name that exists in the same scope, point it somewhere else, which keeps its
    id). The name must be nobody else's in the document (D552); ``legacy_names`` is set for what a log wrote before
    that, and keeps the old rule so that an old document replays."""

    kind: ClassVar[str] = "computes.DefineName"
    schema: ClassVar[int] = 2  # 2: names are shared with sheets, chart tabs (then) and objects, and have ids (D552)
    name: NamedRange
    legacy_names: bool = False

    @property
    def label(self) -> str:
        return "Define table" if self.name.header else "Define name"

    @property
    def summary(self) -> str:
        return f"define {self.name.name}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        named = self.name
        existing = model.names.get(named.key)
        if existing is not None and existing.id != named.id:
            named = replace(named, id=existing.id)  # (the same name pointed somewhere else is still the same thing)
        model.check_name(named, shared=not self.legacy_names)
        if named.anchor is None and named.scope is None and model.pivots.get(named.name) is not None:
            raise Refusal("{name} is a pivot table: change the pivot, not its name", name=named.name)
        before = model.put_names([(named.key, named)])
        ctx.emit(NamesChanged())
        return RestoreNames(tuple(before))

    def to_data(self) -> dict:
        data: dict = {"name": self.name.to_data()}
        if self.legacy_names:
            data["legacy_names"] = True
        return data

    @classmethod
    def from_data(cls, data, registry) -> DefineName:
        return cls(NamedRange.from_data(data["name"]), data.get("legacy_names", False))

    def regions(self, model) -> tuple[CellRegion, ...]:
        area = self.name.range
        return () if area is None else (CellRegion(area),)

    def shifted_by(self, other: Command) -> Command | None:
        return None if _touches(other, self.name.key, self.name.sheet) else self


@register
@dataclass(frozen=True)
class RemoveName(Command):
    """Take a name away; the cells stay, the formulas that used it become ``#NAME?``."""

    kind: ClassVar[str] = "computes.RemoveName"
    scope: SheetId | None
    name: str

    @property
    def label(self) -> str:
        return "Remove name"

    @property
    def summary(self) -> str:
        return f"remove {self.name}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        key = key_of(self.scope, self.name)
        if model.names.get(key) is None:
            raise ValueError(f"there is no name {self.name!r}")
        if self.scope is None and model.pivots.get(self.name) is not None:
            raise Refusal("{name} is a pivot table: delete the pivot, not its name", name=self.name)
        before = model.put_names([(key, None)])
        ctx.emit(NamesChanged())
        return RestoreNames(tuple(before))

    def to_data(self) -> dict:
        return {"scope": self.scope, "name": self.name}

    @classmethod
    def from_data(cls, data, registry) -> RemoveName:
        return cls(None if data.get("scope") is None else SheetId(data["scope"]), data["name"])

    def shifted_by(self, other: Command) -> Command | None:
        return None if _touches(other, key_of(self.scope, self.name), None) else self


@register
@dataclass(frozen=True)
class RenameName(Command):
    """Call a name something else. The formulas that use it are rewritten, so they keep meaning the same cells."""

    kind: ClassVar[str] = "computes.RenameName"
    schema: ClassVar[int] = 2  # 2: the new name must be nobody else's in the document (D552); see ``DefineName``
    scope: SheetId | None
    old: str
    new: str
    legacy_names: bool = False

    @property
    def label(self) -> str:
        return "Rename name"

    @property
    def summary(self) -> str:
        return f"rename {self.old} to {self.new}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        if self.scope is None and ctx.model.pivots.get(self.old) is not None:
            raise Refusal("{old} is a pivot table: a pivot keeps its name", old=self.old)
        restores = ctx.model.rename_name(self.scope, self.old, self.new, shared=not self.legacy_names)
        ctx.emit(NamesChanged())
        undo: list[Command] = [RenameName(self.scope, self.new, self.old)]
        # (the formulas come back as they were typed: writing the old name back would print them by its own case)
        undo.extend(SetCells(sheet, tuple(sorted(items, key=lambda t: t[:2]))) for sheet, items in restores.items())
        return undo[0] if len(undo) == 1 else Batch(tuple(undo))

    def to_data(self) -> dict:
        data: dict = {"scope": self.scope, "old": self.old, "new": self.new}
        if self.legacy_names:
            data["legacy_names"] = True
        return data

    @classmethod
    def from_data(cls, data, registry) -> RenameName:
        scope = None if data.get("scope") is None else SheetId(data["scope"])
        return cls(scope, data["old"], data["new"], data.get("legacy_names", False))

    def shifted_by(self, other: Command) -> Command | None:
        old, new = key_of(self.scope, self.old), key_of(self.scope, self.new)
        return None if _touches(other, old, None) or _touches(other, new, None) else self


@register
@dataclass(frozen=True)
class RestoreNames(Command):
    """Put names back as they were: for each ``(key, name)`` the name is set, or taken out when ``name`` is ``None``.
    What undoes a change to a name, whichever command made it."""

    kind: ClassVar[str] = "computes.RestoreNames"
    entries: tuple[tuple[NameKey, NamedRange | None], ...]

    @property
    def label(self) -> str:
        return "Restore names"

    @property
    def summary(self) -> str:
        return "restore " + ", ".join(named.name if named else key[1] for key, named in self.entries[:3])

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        before = ctx.model.put_names(list(self.entries))
        ctx.emit(NamesChanged())
        return RestoreNames(tuple(reversed(before)))  # (reversed: a key listed twice is restored in the other order)

    def to_data(self) -> dict:
        return {"entries": [_data(key, named) for key, named in self.entries]}

    @classmethod
    def from_data(cls, data, registry) -> RestoreNames:
        entries = []
        for item in data["entries"]:
            scope = None if item.get("scope") is None else SheetId(item["scope"])
            was = None if item["was"] is None else NamedRange.from_data(item["was"])
            entries.append(((scope, item["name"]), was))
        return cls(tuple(entries))

    def shifted_by(self, other: Command) -> Command | None:
        sheets = {named.sheet for _, named in self.entries if named is not None}
        return None if any(_touches(other, key, None, sheets) for key, _ in self.entries) else self


def _touches(other: Command, key: NameKey, sheet: SheetId | None, sheets: set[SheetId] | None = None) -> bool:
    """Whether ``other``, done after a name command, makes the name command mean something else or nothing: it
    changed the same name, or moved the cells the name is on."""
    from .commands import RemoveSheet, Structure

    where = {sheet} if sheet is not None else set()
    where |= sheets or set()
    if isinstance(other, Structure):
        return other.edit.sheet in where
    if isinstance(other, RemoveSheet):
        return other.id in where
    if isinstance(other, DefineName):
        return other.name.key == key
    if isinstance(other, RemoveName):
        return key_of(other.scope, other.name) == key
    if isinstance(other, RenameName):
        return key in (key_of(other.scope, other.old), key_of(other.scope, other.new))
    if isinstance(other, RestoreNames):
        return any(entry_key == key for entry_key, _ in other.entries)
    return False
