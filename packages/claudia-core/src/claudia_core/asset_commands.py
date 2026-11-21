"""The three commands every asset kind is defined, changed and forgotten with (D1431).

``asset_kind`` names the kind (:data:`claudia_core.asset_store.ASSET_KINDS`); ``data`` is the asset as plain data,
which the kind reads back when the command runs (a chart's definition through the app). A table has commands of its
own (:mod:`claudia_core.table_commands`), since it is edited box by box, and is refused here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from .asset_store import TABLE, AssetKind, AssetsChanged, AssetStore, asset_kind
from .commands import Command, CommandRegistry, core_commands
from .objects import AddObject, host_of

if TYPE_CHECKING:
    from .context import Context
    from .model import DocumentModel


def _commanded(name: str) -> AssetKind:
    kind = asset_kind(name)
    if kind is TABLE:
        raise ValueError("a table is defined and forgotten by the table commands")
    return kind


def _store(ctx: Context, kind: AssetKind) -> AssetStore:
    return host_of(ctx).assets[kind.name]


def _a(noun: str) -> str:
    return f"{'an' if noun[0] in 'aeiou' else 'a'} {noun}"


def _blanked(kind: AssetKind, model: type[DocumentModel] | None, data: dict) -> dict:
    """What a redacted step keeps of ``data``."""
    return data if kind.blank is None else kind.blank(model, data)


@core_commands.register
@dataclass(frozen=True)
class DefineAsset(Command):
    """Take an asset into the document, so that it opens the same anywhere."""

    kind: ClassVar[str] = "core.DefineAsset"
    asset_kind: str
    data: dict

    @property
    def label(self) -> str:
        return f"Define {_commanded(self.asset_kind).noun}"

    @property
    def summary(self) -> str:
        return f"The document takes {_a(_commanded(self.asset_kind).noun)}"

    def apply(self, ctx: Context) -> Command:
        kind = _commanded(self.asset_kind)
        store = _store(ctx, kind)
        asset = kind.read(host_of(ctx), self.data)
        store.define(asset)
        ctx.emit(AssetsChanged(kind, asset.id, asset))
        return ForgetAsset(kind.name, asset.id)

    def to_data(self) -> dict:
        return {"asset_kind": self.asset_kind, "data": dict(self.data)}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> DefineAsset:
        return cls(data["asset_kind"], dict(data["data"]))

    def shifted_by(self, other: Command) -> Command | None:
        """Refuse when a colleague defined the same asset since."""
        mine = (self.asset_kind, self.data.get("id"))
        return None if isinstance(other, DefineAsset) and (other.asset_kind, other.data.get("id")) == mine else self

    def redacted(self) -> Command:
        return self.redacted_in(None)

    def redacted_in(self, model: type[DocumentModel] | None) -> Command:
        return DefineAsset(self.asset_kind, _blanked(_commanded(self.asset_kind), model, self.data))


@core_commands.register
@dataclass(frozen=True)
class UpdateAsset(Command):
    """Change an asset in place (its id stays): a chart's range or titles, a container's text and picture. Only the
    kinds meant to be edited after the fact are; an image or a shape is forgotten and defined anew instead."""

    kind: ClassVar[str] = "core.UpdateAsset"
    asset_kind: str
    id: str
    data: dict

    @property
    def label(self) -> str:
        return f"Edit {_commanded(self.asset_kind).noun}"

    @property
    def summary(self) -> str:
        return f"Edited {_a(_commanded(self.asset_kind).noun)}"

    def apply(self, ctx: Context) -> Command:
        kind = _commanded(self.asset_kind)
        new = kind.read(host_of(ctx), self.data)
        if new.id != self.id:
            raise ValueError(f"a {kind.name} cannot change its id")
        old = _store(ctx, kind).replace(new)
        ctx.emit(AssetsChanged(kind, self.id, new))
        return UpdateAsset(kind.name, self.id, old.to_data())

    def to_data(self) -> dict:
        return {"asset_kind": self.asset_kind, "id": self.id, "data": dict(self.data)}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> UpdateAsset:
        return cls(data["asset_kind"], data["id"], dict(data["data"]))

    def shifted_by(self, other: Command) -> Command | None:
        """Never destroy what a colleague has done to the asset since (changed it again, or forgotten it)."""
        if isinstance(other, UpdateAsset | ForgetAsset) and (other.asset_kind, other.id) == (self.asset_kind, self.id):
            return None
        return self

    def redacted(self) -> Command:
        return self.redacted_in(None)

    def redacted_in(self, model: type[DocumentModel] | None) -> Command:
        return UpdateAsset(self.asset_kind, self.id, _blanked(_commanded(self.asset_kind), model, self.data))


@core_commands.register
@dataclass(frozen=True)
class ForgetAsset(Command):
    """Let go of an asset nothing uses (the undo of :class:`DefineAsset`)."""

    kind: ClassVar[str] = "core.ForgetAsset"
    asset_kind: str
    id: str

    @property
    def label(self) -> str:
        return f"Forget {_commanded(self.asset_kind).noun}"

    @property
    def summary(self) -> str:
        return f"The document lets go of the {_commanded(self.asset_kind).noun} {self.id}"

    def apply(self, ctx: Context) -> Command:
        kind = _commanded(self.asset_kind)
        asset = _store(ctx, kind).forget(self.id)
        ctx.emit(AssetsChanged(kind, self.id, None))
        return DefineAsset(kind.name, asset.to_data())

    def to_data(self) -> dict:
        return {"asset_kind": self.asset_kind, "id": self.id}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> ForgetAsset:
        return cls(data["asset_kind"], data["id"])

    def shifted_by(self, other: Command) -> Command | None:
        """Refuse when a colleague now uses the asset, or defined it anew."""
        kind = _commanded(self.asset_kind)
        if isinstance(other, AddObject) and other.body.kind == kind.object_kind and other.body.ref == self.id:
            return None
        if isinstance(other, DefineAsset) and other.asset_kind == self.asset_kind and other.data.get("id") == self.id:
            return None
        return self

    def redacted(self) -> Command:
        return self
