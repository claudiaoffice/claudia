"""The asset store (D1431): what objects show that the document keeps once, by id.

An *asset* is an image, a shape's outline, a chart's definition (``diagram``), a container's definition
(``rendering``) or a table. Objects point at one by id (``ObjectBody.ref``), so several objects — and in computes a
chart tab — can show the same one. "Asset" is a word of the code only; people never see it.

The five kinds are kept alike: one :class:`AssetStore` per kind on the object model
(:class:`~claudia_core.ObjectModel`), one change event (:class:`AssetsChanged`) and one set of commands
(:mod:`claudia_core.asset_commands`). What really differs between the kinds is data on its :class:`AssetKind`: how one
is read from plain data, whether it may be changed in place, an extra check, and what a redacted step keeps of it.
Tables are edited box by box and keep their own commands (:mod:`claudia_core.table_commands`); they share the store.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .assets import ImageAsset
from .renderings import RenderedDefinition
from .shapes import ShapeDefinition
from .tables import TableDef


class Asset(Protocol):
    """What every asset has: an id unique among its kind, and a plain-data form."""

    @property
    def id(self) -> str: ...

    def to_data(self) -> dict: ...


@dataclass(frozen=True)
class AssetKind:
    """One kind of asset and what is its own about it.

    ``name`` is the kind as the stored form, the steps and the change event call it; ``object_kind`` the kind of
    object that shows it. ``read(model, data)`` makes one from plain data (a chart's definition through the app).
    ``editable`` says it may be replaced in place. ``check(model, new, old)`` refuses one that cannot be in the
    document (``old`` is ``None`` when it is defined). ``blank(model_class, data)`` is what a redacted step keeps of
    it (``None``: what it holds is not anybody's words). ``event_key`` names it in the change event's plain data."""

    name: str
    object_kind: str
    noun: str
    read: Callable[[Any, dict], Asset]
    editable: bool = False
    check: Callable[[Any, Any, Any], None] | None = None
    blank: Callable[[Any, dict], dict] | None = None
    event_key: str = "definition"
    in_use: str = "is in use by"


def _check_rendering(model: Any, new: RenderedDefinition, old: RenderedDefinition | None) -> None:
    if old is not None and new.type != old.type:
        raise ValueError("a rendering cannot change its type: make another container")
    if new.image is not None and new.image not in model.images:
        raise ValueError(f"this document does not know the image {new.image!r}")


IMAGE = AssetKind(
    "image",
    "image",
    "image",
    lambda _model, data: ImageAsset.from_data(data),
    blank=lambda _model, data: ImageAsset.from_data(data).blanked().to_data(),
    event_key="asset",
)
SHAPE = AssetKind("shape", "shape", "shape", lambda _model, data: ShapeDefinition.from_data(data))
DIAGRAM = AssetKind(
    "diagram",
    "diagram",
    "diagram",
    lambda model, data: model.diagram_from_data(data),
    editable=True,
    # only the app knows what in a chart is anybody's words: without its model nothing is taken away
    blank=lambda model, data: data if model is None else model.blank_diagram(data),
)
RENDERING = AssetKind(
    "rendering",
    "rendered",
    "rendered text",
    lambda _model, data: RenderedDefinition.from_data(data),
    editable=True,
    check=_check_rendering,
    blank=lambda _model, data: RenderedDefinition.from_data(data).redacted().to_data(),
)
TABLE = AssetKind(
    "table",
    "table",
    "table",
    lambda _model, data: TableDef.from_data(data),
    editable=True,
    check=lambda model, new, _old: model.check_table(new),
    in_use="is shown by",
)

#: Every kind, in the order a stored document is read back: a container's picture is an image, so images come first.
ASSET_KINDS: tuple[AssetKind, ...] = (TABLE, SHAPE, IMAGE, DIAGRAM, RENDERING)
KIND_BY_NAME: Mapping[str, AssetKind] = {kind.name: kind for kind in ASSET_KINDS}
KIND_BY_OBJECT: Mapping[str, AssetKind] = {kind.object_kind: kind for kind in ASSET_KINDS}


def asset_kind(name: str) -> AssetKind:
    """The kind called ``name``; ``ValueError`` for a name that is none."""
    try:
        return KIND_BY_NAME[name]
    except KeyError:
        raise ValueError(f"there is no kind of asset called {name!r}") from None


class AssetStore[T: Asset](Mapping[str, T]):
    """The assets of one kind a document keeps, by id. Read it like a dict; change it only through its methods.

    ``model`` is the object model it belongs to: it reads a kind that needs the app (a chart), checks against the rest
    of the document, and says who uses an asset (:meth:`~claudia_core.ObjectModel.users_of`)."""

    def __init__(self, kind: AssetKind, model: Any) -> None:
        self.kind = kind
        self._model = model
        self._items: dict[str, T] = {}

    def __getitem__(self, asset_id: str) -> T:
        return self._items[asset_id]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def known(self, asset_id: str) -> T:
        """The asset with this id; ``ValueError`` if the document has none."""
        try:
            return self._items[asset_id]
        except KeyError:
            raise ValueError(f"this document does not know the {self.kind.name} {asset_id!r}") from None

    def define(self, asset: T) -> None:
        """Take a checked asset into the document."""
        if asset.id in self._items:
            raise ValueError(f"{self.kind.name} {asset.id!r} is already defined in this document")
        if self.kind.check is not None:
            self.kind.check(self._model, asset, None)
        self._items[asset.id] = asset

    def replace(self, asset: T) -> T:
        """Swap in a changed, checked version of an asset that exists (its id stays); returns the one it replaces."""
        if not self.kind.editable:
            raise ValueError(f"a {self.kind.name} is not changed in place: define another one")
        old = self.known(asset.id)
        if self.kind.check is not None:
            self.kind.check(self._model, asset, old)
        self._items[asset.id] = asset
        return old

    def users(self, asset_id: str) -> list[str]:
        """The ids of what uses this asset (:meth:`~claudia_core.ObjectModel.users_of`)."""
        return self._model.users_of(self.kind, asset_id)

    def forget(self, asset_id: str) -> T:
        """Let go of an asset nothing uses; returns it."""
        self.known(asset_id)
        users = self.users(asset_id)
        if users:
            raise ValueError(f"{self.kind.name} {asset_id!r} {self.kind.in_use} {users[0]!r}")
        return self._items.pop(asset_id)

    def put(self, asset: T) -> None:
        """Keep ``asset`` without checking it: for a document read back or blanked, which held together before."""
        self._items[asset.id] = asset

    def to_data(self) -> list[dict]:
        """Every asset, by id: what a stored document keeps."""
        return [asset.to_data() for _, asset in sorted(self._items.items())]

    def restore(self, stored: Iterable[dict]) -> None:
        """Put back what :meth:`to_data` stored."""
        for data in stored:
            self.put(self.kind.read(self._model, data))  # type: ignore[arg-type]


@dataclass(frozen=True)
class AssetsChanged:
    """The document learned an asset (``asset`` is it), changed one in place (the new one, same id) or forgot one
    (``asset`` is ``None``)."""

    kind: AssetKind
    asset_id: str
    asset: Asset | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": self.kind.name,
            "id": self.asset_id,
            self.kind.event_key: None if self.asset is None else self.asset.to_data(),
        }
