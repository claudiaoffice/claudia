"""The shared object layer: shapes, text boxes and images, in every app (E10.16, D177).

An object is two things, and keeping them apart is the whole point of this module:

* a **body** (:class:`~claudia_core.ObjectBody`) — what it is and how it looks: its kind, its size, its
  style, the words in it, the shape outline or image asset it draws, how far it is turned. Identical in all
  three apps, so a shape made in creates is the same body as a shape made in composes, and moving one
  between apps is a matter of its anchor alone.
* an **anchor** — *where* it sits, which only its own app understands: a point on a slide (creates), a cell
  of a sheet (computes), a place in a paragraph (composes). The :class:`~claudia_core.Anchor` protocol is
  all the kernel and the shared commands ever need of it.

:class:`~claudia_core.VisualObject` is the pair. :class:`~claudia_core.ObjectModel` is the mixin an app's
model inherits to hold objects, their stacking order, their shape outlines and their image assets. The
commands below — define and forget a shape or an image, add, remove, move, resize, retext, rotate, snap and
describe an object — are written once, against the anchor protocol, and are the same command in every app.

An anchor crosses the wire and the log as plain data, exactly as a :class:`~claudia_core.Region` does, and is
read back by the one app-specific door, :meth:`~claudia_core.ObjectModel.anchor_from_data`. A command
therefore stays what the kernel requires it to be: immutable plain data, buildable without a model.

What an app brings: its anchor type, ``containers()``, ``check_anchor``, ``anchor_from_data``, and whatever its
own geometry needs. What it does *not* bring is its own copy of place-an-object, take-it-away, stack-it, size-it
or style-it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, Self, TypeIs, runtime_checkable

from .assets import MAX_ALT_CHARS, ImageAsset, ImageImport
from .commands import Batch, Command, CommandRegistry, core_commands
from .facets import SLOTS, fits
from .fields import FIELD_CHAR, Field, plain
from .generated import Generated
from .names import clean_name, name_key, name_problem
from .paragraphs import ListItem, Paragraph, Run
from .renderings import RenderedDefinition
from .shapes import ShapeDefinition
from .tables import FILLER, TableDef, parse_entry_id

if TYPE_CHECKING:
    from .context import Context
    from .model import DocumentModel

#: Kinds of object every app understands. A text box carries only words; a shape carries an outline and may carry
#: words; an image carries an asset; a diagram carries a :class:`DiagramDefinition` (E6.6) — what it draws is
#: opaque to the kernel, the same way an anchor's own geometry is (see :class:`DiagramDefinition`); a rendered
#: container carries a :class:`~claudia_core.RenderedDefinition` — text that something outside the document turns
#: into a picture (D390); a table carries a :class:`~claudia_core.TableDef` (D1201).
OBJECT_KINDS: tuple[str, ...] = ("text", "shape", "image", "diagram", "rendered", "table")

MIN_OBJECT_SIZE = 20  # an object is at least this wide and this tall, in its app's own units
MAX_OBJECTS_PER_CONTAINER = 500
MAX_SELECTION = 64  # objects in one selection that arrives from a client
ASPECT_TOLERANCE = 1  # units a width may differ from height * aspect (whole units cannot match exactly)
MAX_LISTED_TEXT = 40  # characters of an object's text that a history sentence quotes

_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}")
_BODY_FIELDS = (
    "id",
    "kind",
    "w",
    "h",
    "style",
    "paragraph",
    "ref",
    "imported",
    "rotation",
    "snap",
    "description",
    "decorative",
    "name",
)
#: Bodies were once written with one pointer field per kind (``shape``, ``image``, ``diagram``, ``rendered``,
#: ``table``) and grew a generation of field sets with each new field. They still read: the pointer that matches the
#: body's kind becomes ``ref``, and any other pointer that is set is refused. Nothing new is ever added to this list;
#: a new kind of object uses ``ref`` and needs no field of its own.
# The kinds that do not turn, and what the sentence calls them (D1021: a chart; D1224: a table).
_NOT_TURNED = {"diagram": "chart", "table": "table"}
_LEGACY_POINTERS = ("shape", "image", "diagram", "rendered", "table")
_LEGACY_SETS = (
    frozenset(
        (
            *(f for f in _BODY_FIELDS if f != "ref"),
            *_LEGACY_POINTERS,
        )
    ),
    frozenset((*(f for f in _BODY_FIELDS if f != "ref"), *_LEGACY_POINTERS[:4])),
    frozenset((*(f for f in _BODY_FIELDS if f not in ("ref", "name")), *_LEGACY_POINTERS[:4])),
    frozenset((*(f for f in _BODY_FIELDS if f not in ("ref", "name")), *_LEGACY_POINTERS[:3])),
    frozenset(
        (*(f for f in _BODY_FIELDS if f not in ("ref", "name", "description", "decorative")), *_LEGACY_POINTERS[:3])
    ),
)


def _is_whole(value: object) -> TypeIs[int]:
    """``True`` for a plain ``int`` (not a ``bool``), narrowing the type for the caller."""
    return type(value) is int


def paragraph_for(object_id: str, style: str, text: str = "", author: str | None = None) -> Paragraph:
    """The paragraph a new text box or shape starts with: the object's own id (it is the only paragraph in there,
    so nothing else can collide with it) and ``style``, the style of the object's words — a paragraph style, not
    the object's own box or outline style (D304, D310)."""
    return Paragraph(object_id, style, text).written_by(author)


def object_styles(body: ObjectBody) -> tuple[str, ...]:
    """The styles an object uses, one per slot: its own, then its words' if it has any (D304)."""
    return (body.style,) if body.paragraph is None else (body.style, body.paragraph.style)


def _quote(text: str) -> str:
    """A short, one-line piece of an object's text for a sentence in the history."""
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= MAX_LISTED_TEXT else flat[: MAX_LISTED_TEXT - 1] + "…"


# --------------------------------------------------------------------------- the anchor seam
@runtime_checkable
class Anchor(Protocol):
    """Where an object sits, in the terms of one app only (see the module description).

    ``container`` is the thing the object belongs to — a slide, a sheet, a paragraph — by id. The kernel uses it
    to group objects for events and locks; it never interprets it. ``to_data`` must round-trip through the app's
    :meth:`~claudia_core.ObjectModel.anchor_from_data`."""

    kind: ClassVar[str]

    @property
    def container(self) -> str:
        """The id of the slide, sheet or paragraph this object belongs to."""

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""


# --------------------------------------------------------------------------- the diagram seam
@runtime_checkable
class DiagramDefinition(Protocol):
    """What a diagram draws, in the terms of one app only (E6.6) — a chart's cell range, series direction and
    titles (computes); another app may one day give it a different shape entirely.

    This is the same split the module description draws between a body and an anchor, applied to a *kind's*
    own data instead of its placement: the kernel stores a definition by ``id`` and asks only whether one an
    object still points at exists — never what is inside it. ``to_data`` must round-trip through the app's own
    :meth:`~claudia_core.ObjectModel.diagram_from_data`, the one door this data enters through, exactly as an
    anchor does. A definition is referenced by ``id`` from :attr:`ObjectBody.diagram` (a floating diagram
    object) or from whatever other, app-specific place an app surfaces the same drawing (a tab, say) — the same
    way an image asset is referenced by both an object and, one day, something else that reuses it."""

    @property
    def id(self) -> str:
        """The id this definition is stored and referenced under."""

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""


# --------------------------------------------------------------------------- the body
@dataclass(frozen=True)
class ObjectBody:
    """What an object is and how it looks, the same in all three apps.

    ``kind`` is one of ``OBJECT_KINDS``. ``w`` and ``h`` are the size in the app's own units. ``style`` is the
    id of a style in the document's :class:`~claudia_core.StyleBook`, which is where *the object's* colours and
    border come from — its ``fill``, ``stroke`` and ``stroke-width`` (D178).

    ``paragraph`` is the words in it: a :class:`~claudia_core.Paragraph`, the same entity composes uses for a
    paragraph of a document (E10.17, D181), so a shape's label has a paragraph style, an alignment and per-author
    runs like any other text in the suite. A text box always has one, a shape may, an image never (``None``).
    The paragraph's own ``style`` says what the *words* look like, separately from the object's.
    ``ref`` is the id of the definition the kind points at, in the document's own tables of definitions: a
    ``shape`` object's outline (:class:`~claudia_core.ShapeDefinition`), an ``image``'s asset
    (:class:`~claudia_core.ImageAsset`), a ``diagram``'s :class:`DiagramDefinition` (E6.6, opaque to the kernel, the
    way an anchor is), a ``rendered`` container's :class:`~claudia_core.RenderedDefinition` (the text it is made from
    and the picture last made of it, D390) and a ``table``'s :class:`~claudia_core.TableDef` (D1201). A text box
    points at nothing (``None``). The kind says which table ``ref`` is looked up in, so one field serves every kind
    and a new kind of object needs no new field. :attr:`shape`, :attr:`image`, :attr:`diagram`, :attr:`rendered` and
    :attr:`table` read it by kind. ``imported`` is the record of how an image got there.
    ``rotation`` is whole degrees clockwise. ``snap`` is whether the object holds to its app's grid (E10.15,
    D214): the grid is a helper the view draws, but each object's own choice to follow it is real, persisted
    document state.

    ``name`` is what people call the object (D550): unique among everything in the document that has a name, and
    ``""`` only for a body that has none yet (the server gives every new object one).

    ``description`` is what the object says to someone who cannot see it, and ``decorative`` says it has nothing to
    say (a flourish, a divider): a decorative object has no description. Both are the same in every kind of
    object, and a screen reader, a tagged PDF and an office file each get them from here. A picture that has no
    description of its own is described by the words it was imported with."""

    id: str
    kind: str
    w: int
    h: int
    style: str
    paragraph: Paragraph | None = None
    ref: str | None = None
    imported: ImageImport | None = None
    rotation: int = 0
    snap: bool = True
    description: str = ""
    decorative: bool = False
    name: str = ""

    def __post_init__(self) -> None:
        if self.imported is not None and not self.description and not self.decorative:
            object.__setattr__(self, "description", self.imported.alt)

    def _pointing(self, kind: str) -> str | None:
        return self.ref if self.kind == kind else None

    @property
    def shape(self) -> str | None:
        """The id of the outline, if this is a shape."""
        return self._pointing("shape")

    @property
    def image(self) -> str | None:
        """The id of the image asset, if this is an image."""
        return self._pointing("image")

    @property
    def diagram(self) -> str | None:
        """The id of the diagram definition, if this is a diagram."""
        return self._pointing("diagram")

    @property
    def rendered(self) -> str | None:
        """The id of the rendered container's definition, if this is one."""
        return self._pointing("rendered")

    @property
    def table(self) -> str | None:
        """The id of the table definition, if this is a table."""
        return self._pointing("table")

    def to_data(self) -> dict:
        """The plain-data form: what the log stores. Carries ``imported`` unmasked (the log is not a client)."""
        skip = ("imported", "paragraph")
        data: dict[str, Any] = {name: getattr(self, name) for name in _BODY_FIELDS if name not in skip}
        data["imported"] = None if self.imported is None else self.imported.to_data()
        data["paragraph"] = None if self.paragraph is None else self.paragraph.to_data()
        return data

    def to_data_for(self, viewer: str) -> dict:
        """What ``viewer`` is sent: as :meth:`to_data`, but an image's import record is masked for anyone but the
        person who imported it (a colleague sees "imported from disk", not the importer's own filesystem path)."""
        data = self.to_data()
        if self.imported is not None:
            data["imported"] = self.imported.masked(viewer).to_data()
        return data

    @classmethod
    def from_data(cls, data: dict) -> ObjectBody:
        """Inverse of :meth:`to_data`; whether the values make sense is the model's business
        (:meth:`~claudia_core.ObjectModel.check_object`). A body written with one field per kind (see
        ``_LEGACY_POINTERS``) reads too."""
        fields = frozenset(data)
        if fields in _LEGACY_SETS:
            data = cls._from_legacy(data)
        elif fields != frozenset(_BODY_FIELDS):
            raise ValueError("an object body has exactly these fields: " + ", ".join(_BODY_FIELDS))
        imported, paragraph = data["imported"], data["paragraph"]
        return cls(
            **{
                **data,
                "imported": None if imported is None else ImageImport.from_data(imported),
                "paragraph": None if paragraph is None else Paragraph.from_data(paragraph),
            }
        )

    @staticmethod
    def _from_legacy(data: dict) -> dict:
        """The same body with the one pointer field of its kind as ``ref``; ``ValueError`` if a pointer of another
        kind is set, which no checked body ever had."""
        kind = data["kind"]
        stray = [name for name in _LEGACY_POINTERS if name in data and name != kind and data[name] is not None]
        if stray:
            raise ValueError(f"a {kind} object has no {stray[0]}")
        current = {name: value for name, value in data.items() if name not in _LEGACY_POINTERS}
        current["ref"] = data.get(kind) if kind in _LEGACY_POINTERS else None
        return current


@dataclass(frozen=True)
class VisualObject[A: Anchor]:
    """One object: an :class:`~claudia_core.ObjectBody` and the :class:`~claudia_core.Anchor` that says where it sits.

    The body is the same type in every app; ``A`` is the app's own anchor. Everything the three apps share is
    reached through ``obj.body``, everything only one app knows through ``obj.anchor``."""

    body: ObjectBody
    anchor: A

    @property
    def id(self) -> str:
        """The object's id (its body's)."""
        return self.body.id

    @property
    def container(self) -> str:
        """The slide, sheet or paragraph this object belongs to (its anchor's)."""
        return self.anchor.container

    def with_body(self, **changes: Any) -> Self:
        """The same object with these body fields changed."""
        return replace(self, body=replace(self.body, **changes))

    def to_data(self) -> dict:
        """The plain-data form: the body's fields plus ``anchor``, the one app-specific part."""
        return {**self.body.to_data(), "anchor": self.anchor.to_data()}

    def to_data_for(self, viewer: str) -> dict:
        """What ``viewer`` is sent (see :meth:`ObjectBody.to_data_for`)."""
        return {**self.body.to_data_for(viewer), "anchor": self.anchor.to_data()}

    @classmethod
    def from_data(cls, data: dict, read_anchor: ReadAnchor[A]) -> VisualObject[A]:
        """Inverse of :meth:`to_data`. ``read_anchor`` is the app's own anchor reader
        (:meth:`~claudia_core.ObjectModel.anchor_from_data`), the single place an app's geometry enters."""
        if "anchor" not in data:
            raise ValueError("an object has an anchor")
        body = {name: value for name, value in data.items() if name != "anchor"}
        return VisualObject(ObjectBody.from_data(body), read_anchor(data["anchor"]))


class ReadAnchor[A: Anchor](Protocol):
    """Reads one app's anchor from its plain-data form."""

    def __call__(self, data: dict) -> A: ...


# --------------------------------------------------------------------------- the region
@dataclass(frozen=True)
class ObjectSet:
    """Some objects of one container (a selection, an area the AI is working on). It is also what a lock holds
    (D67). The same :class:`~claudia_core.Region` in all three apps: objects are named by id, and which container
    they live in is the anchor's business, not this one's."""

    kind: ClassVar[str] = "objects"
    container: str
    ids: frozenset[str] = frozenset()

    def overlaps(self, other: object) -> bool:
        """Do the two selections share an object of the same container?"""
        return isinstance(other, ObjectSet) and self.container == other.container and bool(self.ids & other.ids)

    def transformed(self, command: Command) -> ObjectSet | None:
        """The selection after a command: it loses an object that was removed, and is gone when none is left."""
        if isinstance(command, RemoveObject) and command.id in self.ids:
            rest = self.ids - {command.id}
            return ObjectSet(self.container, rest) if rest else None
        return self

    def to_data(self) -> dict:
        """The plain-data form for the wire (regions are never stored in the log)."""
        return {"kind": self.kind, "container": self.container, "ids": sorted(self.ids)}

    @classmethod
    def from_data(cls, data: dict) -> ObjectSet:
        """Read a selection sent by a client; ``ValueError`` if it is not one."""
        container, ids = data.get("container"), data.get("ids")
        if not isinstance(container, str) or not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ValueError("not a selection: it names a container and a list of object ids")
        if len(ids) > MAX_SELECTION:
            raise ValueError(f"a selection holds at most {MAX_SELECTION} objects")
        return cls(container, frozenset(ids))


# --------------------------------------------------------------------------- the events
@dataclass(frozen=True)
class ThingRenamed:
    """A thing (an object, a slide, a sheet, a chart tab) was given another name (D550): its id and its new name."""

    id: str
    name: str

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {"type": "thing_renamed", "id": self.id, "name": self.name}


@dataclass(frozen=True)
class ObjectsChanged:
    """Objects of one container changed. ``changed`` are their new state (added or altered), ``removed`` their
    ids, and ``order`` is the stacking order of the whole container afterwards (bottom first), so a view needs
    no query."""

    container: str
    changed: tuple[VisualObject, ...]
    removed: tuple[str, ...]
    order: tuple[str, ...]

    def to_data(self) -> dict:
        """The plain-data form of the event. Carries every ``changed`` object's import record unmasked; a client
        that goes straight to this (rather than through :meth:`to_data_for`) is trusted with the full record, as
        the log is."""
        return {
            "type": "objects",
            "container": self.container,
            "changed": [obj.to_data() for obj in self.changed],
            "removed": list(self.removed),
            "order": list(self.order),
        }

    def to_data_for(self, viewer: str) -> dict:
        """What ``viewer`` is sent: as :meth:`to_data`, with each changed image's import record masked for anyone
        but the person who imported it (``hub.py`` calls this per connection when an event offers it)."""
        return {**self.to_data(), "changed": [obj.to_data_for(viewer) for obj in self.changed]}


@dataclass(frozen=True)
class ImagesChanged:
    """The document learned an image (``asset`` is it) or forgot one (``asset`` is ``None``)."""

    image_id: str
    asset: ImageAsset | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "image",
            "id": self.image_id,
            "asset": None if self.asset is None else self.asset.to_data(),
        }


@dataclass(frozen=True)
class ShapesChanged:
    """The document learned a shape (``definition`` is it) or forgot one (``definition`` is ``None``)."""

    shape_id: str
    definition: ShapeDefinition | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "shape",
            "id": self.shape_id,
            "definition": None if self.definition is None else self.definition.to_data(),
        }


@dataclass(frozen=True)
class DiagramsChanged:
    """The document learned a diagram definition (``definition`` is it), forgot one (``definition`` is ``None``),
    or redefined one in place (``definition`` is the new one, same id)."""

    diagram_id: str
    definition: DiagramDefinition | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "diagram",
            "id": self.diagram_id,
            "definition": None if self.definition is None else self.definition.to_data(),
        }


@dataclass(frozen=True)
class RenderingsChanged:
    """The document learned a rendered container's definition (``definition`` is it), forgot one (``definition`` is
    ``None``), or changed one in place: its text, its settings or its picture (``definition`` is the new one)."""

    rendering_id: str
    definition: RenderedDefinition | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        return {
            "type": "rendering",
            "id": self.rendering_id,
            "definition": None if self.definition is None else self.definition.to_data(),
        }


# --------------------------------------------------------------------------- the model mixin
class ObjectModel[A: Anchor]:
    """Objects, their stacking order, their shapes and their image assets: the state and the operations all three
    apps share.

    An app's model inherits this next to :class:`~claudia_core.DocumentModel` and brings only what is its own:

    * ``containers()`` — the ids of the slides, sheets or paragraphs objects may sit on, in order.
    * ``check_anchor(anchor, body)`` — whether an object with this body fits where the anchor says it does (a
      slide's bounds, a cell of the sheet, an offset inside a paragraph). Raise ``ValueError`` with a sentence.
    * ``anchor_from_data(data)`` — read its own anchor.
    * ``diagram_from_data(data)`` — read its own :class:`DiagramDefinition`, if this app offers ``"diagram"``
      among its ``object_kinds`` (an app that does not need raise the default ``NotImplementedError``).
    * ``styles`` — a :class:`~claudia_core.StyleBook`, which ``check_object`` looks a style up in.

    The stacking order is per container, bottom first; the last object is in front."""

    #: How many objects one slide, sheet or paragraph may hold.
    max_objects_per_container: ClassVar[int] = MAX_OBJECTS_PER_CONTAINER
    #: The smallest an object may be, in the app's own units.
    min_object_size: ClassVar[int] = MIN_OBJECT_SIZE
    #: The kinds of object this app offers (a subset of ``OBJECT_KINDS``).
    object_kinds: ClassVar[tuple[str, ...]] = OBJECT_KINDS

    def __init__(self) -> None:
        self.objects: dict[str, VisualObject[A]] = {}
        self.images: dict[str, ImageAsset] = {}
        self.shapes: dict[str, ShapeDefinition] = {}
        self.diagrams: dict[str, DiagramDefinition] = {}
        self.renderings: dict[str, RenderedDefinition] = {}
        self.tables: dict[str, TableDef] = {}
        self._stack: dict[str, list[str]] = {}  # container id -> object ids, bottom first
        #: Changes whenever the objects' paragraphs may be read in another order or be another list item. An object
        #: came, went or moved to another container, or its paragraph's item or style changed; typing in an object
        #: does not count. Part of what a ``ParagraphHost`` reports as its ``structure_version``.
        self.paragraph_order = 0

    # -- what the app brings -----------------------------------------------------
    def containers(self) -> Iterable[str]:
        """The ids of the containers objects may sit on (slides, sheets, paragraphs), in order."""
        raise NotImplementedError

    def check_anchor(self, anchor: A, body: ObjectBody) -> None:
        """``ValueError`` with a sentence unless an object with this body may sit at this anchor."""
        raise NotImplementedError

    def anchor_from_data(self, data: dict) -> A:
        """Read this app's anchor from its plain-data form; ``ValueError`` if it is not one."""
        raise NotImplementedError

    def diagram_from_data(self, data: dict) -> DiagramDefinition:
        """Read this app's diagram definition from its plain-data form; ``ValueError`` if it is not one.

        Only apps that put ``"diagram"`` in ``object_kinds`` need override this (the default is never reached by
        :class:`DefineDiagram`/:class:`UpdateDiagram` unless an app actually issues them)."""
        raise NotImplementedError

    def turn_command(self, object_id: str, rotation: int) -> RotateObject:
        """The command that turns an object to ``rotation`` degrees clockwise: any whole number, read modulo a whole
        turn (−20 is 340), carrying the place the object must be moved to for its turned outline to be allowed (see
        :meth:`turned_anchor`) when that is not where it is.
        A chart and a table do not turn (``ValueError``; D1021, D1224)."""
        if not _is_whole(rotation):
            raise ValueError("the rotation must be whole degrees")
        obj = self.get_object(object_id)
        if not self.can_turn(obj.body):
            raise ValueError(f"A {_NOT_TURNED[obj.body.kind]} does not turn")
        turned = rotation % 360
        anchor = self.turned_anchor(obj, turned)
        return RotateObject(object_id, turned, None if anchor == obj.anchor else anchor.to_data())

    def can_turn(self, body: ObjectBody) -> bool:
        """Does an object like this turn? Text boxes, shapes, pictures, rendered text do; a chart or table does not."""
        return body.kind not in _NOT_TURNED

    def turned_anchor(self, obj: VisualObject[A], rotation: int) -> A:
        """Where ``obj`` has to sit for a turn to ``rotation`` to be allowed: its own anchor unless this app keeps what
        is in a container inside it (a slide does), in which case the nearest place that keeps the turned outline in.
        ``ValueError`` with a sentence when there is no such place."""
        return obj.anchor

    # -- the stack ---------------------------------------------------------------
    def open_container(self, container: str) -> None:
        """Make room for a container's objects (called when a slide, sheet or paragraph appears)."""
        self._stack.setdefault(container, [])

    def close_container(self, container: str) -> None:
        """Forget a container; refused while it still holds objects."""
        if self._stack.get(container):
            raise ValueError(f"{container!r} still has objects; remove them first")
        self._stack.pop(container, None)

    def objects_on(self, container: str) -> list[VisualObject[A]]:
        """The objects of a container, bottom first (the last one is in front)."""
        return [self.objects[object_id] for object_id in self._stack.get(container, [])]

    def stack_of(self, container: str) -> tuple[str, ...]:
        """The stacking order of a container, bottom first."""
        return tuple(self._stack.get(container, ()))

    # -- reading -----------------------------------------------------------------
    def get_object(self, object_id: str) -> VisualObject[A]:
        """The object with this id; ``ValueError`` if there is none."""
        try:
            return self.objects[object_id]
        except KeyError:
            raise ValueError(f"no object {object_id!r}") from None

    def selection_of(self, object_id: str) -> tuple[ObjectSet, ...]:
        """The one-object selection a command about this object touches, or ``()`` if it is gone."""
        obj = self.objects.get(object_id)
        return () if obj is None else (ObjectSet(obj.container, frozenset({object_id})),)

    # -- names (D550, D551) --------------------------------------------------------
    def named_things(self) -> Iterator[tuple[str, str, str]]:
        """``(kind, id, name)`` of everything in this document that has a name: the objects here, and whatever else the
        app names (its slides, sheets, chart tabs) by adding to this. One namespace for all of it (D550)."""
        for obj in self.objects.values():
            if obj.body.name:
                yield obj.body.kind, obj.id, obj.body.name

    def unnamed_things(self) -> Iterator[tuple[str, str]]:
        """``(kind, id)`` of everything that could have a name and has none: what a document from before names holds. An
        app that names more than its objects adds to this, as it does to :meth:`named_things`."""
        for obj in self.objects.values():
            if not obj.body.name:
                yield obj.body.kind, obj.id

    def has_thing(self, thing_id: str) -> bool:
        """Is there an object, slide, sheet or chart tab with this id, named or not?"""
        return any(i == thing_id for _kind, i, _name in self.named_things()) or any(
            i == thing_id for _kind, i in self.unnamed_things()
        )

    def thing_name(self, thing_id: str) -> str:
        """The name of the thing with this id, ``""`` if it has none; ``ValueError`` if there is no such thing."""
        return self.get_object(thing_id).body.name

    def set_thing_name(self, thing_id: str, name: str) -> str:
        """Give the thing this (checked) name; returns the one it had. An app that names more than its objects
        overrides this for its own things and hands the rest on."""
        old = self.get_object(thing_id)
        self.replace_object(old.with_body(name=name))
        return old.body.name

    def rename_thing(self, ctx: Context, thing_id: str, name: str) -> tuple[str, tuple[Command, ...]]:
        """Give the thing this (checked) name; returns the one it had and the commands that, done after the old name
        is back, put back everything else the rename changed. An app whose rename changes more than the name (a
        sheet's name is in the formulas that read it) overrides this and emits what its clients must hear."""
        return self.set_thing_name(thing_id, name), ()

    def check_thing_name(self, thing_id: str, name: str, *, shared: bool = True) -> None:
        """``ValueError`` with a sentence unless ``name`` may be the name of the thing ``thing_id`` (``""`` is no name
        and always allowed): written tidily, a good name, and nobody else's, however capitals and spaces are written.
        A thing that keeps the name it has is not judged against the others again, so a clash that an older document
        holds does not stop its thing from being changed for another reason. With ``shared`` false (what an old log
        replays with, D550, D552) the others are not looked at at all."""
        if not name:
            return
        problem = name_problem(name)
        if problem is not None:
            raise ValueError(problem)
        if clean_name(name) != name:
            raise ValueError("a name is written without spaces around it or twice in a row")
        if shared and not self._keeps_name(thing_id, name):
            self.check_name_free(thing_id, name)

    def _keeps_name(self, thing_id: str, name: str) -> bool:
        """Is ``name`` (as far as capitals go) the name the thing ``thing_id`` has now? ``False`` for a new thing."""
        try:
            return name_key(self.thing_name(thing_id)) == name_key(name)
        except ValueError:
            return False

    def name_holder(self, thing_id: str, name: str, ignoring: tuple[str, ...] = ()) -> tuple[str, str] | None:
        """``(kind, name)`` of another thing that already has this name, however capitals and spaces are written.
        Things of the kinds in ``ignoring`` do not count (a name of a range is checked against things only)."""
        key = name_key(name)
        for kind, other, other_name in self.named_things():
            if other != thing_id and kind not in ignoring and name_key(other_name) == key:
                return kind, other_name
        return None

    def check_name_free(self, thing_id: str, name: str, ignoring: tuple[str, ...] = ()) -> None:
        """``ValueError`` with a sentence unless nobody but ``thing_id`` has this name. Only this half of the check is
        for commands that may be in an old log (D550): what was written before names were shared is not tidied or
        judged again, it only never gets a new clash."""
        holder = self.name_holder(thing_id, name, ignoring)
        if holder is not None:
            kind, other_name = holder
            article = "an" if kind[:1] in "aeiou" else "a"
            raise ValueError(f"There is already {article} {kind} called “{other_name}”")

    def names_in_use(self) -> list[str]:
        """Every name in this document, for choosing a free one (:func:`~claudia_core.free_name`)."""
        return [name for _kind, _id, name in self.named_things()]

    def users_of_image(self, image_id: str) -> list[str]:
        """The ids of the objects that use this image asset."""
        return [obj.id for obj in self.objects.values() if obj.body.image == image_id]

    def picture_of(self, body: ObjectBody) -> str | None:
        """The id of the image asset that draws ``body``: its own picture, or for a rendered container the picture last
        made from its text (``None`` for a container nothing has been made for yet, and for kinds drawn otherwise).
        Everything that draws or exports a picture asks this, so a rendered container is a picture to it (D394)."""
        if body.image is not None:
            return body.image
        if body.rendered is not None and body.rendered in self.renderings:
            return self.renderings[body.rendered].image
        return None

    def users_of_shape(self, shape_id: str) -> list[str]:
        """The ids of the objects that use this shape outline."""
        return [obj.id for obj in self.objects.values() if obj.body.shape == shape_id]

    def users_of_diagram(self, diagram_id: str) -> list[str]:
        """The ids of the objects that use this diagram definition."""
        return [obj.id for obj in self.objects.values() if obj.body.diagram == diagram_id]

    def users_of_rendering(self, rendering_id: str) -> list[str]:
        """The ids of the objects that show this rendered container's definition."""
        return [obj.id for obj in self.objects.values() if obj.body.rendered == rendering_id]

    def users_of_table(self, table_id: str) -> list[str]:
        """The ids of the objects that show this table."""
        return [obj.id for obj in self.objects.values() if obj.body.table == table_id]

    def style_in_use(self, style_id: str) -> bool:
        """Does any object have this style, for itself or for its words, or does any box of a table? (Asked by the core
        style commands before they take a style back.)"""
        return any(style_id in object_styles(obj.body) for obj in self.objects.values()) or any(
            p.style == style_id for table in self.tables.values() for p in table.all_paragraphs()
        )

    def restyle_users(self, old: str, new: str) -> list[Command]:
        """The commands that put every object that has the style ``old`` (for itself or for its words) under ``new``
        instead, in object order (asked by the deletion of a style, D226)."""
        commands: list[Command] = []
        for obj in self.objects.values():
            if obj.body.style == old:
                commands.append(SetObjectStyle(obj.id, new))
            if obj.body.paragraph is not None and obj.body.paragraph.style == old:
                commands.append(SetParagraphStyle(obj.id, new))
        return commands

    # -- list items (E9.21, step D): the words of an object may be an item of a list ------------------
    def _words(self, object_id: str) -> Paragraph:
        paragraph = self.get_object(object_id).body.paragraph
        if paragraph is None:
            raise ValueError("an image carries no text")
        return paragraph

    def object_item(self, object_id: str) -> ListItem | None:
        """The list item the words of this object are (an object has one paragraph, D181)."""
        return self._words(object_id).item

    def put_object_item(self, object_id: str, item: ListItem | None) -> ObjectsChanged:
        """Make the words of this object an item as ``item`` says (``None``: none); the event tells the clients."""
        new = self.get_object(object_id).with_body(paragraph=self._words(object_id).with_item(item))
        self.replace_object(new)
        return self.objects_changed(new.container, changed=(new,))

    def object_generated(self, object_id: str) -> Generated | None:
        """The options of the table of contents (agenda) the words of this object are, or ``None``."""
        return self._words(object_id).generated

    def put_object_generated(self, object_id: str, generated: Generated | None) -> ObjectsChanged:
        """Make the words of this object a table of contents (an agenda) as ``generated`` says, or plain again; only
        an object without words can become one. The event tells the clients."""
        new = self.get_object(object_id).with_body(paragraph=self._words(object_id).with_generated(generated))
        self.replace_object(new)
        return self.objects_changed(new.container, changed=(new,))

    def insert_object_text(
        self, object_id: str, offset: int, text: str, runs: list[Run], fields: tuple[Field, ...] = ()
    ) -> ObjectsChanged:
        """Type ``text``, written as ``runs`` say and with the ``fields`` of its U+FFFC, into the words of this object
        at ``offset`` (step G); the event tells the clients. An agenda takes no typing."""
        words = self._words(object_id)
        if words.generated is not None and text:
            raise ValueError("an agenda takes no typing: its entries come from the slide titles")
        return self._put_words(object_id, words.typed(offset, text, runs, fields))

    def remove_object_text(
        self, object_id: str, start: int, end: int
    ) -> tuple[str, list[Run], tuple[Field, ...], ObjectsChanged]:
        """Cut ``start <= i < end`` out of the words of this object: what was cut, with its runs and fields, and the
        event."""
        kept, text, runs, fields = self._words(object_id).cut(start, end)
        return text, runs, fields, self._put_words(object_id, kept)

    def object_fields(self, object_id: str) -> tuple[Field, ...]:
        """The fields in the words of this object (step H)."""
        return self._words(object_id).fields

    def put_object_fields(self, object_id: str, fields: tuple[Field, ...]) -> ObjectsChanged:
        """Give the words of this object other fields at their U+FFFC; the event tells the clients."""
        return self._put_words(object_id, self._words(object_id).with_fields(fields))

    def _put_words(self, object_id: str, words: Paragraph) -> ObjectsChanged:
        new = self.get_object(object_id).with_body(paragraph=words)
        self.replace_object(new)
        return self.objects_changed(new.container, changed=(new,))

    def object_list_in_use(self, list_id: str) -> bool:
        """Are the words of any object an item of this list?"""
        return any(
            obj.body.paragraph is not None
            and obj.body.paragraph.item is not None
            and obj.body.paragraph.item.list == list_id
            for obj in self.objects.values()
        )

    # -- redaction (D720, D723) ---------------------------------------------------
    @classmethod
    def blank_diagram(cls, definition: dict) -> dict:
        """A diagram's definition with what people wrote in it gone and its shape kept (its id, what it reads), for
        redaction. Only an app that has diagrams knows their content; the default refuses."""
        from .errors import RedactionError

        raise RedactionError(f"{getattr(cls, 'app', cls.__name__)} documents cannot blank a diagram")

    def blank_objects(self, parts: frozenset[str] | None) -> None:
        """Blank the objects whose id is in ``parts`` (all of them for ``None``), in place, for redacting an import
        (D723): their words become filler of the same length, their description and import record lose what a
        person wrote, and the pictures, rendered sources and diagrams they show are blanked with them. Ids, places,
        sizes and styles stay."""
        chosen = [obj for obj in self.objects.values() if parts is None or obj.id in parts]
        for obj in chosen:
            body = obj.body
            if body.image is not None and body.image in self.images:
                self.images[body.image] = self.images[body.image].blanked()
            if body.rendered is not None and body.rendered in self.renderings:
                rendering = self.renderings[body.rendered]
                if rendering.image is not None and rendering.image in self.images:
                    self.images[rendering.image] = self.images[rendering.image].blanked()
                self.renderings[body.rendered] = rendering.redacted()
            if body.table is not None and body.table in self.tables:
                self.tables[body.table] = self.tables[body.table].blanked(keep_length=True)
            if body.diagram is not None and body.diagram in self.diagrams:
                blank = self.blank_diagram(self.diagrams[body.diagram].to_data())
                self.diagrams[body.diagram] = self.diagram_from_data(blank)
            self.objects[obj.id] = replace(obj, body=blank_body(body, keep_length=True))

    # -- shapes ------------------------------------------------------------------
    def define_shape(self, shape: ShapeDefinition) -> None:
        """Take a shape's outline into the document, so that it opens the same on any server."""
        if shape.id in self.shapes:
            raise ValueError(f"shape {shape.id!r} is already defined in this document")
        self.shapes[shape.id] = shape

    def forget_shape(self, shape_id: str) -> ShapeDefinition:
        """Let go of a shape nobody uses; returns it."""
        if shape_id not in self.shapes:
            raise ValueError(f"this document does not know the shape {shape_id!r}")
        users = self.users_of_shape(shape_id)
        if users:
            raise ValueError(f"shape {shape_id!r} is in use by {users[0]!r}")
        return self.shapes.pop(shape_id)

    # -- images ------------------------------------------------------------------
    def define_image(self, image: ImageAsset) -> None:
        """Take a decoded image into the document, so that it opens the same on any server."""
        if image.id in self.images:
            raise ValueError(f"image {image.id!r} is already defined in this document")
        self.images[image.id] = image

    def forget_image(self, image_id: str) -> ImageAsset:
        """Let go of an image asset nobody uses; returns it."""
        if image_id not in self.images:
            raise ValueError(f"this document does not know the image {image_id!r}")
        users = self.users_of_image(image_id)
        if users:
            raise ValueError(f"image {image_id!r} is in use by {users[0]!r}")
        holder = next((r.id for r in self.renderings.values() if r.image == image_id), None)
        if holder is not None:
            raise ValueError(f"image {image_id!r} is in use by the rendering {holder!r}")
        return self.images.pop(image_id)

    # -- diagrams ------------------------------------------------------------------
    def define_diagram(self, definition: DiagramDefinition) -> None:
        """Take a diagram's definition into the document, so that it opens the same on any server."""
        if definition.id in self.diagrams:
            raise ValueError(f"diagram {definition.id!r} is already defined in this document")
        self.diagrams[definition.id] = definition

    def forget_diagram(self, diagram_id: str) -> DiagramDefinition:
        """Let go of a diagram definition nobody uses; returns it."""
        if diagram_id not in self.diagrams:
            raise ValueError(f"this document does not know the diagram {diagram_id!r}")
        users = self.users_of_diagram(diagram_id)
        if users:
            raise ValueError(f"diagram {diagram_id!r} is in use by {users[0]!r}")
        return self.diagrams.pop(diagram_id)

    def replace_diagram(self, definition: DiagramDefinition) -> DiagramDefinition:
        """Swap in a changed version of a diagram definition that exists, in place (its id stays); returns the
        one it replaces. Unlike a shape or an image, a diagram's own content (its range, its titles) is meant to
        be edited after the fact — this is what :class:`UpdateDiagram` uses."""
        if definition.id not in self.diagrams:
            raise ValueError(f"this document does not know the diagram {definition.id!r}")
        old = self.diagrams[definition.id]
        self.diagrams[definition.id] = definition
        return old

    # -- checking ----------------------------------------------------------------
    # -- rendered containers ---------------------------------------------------------
    def define_rendering(self, definition: RenderedDefinition) -> None:
        """Take a rendered container's definition into the document. Its picture, if it names one, must be here."""
        if definition.id in self.renderings:
            raise ValueError(f"rendering {definition.id!r} is already defined in this document")
        self._check_rendering_picture(definition)
        self.renderings[definition.id] = definition

    def forget_rendering(self, rendering_id: str) -> RenderedDefinition:
        """Let go of a definition nobody uses; returns it."""
        if rendering_id not in self.renderings:
            raise ValueError(f"this document does not know the rendering {rendering_id!r}")
        users = self.users_of_rendering(rendering_id)
        if users:
            raise ValueError(f"rendering {rendering_id!r} is in use by {users[0]!r}")
        return self.renderings.pop(rendering_id)

    def replace_rendering(self, definition: RenderedDefinition) -> RenderedDefinition:
        """Swap in a changed definition that exists, in place (its id and its type stay); returns the one it replaces.

        A container's text is meant to be edited, so unlike an image or a shape there is no forget-and-define dance."""
        old = self.renderings.get(definition.id)
        if old is None:
            raise ValueError(f"this document does not know the rendering {definition.id!r}")
        if definition.type != old.type:
            raise ValueError("a rendering cannot change its type: make another container")
        self._check_rendering_picture(definition)
        self.renderings[definition.id] = definition
        return old

    # -- tables (D1201) ------------------------------------------------------------------------------------------
    def define_table(self, definition: TableDef) -> None:
        """Take a table's definition into the document; ``ValueError`` unless it holds together."""
        if definition.id in self.tables:
            raise ValueError(f"table {definition.id!r} is already defined in this document")
        self.check_table(definition)
        self.tables[definition.id] = definition

    def forget_table(self, table_id: str) -> TableDef:
        """Let go of a table nobody shows; returns it."""
        if table_id not in self.tables:
            raise ValueError(f"this document does not know the table {table_id!r}")
        users = self.users_of_table(table_id)
        if users:
            raise ValueError(f"table {table_id!r} is shown by {users[0]!r}")
        return self.tables.pop(table_id)

    def get_table(self, table_id: str) -> TableDef:
        """The table with this id; ``ValueError`` if the document has none."""
        try:
            return self.tables[table_id]
        except KeyError:
            raise ValueError(f"this document does not know the table {table_id!r}") from None

    def replace_table(self, definition: TableDef) -> TableDef:
        """Swap in a changed, checked version of a table that exists; returns the one it replaces. The words of a box
        are not a change of the layout of the text around it, so nothing else is told."""
        old = self.get_table(definition.id)
        self.check_table(definition)
        self.tables[definition.id] = definition
        return old

    def check_table(self, definition: TableDef) -> None:
        """``ValueError`` with a sentence unless this table may be in this document. An app adds what only it knows
        (composes: that the look exists and the styles it names fit); the table's own checks are always made."""
        definition.check()

    # -- the words of a table's boxes (D1210) ----------------------------------------------------------------------
    def is_entry(self, paragraph_id: str) -> bool:
        """Is this the id of a box of a table the document has (and is it a box that holds words of its own)?"""
        found = parse_entry_id(paragraph_id)
        if found is None or found[0] not in self.tables:
            return False
        table = self.tables[found[0]]
        return found[1] in table.rows and found[2] in table.column_ids()

    def entry_words(self, paragraph_id: str) -> Paragraph:
        """The paragraph of a box: what is typed into, cut from and styled. ``ValueError`` if it names no box."""
        if not self.is_entry(paragraph_id):
            raise ValueError(f"no table box {paragraph_id!r}")
        table, row, col = parse_entry_id(paragraph_id)  # type: ignore[misc]
        return self.tables[table].paragraph(row, col)

    def put_entry_words(self, paragraph_id: str, words: Paragraph) -> None:
        """Put these words in a box; a box with no words and no style of its own is not kept (it follows the look)."""
        table, row, col = parse_entry_id(paragraph_id)  # type: ignore[misc]
        definition = self.tables[table]
        empty = not words.text and not words.style and not words.fields
        self.replace_table(definition.with_entries([(row, col, None if empty else words)]))

    def check_entry_edit(self, paragraph_id: str) -> None:
        """``ValueError`` unless words may be typed into this box: a box a merge covers takes none."""
        table, row, col = parse_entry_id(paragraph_id)  # type: ignore[misc]
        if self.tables[table].covered(row, col):
            raise ValueError("a merged box holds its words in its top-left box")

    def _check_rendering_picture(self, definition: RenderedDefinition) -> None:
        if definition.image is not None and definition.image not in self.images:
            raise ValueError(f"this document does not know the image {definition.image!r}")

    def check_object(self, obj: VisualObject[A], *, shared_names: bool = True) -> None:
        """``ValueError`` with a sentence if this object cannot exist in this document as it is now. With
        ``shared_names`` false its name is not compared with the others (an old log, D552).

        The shared checks are here; ``check_anchor`` adds the app's own."""
        body = obj.body
        if not isinstance(body.id, str) or not _ID.fullmatch(body.id):
            raise ValueError(f"object id {body.id!r}: lower-case letters, digits, '-' and '_', starting with a letter")
        if obj.container not in self._stack:
            # ``_stack`` has a key for every container that exists (``open_container``/``close_container``), so
            # this is O(1). Asking ``containers()`` instead would walk every paragraph of a text on every check.
            raise ValueError(f"unknown container {obj.container!r}")
        if body.kind not in self.object_kinds:
            raise ValueError(f"unknown kind {body.kind!r}: an object is one of {', '.join(self.object_kinds)}")
        styles = getattr(self, "styles", None)
        if styles is not None:
            self._check_slot(styles, body.kind, 0, body.style)
        aspect = self._check_visual(body)
        self._check_size(body, aspect)
        if body.kind in ("image", "diagram", "rendered", "table"):
            if body.paragraph is not None:
                raise ValueError(f"a {body.kind} carries no text")
        else:
            if body.paragraph is None:
                raise ValueError(f"a {body.kind} object carries a paragraph, even an empty one")
            body.paragraph.check()
            if styles is not None:
                self._check_slot(styles, body.kind, 1, body.paragraph.style)
        if not _is_whole(body.rotation) or not 0 <= body.rotation < 360:
            raise ValueError("the rotation must be whole degrees from 0 to 359")
        if type(body.snap) is not bool:
            raise ValueError("snap must be true or false")
        self._check_description(body)
        self.check_thing_name(body.id, body.name, shared=shared_names)
        self.check_anchor(obj.anchor, body)

    @staticmethod
    def _check_description(body: ObjectBody) -> None:
        """``ValueError`` unless the description is short text and a decorative object has none."""
        if not isinstance(body.description, str) or len(body.description) > MAX_ALT_CHARS:
            raise ValueError(f"the description is text of at most {MAX_ALT_CHARS} characters")
        if type(body.decorative) is not bool:
            raise ValueError("decorative must be true or false")
        if body.decorative and body.description:
            raise ValueError("a decorative object has no description")

    @staticmethod
    def _check_slot(styles: Any, kind: str, index: int, style_id: str) -> None:
        """``ValueError`` unless ``style_id`` exists and fits slot ``index`` of an object of ``kind``: the
        container's slot (0) or the words' (1) — see :data:`claudia_core.facets.SLOTS` (D304, D316)."""
        if style_id not in styles:
            raise ValueError(f"unknown {'paragraph ' if index else ''}style {style_id!r}")
        slot = SLOTS.slots_of(kind)[index]
        style = styles.get(style_id)
        if not fits(style.kind, slot):
            raise ValueError(
                f"“{style.name}” is a {style.kind} style and cannot be put into the {slot.name} of a {kind} object"
            )

    def _check_visual(self, body: ObjectBody) -> float | None:
        """What ``body.kind`` requires of ``shape``/``image``/``imported``/``diagram``, and the aspect ratio (if
        any) it keeps. Each kind's own requirements are a small method of its own below, rather than one long
        dispatch, now that there are four kinds to tell apart."""
        checks = {
            "text": self._check_text_visual,
            "shape": self._check_shape_visual,
            "diagram": self._check_diagram_visual,
            "image": self._check_image_visual,
            "rendered": self._check_rendered_visual,
            "table": self._check_table_visual,
        }
        return checks[body.kind](body)

    @staticmethod
    def _check_text_visual(body: ObjectBody) -> None:
        if body.ref is not None or body.imported is not None:
            raise ValueError("a text box points at no definition")

    def _check_shape_visual(self, body: ObjectBody) -> float | None:
        self._check_ref(body, "shape", self.shapes)
        return self.shapes[str(body.ref)].aspect

    def _check_diagram_visual(self, body: ObjectBody) -> None:
        self._check_ref(body, "diagram", self.diagrams)
        # a diagram keeps no fixed aspect ratio (falls through to the implicit ``None``)

    def _check_rendered_visual(self, body: ObjectBody) -> None:
        self._check_ref(body, "rendered", self.renderings, label="rendering")
        # the picture scales with the frame the person gives it, and keeps no fixed ratio of its own

    def _check_table_visual(self, body: ObjectBody) -> None:
        self._check_ref(body, "table", self.tables)
        # the layout works out the height from the words: ``h`` is only what it was last found to be

    def _check_image_visual(self, body: ObjectBody) -> float | None:
        if body.ref is None or body.imported is None:
            raise ValueError("an image object needs an image and its import record")
        self._check_ref(body, "image", self.images)
        if body.imported.asset != body.ref:
            raise ValueError("the import record's asset does not match the object's image")
        return self.images[body.ref].aspect

    @staticmethod
    def _check_ref(body: ObjectBody, noun: str, known: Mapping[str, Any], *, label: str | None = None) -> None:
        """``ValueError`` unless ``body`` points at a definition of its kind that the document knows, and (unless it
        is an image) has no import record."""
        label = label or noun
        if body.imported is not None and noun != "image":
            raise ValueError(f"a {body.kind} object has no import record")
        if body.ref is None:
            raise ValueError(f"a {body.kind} object needs a {label}")
        if body.ref not in known:
            raise ValueError(f"this document does not know the {label} {body.ref!r}")

    def _check_size(self, body: ObjectBody, aspect: float | None) -> None:
        if not all(_is_whole(value) for value in (body.w, body.h)):
            raise ValueError("w and h must be whole numbers")
        if body.w < self.min_object_size or body.h < self.min_object_size:
            raise ValueError(f"the size must be at least {self.min_object_size} by {self.min_object_size} units")
        if aspect is not None and abs(body.w - aspect * body.h) > ASPECT_TOLERANCE:
            raise ValueError(f"this object keeps its proportions (width divided by height is {aspect:g})")

    # -- changing (used by the commands) -----------------------------------------
    def insert_object(self, obj: VisualObject[A], at: int | None = None, *, shared_names: bool = True) -> None:
        """Add a checked object on top of its container, or at stacking place ``at``."""
        if obj.id in self.objects:
            raise ValueError(f"object {obj.id!r} exists already")
        self.check_object(obj, shared_names=shared_names)
        stack = self._stack[obj.container]
        if len(stack) >= self.max_objects_per_container:
            raise ValueError(f"a container holds at most {self.max_objects_per_container} objects")
        if at is not None and not 0 <= at <= len(stack):
            raise ValueError(f"there is no stacking place {at} among {len(stack)} objects")
        stack.insert(len(stack) if at is None else at, obj.id)
        self.objects[obj.id] = obj
        self.paragraph_order += 1

    def delete_object(self, object_id: str) -> tuple[VisualObject[A], int]:
        """Take an object away; returns it and the stacking place it had."""
        obj = self.get_object(object_id)
        stack = self._stack[obj.container]
        place = stack.index(object_id)
        del stack[place]
        del self.objects[object_id]
        self.paragraph_order += 1
        return obj, place

    def replace_object(self, obj: VisualObject[A]) -> VisualObject[A]:
        """Swap in a changed (checked) version of an object that exists; returns the one it replaces.

        An object may move inside its container but never to another one: that would be a different object as far
        as locks and stacking are concerned."""
        old = self.get_object(obj.id)
        if obj.container != old.container:
            raise ValueError("an object cannot change its container")
        self.check_object(obj)
        self.objects[obj.id] = obj
        before, after = old.body.paragraph, obj.body.paragraph
        if (before is None) != (after is None) or (
            before is not None
            and after is not None
            and (before.item, before.style, before.generated) != (after.item, after.style, after.generated)
        ):
            self.paragraph_order += 1
        return old

    def objects_changed(
        self,
        container: str,
        *,
        changed: tuple[VisualObject[A], ...] = (),
        removed: tuple[str, ...] = (),
    ) -> ObjectsChanged:
        """The event that tells views what happened on ``container``, with its stacking order as it is now."""
        return ObjectsChanged(container, changed, removed, self.stack_of(container))

    # -- serialization helpers ---------------------------------------------------
    def objects_to_data(self) -> list[dict]:
        """Every object, container by container in stacking order: what ``serialize`` stores."""
        return [obj.to_data() for container in self.containers() for obj in self.objects_on(container)]

    def images_to_data(self) -> list[dict]:
        """Every image asset, by id: what ``serialize`` stores."""
        return [image.to_data() for _, image in sorted(self.images.items())]

    def shapes_to_data(self) -> list[dict]:
        """Every shape outline, by id: what ``serialize`` stores."""
        return [shape.to_data() for _, shape in sorted(self.shapes.items())]

    def diagrams_to_data(self) -> list[dict]:
        """Every diagram definition, by id: what ``serialize`` stores."""
        return [definition.to_data() for _, definition in sorted(self.diagrams.items())]

    def renderings_to_data(self) -> list[dict]:
        """Every rendered container's definition, by id: what ``serialize`` stores."""
        return [definition.to_data() for _, definition in sorted(self.renderings.items())]

    def tables_to_data(self) -> list[dict]:
        """Every table's definition, by id: what ``serialize`` stores."""
        return [definition.to_data() for _, definition in sorted(self.tables.items())]

    def restore_objects(
        self,
        objects: Iterable[dict],
        images: Iterable[dict] = (),
        shapes: Iterable[dict] = (),
        diagrams: Iterable[dict] = (),
        renderings: Iterable[dict] = (),
        tables: Iterable[dict] = (),
    ) -> None:
        """Put back what the six ``*_to_data`` methods stored (the containers must already exist)."""
        for data in tables:
            definition = TableDef.from_data(data)
            self.tables[definition.id] = definition
        for data in shapes:
            shape = ShapeDefinition.from_data(data)
            self.shapes[shape.id] = shape
        for data in images:
            image = ImageAsset.from_data(data)
            self.images[image.id] = image
        for data in diagrams:
            diagram = self.diagram_from_data(data)
            self.diagrams[diagram.id] = diagram
        for data in renderings:
            rendering = RenderedDefinition.from_data(data)
            self.renderings[rendering.id] = rendering
        for data in objects:
            obj = VisualObject.from_data(data, self.anchor_from_data)
            self.objects[obj.id] = obj
            self._stack.setdefault(obj.container, []).append(obj.id)
        self.paragraph_order += 1


# --------------------------------------------------------------------------- redaction
# FILLER, what a redacted character becomes (D720: one block per character, so that every later place in the text
# holds), is defined with the tables, which are blanked the same way, and read from here as it always was.


def blank_body(body: ObjectBody, *, keep_length: bool = False) -> ObjectBody:
    """An object's body with everything a person wrote gone (D720): its words, its description and the words of its
    import record. A paragraph that exists keeps existing, or the body would no longer be a valid object of its kind;
    with ``keep_length`` its words become as many :data:`FILLER` characters (what blanking an import needs, since
    later steps may edit them by place), otherwise it is emptied (what a redacted step that made the object needs)."""
    paragraph = body.paragraph
    if paragraph is not None:
        # a reference stays a reference (an id, not words) when the length is kept; emptied words take theirs along
        filler = "".join(c if c == FIELD_CHAR else FILLER for c in paragraph.text)
        paragraph = (
            paragraph.with_text(filler, paragraph.runs)
            if keep_length
            else replace(paragraph.with_text("", ()), fields=())
        )
    imported = None if body.imported is None else body.imported.blanked()
    return replace(body, paragraph=paragraph, description="", imported=imported)


def _object_model(model: type[DocumentModel]) -> type[ObjectModel]:
    if not issubclass(model, ObjectModel):
        raise TypeError(f"The {model.app} model holds no objects")
    return model


# --------------------------------------------------------------------------- the shared commands
def _host(ctx: Context) -> ObjectModel:
    model = ctx.model
    if not isinstance(model, ObjectModel):
        raise TypeError(f"The {model.app} model holds no objects, so it cannot use the object commands")
    return model


def _anchor_of(ctx: Context, data: dict):
    return _host(ctx).anchor_from_data(data)


def _target(command: Command) -> str | None:
    """The id of the object a command is about, if it is about one."""
    if isinstance(command, AddObject):
        return command.object_id
    kinds = (
        MoveObject
        | ResizeObject
        | SetText
        | SetParagraph
        | SetSnap
        | DescribeObject
        | SetParagraphStyle
        | RotateObject
        | RemoveObject
        | RenameThing
    )
    if isinstance(command, kinds):
        return command.id
    return None


def _touches(other: Command, object_id: str) -> bool:
    return _target(other) == object_id


def _changes_frame(other: Command, object_id: str) -> bool:
    """Did ``other`` place, size, turn, remove or re-create the object? (Its text is another matter.)"""
    kinds = MoveObject | ResizeObject | RotateObject | RemoveObject | AddObject
    return isinstance(other, kinds) and _target(other) == object_id


@core_commands.register
@dataclass(frozen=True)
class DefineShape(Command):
    """Take a shape's outline into the document, so that it opens the same anywhere."""

    kind: ClassVar[str] = "core.DefineShape"
    shape: ShapeDefinition

    @property
    def label(self) -> str:
        return "Define shape"

    @property
    def summary(self) -> str:
        return f"The document takes the shape “{self.shape.name}”"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        model.define_shape(self.shape)
        ctx.emit(ShapesChanged(self.shape.id, self.shape))
        return ForgetShape(self.shape.id)

    def to_data(self) -> dict:
        return {"shape": self.shape.to_data()}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> DefineShape:
        return cls(ShapeDefinition.from_data(data["shape"]))

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, DefineShape) and other.shape.id == self.shape.id else self

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class ForgetShape(Command):
    """Let go of a shape that no object uses (the undo of :class:`~claudia_core.DefineShape`)."""

    kind: ClassVar[str] = "core.ForgetShape"
    id: str

    @property
    def label(self) -> str:
        return "Forget shape"

    @property
    def summary(self) -> str:
        return f"The document lets go of the shape {self.id}"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        shape = model.forget_shape(self.id)
        ctx.emit(ShapesChanged(self.id, None))
        return DefineShape(shape)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> ForgetShape:
        return cls(data["id"])

    def shifted_by(self, other: Command) -> Command | None:
        """Refuse when a colleague now uses the shape, or defined it anew."""
        if isinstance(other, AddObject) and other.body.shape == self.id:
            return None
        return None if isinstance(other, DefineShape) and other.shape.id == self.id else self

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class DefineImage(Command):
    """Take a decoded image into the document, so that it opens the same anywhere."""

    kind: ClassVar[str] = "core.DefineImage"
    image: ImageAsset

    @property
    def label(self) -> str:
        return "Define image"

    @property
    def summary(self) -> str:
        return f"The document takes an image ({self.image.width} × {self.image.height})"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        model.define_image(self.image)
        ctx.emit(ImagesChanged(self.image.id, self.image))
        return ForgetImage(self.image.id)

    def to_data(self) -> dict:
        return {"image": self.image.to_data()}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> DefineImage:
        return cls(ImageAsset.from_data(data["image"]))

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, DefineImage) and other.image.id == self.image.id else self

    def redacted(self) -> Command:
        return DefineImage(self.image.blanked())


@core_commands.register
@dataclass(frozen=True)
class ForgetImage(Command):
    """Let go of an image that no object uses (the undo of :class:`~claudia_core.DefineImage`)."""

    kind: ClassVar[str] = "core.ForgetImage"
    id: str

    @property
    def label(self) -> str:
        return "Forget image"

    @property
    def summary(self) -> str:
        return f"The document lets go of the image {self.id}"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        image = model.forget_image(self.id)
        ctx.emit(ImagesChanged(self.id, None))
        return DefineImage(image)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> ForgetImage:
        return cls(data["id"])

    def shifted_by(self, other: Command) -> Command | None:
        """Refuse when a colleague now uses the image, or defined it anew."""
        if isinstance(other, AddObject) and other.body.image == self.id:
            return None
        return None if isinstance(other, DefineImage) and other.image.id == self.id else self

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class DefineDiagram(Command):
    """Take a diagram's definition into the document, so that it opens the same anywhere.

    ``definition`` crosses the wire and the log as plain data, exactly as an anchor does (see the module
    description): the app reads it back through :meth:`~claudia_core.ObjectModel.diagram_from_data`, the one
    door its own geometry (a cell range, say) enters through."""

    kind: ClassVar[str] = "core.DefineDiagram"
    definition: dict

    @property
    def label(self) -> str:
        return "Define diagram"

    @property
    def summary(self) -> str:
        return "The document takes a diagram"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        definition = model.diagram_from_data(self.definition)
        model.define_diagram(definition)
        ctx.emit(DiagramsChanged(definition.id, definition))
        return ForgetDiagram(definition.id)

    def to_data(self) -> dict:
        return {"definition": dict(self.definition)}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> DefineDiagram:
        return cls(dict(data["definition"]))

    def shifted_by(self, other: Command) -> Command | None:
        definition_id = self.definition.get("id")
        return None if isinstance(other, DefineDiagram) and other.definition.get("id") == definition_id else self

    def redacted(self) -> Command:
        """Only the app knows what in a diagram is content: see :meth:`redacted_in`."""
        return self

    def redacted_in(self, model: type[DocumentModel]) -> Command:
        return DefineDiagram(_object_model(model).blank_diagram(self.definition))


@core_commands.register
@dataclass(frozen=True)
class UpdateDiagram(Command):
    """Redefine a diagram in place (its id stays): the only way a diagram's own content — its range, its titles —
    ever changes once added. Unlike a shape or an image, which are immutable once imported, a diagram is meant
    to be edited after the fact, so there is no forget-and-redefine dance for this."""

    kind: ClassVar[str] = "core.UpdateDiagram"
    id: str
    definition: dict

    @property
    def label(self) -> str:
        return "Edit diagram"

    @property
    def summary(self) -> str:
        return "Edited a diagram"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        new = model.diagram_from_data(self.definition)
        if new.id != self.id:
            raise ValueError("a diagram cannot change its id")
        old = model.replace_diagram(new)
        ctx.emit(DiagramsChanged(self.id, new))
        return UpdateDiagram(self.id, old.to_data())

    def to_data(self) -> dict:
        return {"id": self.id, "definition": dict(self.definition)}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> UpdateDiagram:
        return cls(data["id"], dict(data["definition"]))

    def shifted_by(self, other: Command) -> Command | None:
        """Never destroy what a colleague has done to the diagram since (edited it again, or forgotten it)."""
        if isinstance(other, UpdateDiagram) and other.id == self.id:
            return None
        return None if isinstance(other, ForgetDiagram) and other.id == self.id else self

    def redacted(self) -> Command:
        """Only the app knows what in a diagram is content: see :meth:`redacted_in`."""
        return self

    def redacted_in(self, model: type[DocumentModel]) -> Command:
        return UpdateDiagram(self.id, _object_model(model).blank_diagram(self.definition))


@core_commands.register
@dataclass(frozen=True)
class ForgetDiagram(Command):
    """Let go of a diagram definition that no object uses (the undo of :class:`DefineDiagram`)."""

    kind: ClassVar[str] = "core.ForgetDiagram"
    id: str

    @property
    def label(self) -> str:
        return "Forget diagram"

    @property
    def summary(self) -> str:
        return f"The document lets go of the diagram {self.id}"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        definition = model.forget_diagram(self.id)
        ctx.emit(DiagramsChanged(self.id, None))
        return DefineDiagram(definition.to_data())

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> ForgetDiagram:
        return cls(data["id"])

    def shifted_by(self, other: Command) -> Command | None:
        """Refuse when a colleague now uses the diagram, or defined it anew."""
        if isinstance(other, AddObject) and other.body.diagram == self.id:
            return None
        return None if isinstance(other, DefineDiagram) and other.definition.get("id") == self.id else self

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class DefineRendering(Command):
    """Take a rendered container's definition into the document: its text, its settings and, if it has one, its
    picture (which must already be in the document, see :class:`DefineImage`).

    ``definition`` crosses the wire and the log as plain data, as :meth:`RenderedDefinition.to_data` writes it."""

    kind: ClassVar[str] = "core.DefineRendering"
    definition: dict

    @property
    def label(self) -> str:
        return "Define rendered text"

    @property
    def summary(self) -> str:
        return "The document takes a piece of rendered text"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        definition = RenderedDefinition.from_data(self.definition)
        model.define_rendering(definition)
        ctx.emit(RenderingsChanged(definition.id, definition))
        return ForgetRendering(definition.id)

    def to_data(self) -> dict:
        return {"definition": dict(self.definition)}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> DefineRendering:
        return cls(dict(data["definition"]))

    def shifted_by(self, other: Command) -> Command | None:
        mine = self.definition.get("id")
        return None if isinstance(other, DefineRendering) and other.definition.get("id") == mine else self

    def redacted(self) -> Command:
        return DefineRendering(RenderedDefinition.from_data(self.definition).redacted().to_data())


@core_commands.register
@dataclass(frozen=True)
class UpdateRendering(Command):
    """Change a rendered container's definition in place: the text a person writes, the settings, and the picture
    made from it. Its id and its type stay. The undo puts the whole earlier definition back, picture included."""

    kind: ClassVar[str] = "core.UpdateRendering"
    id: str
    definition: dict

    @property
    def label(self) -> str:
        return "Edit rendered text"

    @property
    def summary(self) -> str:
        return "Edited a piece of rendered text"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        new = RenderedDefinition.from_data(self.definition)
        if new.id != self.id:
            raise ValueError("a rendering cannot change its id")
        old = model.replace_rendering(new)
        ctx.emit(RenderingsChanged(self.id, new))
        return UpdateRendering(self.id, old.to_data())

    def to_data(self) -> dict:
        return {"id": self.id, "definition": dict(self.definition)}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> UpdateRendering:
        return cls(data["id"], dict(data["definition"]))

    def shifted_by(self, other: Command) -> Command | None:
        """Never destroy what a colleague has done to the text since (edited it again, or forgotten it)."""
        if isinstance(other, UpdateRendering | ForgetRendering) and other.id == self.id:
            return None
        return self

    def redacted(self) -> Command:
        return UpdateRendering(self.id, RenderedDefinition.from_data(self.definition).redacted().to_data())


@core_commands.register
@dataclass(frozen=True)
class ForgetRendering(Command):
    """Let go of a rendered container's definition that no object shows (the undo of :class:`DefineRendering`)."""

    kind: ClassVar[str] = "core.ForgetRendering"
    id: str

    @property
    def label(self) -> str:
        return "Forget rendered text"

    @property
    def summary(self) -> str:
        return f"The document lets go of the rendered text {self.id}"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        definition = model.forget_rendering(self.id)
        ctx.emit(RenderingsChanged(self.id, None))
        return DefineRendering(definition.to_data())

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> ForgetRendering:
        return cls(data["id"])

    def shifted_by(self, other: Command) -> Command | None:
        """Refuse when a colleague now shows the definition, or defined it anew."""
        if isinstance(other, AddObject) and other.body.rendered == self.id:
            return None
        return None if isinstance(other, DefineRendering) and other.definition.get("id") == self.id else self

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class AddObject(Command):
    """Put a text box, a shape or an image on a slide, a sheet or a paragraph: on top of the others, or at
    stacking place ``at``.

    The body is the shared part; ``anchor`` is plain data the app reads back (see the module description)."""

    kind: ClassVar[str] = "core.AddObject"
    schema: ClassVar[int] = (
        6  # 1: a body without ``description`` and ``decorative``; 2: without ``rendered``; 3: without ``name``;
        # 4: names were not yet shared with named ranges (D552); 5: a body with one pointer field per kind (``shape``,
        # ``image``, ``diagram``, ``rendered``, ``table``) instead of ``ref``
    )
    body: ObjectBody
    anchor: dict
    at: int | None = None
    legacy_names: bool = False  # written before ranges shared the names: its name is not compared again

    @property
    def object_id(self) -> str:
        """The id of the object this command adds."""
        return self.body.id

    @property
    def label(self) -> str:
        labels = {
            "text": "Add text box",
            "shape": "Add shape",
            "image": "Add image",
            "diagram": "Add diagram",
            "rendered": "Add rendered text",
        }
        return labels[self.body.kind]

    @property
    def summary(self) -> str:
        if self.body.kind == "text":
            words = self.body.paragraph.text if self.body.paragraph else ""
            return f"Added a text box: {_quote(words)}" if words.strip() else "Added a text box"
        if self.body.kind == "image":
            if self.body.decorative:
                return "Added a decorative image"
            alt = self.body.description
            return f"Added an image: {_quote(alt)}" if alt.strip() else "Added an image"
        if self.body.kind == "diagram":
            return "Added a diagram"
        if self.body.kind == "rendered":
            return "Added a piece of rendered text"
        return f"Added a {self.body.shape}"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        obj = VisualObject(self.body, _anchor_of(ctx, self.anchor))
        model.insert_object(obj, self.at, shared_names=not self.legacy_names)
        ctx.emit(model.objects_changed(obj.container, changed=(obj,)))
        return RemoveObject(obj.id)

    def to_data(self) -> dict:
        data = {"body": self.body.to_data(), "anchor": dict(self.anchor), "at": self.at}
        if self.legacy_names:
            data["legacy_names"] = True
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> AddObject:
        return cls(
            ObjectBody.from_data(data["body"]), dict(data["anchor"]), data.get("at"), data.get("legacy_names", False)
        )

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        container = self.anchor.get("container")
        return (ObjectSet(container, frozenset({self.object_id})),) if isinstance(container, str) else ()

    def shifted_by(self, other: Command) -> Command | None:
        """Bringing an object back is refused when somebody made another one with its id, or took its shape,
        image or diagram away."""
        if isinstance(other, AddObject) and other.object_id == self.object_id:
            return None
        if isinstance(other, ForgetShape) and other.id == self.body.shape:
            return None
        if isinstance(other, ForgetDiagram) and other.id == self.body.diagram:
            return None
        if isinstance(other, ForgetRendering) and other.id == self.body.rendered:
            return None
        return None if isinstance(other, ForgetImage) and other.id == self.body.image else self

    def redacted(self) -> Command:
        return AddObject(blank_body(self.body), self.anchor, self.at, self.legacy_names)

    def stub(self) -> dict:
        return {"id": self.object_id}


@core_commands.register
@dataclass(frozen=True)
class RemoveObject(Command):
    """Take an object off its slide, sheet or paragraph."""

    kind: ClassVar[str] = "core.RemoveObject"
    id: str

    @property
    def label(self) -> str:
        return "Remove object"

    @property
    def summary(self) -> str:
        return "Removed an object"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        obj, place = model.delete_object(self.id)
        ctx.emit(model.objects_changed(obj.container, removed=(obj.id,)))
        return AddObject(obj.body, obj.anchor.to_data(), place)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> RemoveObject:
        return cls(data["id"])

    def ends_paragraph(self, paragraph_id: str) -> bool:
        return paragraph_id == self.id  # an object's words are the paragraph with its id

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, ObjectModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        """Never destroy what a colleague has done to the object since (this is the undo of adding it)."""
        return None if _touches(other, self.id) else self

    def redacted(self) -> Command:
        return self

    def stub(self) -> dict:
        return {"id": self.id}


@core_commands.register
@dataclass(frozen=True)
class MoveObject(Command):
    """Put an object at a new place; its size stays. ``anchor`` is the app's own, as plain data."""

    kind: ClassVar[str] = "core.MoveObject"
    id: str
    anchor: dict

    @property
    def label(self) -> str:
        return "Move object"

    @property
    def summary(self) -> str:
        return "Moved an object"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        old = model.get_object(self.id)
        new = replace(old, anchor=_anchor_of(ctx, self.anchor))
        model.replace_object(new)
        ctx.emit(model.objects_changed(new.container, changed=(new,)))
        return MoveObject(self.id, old.anchor.to_data())

    def to_data(self) -> dict:
        return {"id": self.id, "anchor": dict(self.anchor)}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> MoveObject:
        return cls(data["id"], dict(data["anchor"]))

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, ObjectModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        return None if _changes_frame(other, self.id) else self

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class ResizeObject(Command):
    """Give an object a new frame: place and size together, since dragging a corner moves the corner."""

    kind: ClassVar[str] = "core.ResizeObject"
    id: str
    anchor: dict
    w: int
    h: int

    @property
    def label(self) -> str:
        return "Resize object"

    @property
    def summary(self) -> str:
        return f"Resized an object to {self.w} × {self.h}"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        old = model.get_object(self.id)
        new = replace(old, anchor=_anchor_of(ctx, self.anchor)).with_body(w=self.w, h=self.h)
        model.replace_object(new)
        ctx.emit(model.objects_changed(new.container, changed=(new,)))
        return ResizeObject(self.id, old.anchor.to_data(), old.body.w, old.body.h)

    def to_data(self) -> dict:
        return {"id": self.id, "anchor": dict(self.anchor), "w": self.w, "h": self.h}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> ResizeObject:
        return cls(data["id"], dict(data["anchor"]), data["w"], data["h"])

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, ObjectModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        return None if _changes_frame(other, self.id) else self

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class RotateObject(Command):
    """Turn an object to ``rotation`` whole degrees clockwise about the centre of its frame.

    ``anchor`` is where the object sits afterwards, as plain data, when the turn has to move it: a slide keeps the
    turned outline of what is on it on the slide, so a turn that would push a corner off carries the place that keeps
    it on (:meth:`ObjectModel.turned_anchor`), and one undo takes back both. ``None``: the object stays where it is."""

    kind: ClassVar[str] = "core.RotateObject"
    id: str
    rotation: int
    anchor: dict | None = None

    @property
    def label(self) -> str:
        return "Rotate object"

    @property
    def summary(self) -> str:
        return f"Turned an object to {self.rotation}°"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        old = model.get_object(self.id)
        new = old.with_body(rotation=self.rotation)
        if self.anchor is not None:
            new = replace(new, anchor=_anchor_of(ctx, self.anchor))
        model.replace_object(new)
        ctx.emit(model.objects_changed(new.container, changed=(new,)))
        return RotateObject(self.id, old.body.rotation, None if self.anchor is None else old.anchor.to_data())

    def to_data(self) -> dict:
        data: dict[str, Any] = {"id": self.id, "rotation": self.rotation}
        if self.anchor is not None:
            data["anchor"] = dict(self.anchor)
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> RotateObject:
        anchor = data.get("anchor")
        return cls(data["id"], data["rotation"], None if anchor is None else dict(anchor))

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, ObjectModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        return None if _changes_frame(other, self.id) else self

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class SetText(Command):
    """Give an object's text box or shape other words; an image carries no text.

    This replaces the whole paragraph's text at once, so all of it is attributed to whoever ran the command —
    that is what setting a label means, as against typing into a document paragraph character by character
    (which is composes' ``InsertText``, and keeps everybody's runs apart)."""

    kind: ClassVar[str] = "core.SetText"
    id: str
    text: str

    @property
    def label(self) -> str:
        return "Edit text"

    @property
    def summary(self) -> str:
        return f"Wrote {_quote(self.text)}" if self.text.strip() else "Cleared an object's text"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        old = model.get_object(self.id)
        if old.body.paragraph is None:
            raise ValueError("an image carries no text")
        if old.body.paragraph.generated is not None and self.text:
            raise ValueError("an agenda takes no typing: its entries come from the slide titles")
        # whole new words: they make no field, and the fields of the old ones go (the inverse puts them back)
        written = replace(old.body.paragraph, text=plain(self.text), fields=()).written_by(ctx.author)
        new = old.with_body(paragraph=written)
        model.replace_object(new)
        ctx.emit(model.objects_changed(new.container, changed=(new,)))
        # The inverse restores the whole paragraph, not just its words: see SetParagraph.
        return SetParagraph(self.id, old.body.paragraph)

    def to_data(self) -> dict:
        return {"id": self.id, "text": self.text}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetText:
        return cls(data["id"], data["text"])

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, ObjectModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        """Moving or resizing the box does not matter to its words; another text or a removal does."""
        kinds = SetText | SetParagraph | RemoveObject | AddObject
        return None if isinstance(other, kinds) and _target(other) == self.id else self

    def redacted(self) -> Command:
        return SetText(self.id, "")

    def stub(self) -> dict:
        return {"id": self.id}


@core_commands.register
@dataclass(frozen=True)
class SetParagraph(Command):
    """Put a whole paragraph — its words, its style and who wrote which part — into an object at once.

    This is what the inverse of :class:`~claudia_core.SetText` has to be. Setting the text alone would restore
    the words but not their authorship, and undoing somebody's edit would quietly re-attribute the text it
    brought back to whoever pressed undo."""

    kind: ClassVar[str] = "core.SetParagraph"
    id: str
    paragraph: Paragraph

    @property
    def label(self) -> str:
        return "Edit text"

    @property
    def summary(self) -> str:
        words = self.paragraph.text
        return f"Wrote {_quote(words)}" if words.strip() else "Cleared an object's text"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        old = model.get_object(self.id)
        if old.body.paragraph is None:
            raise ValueError("an image carries no text")
        model.replace_object(old.with_body(paragraph=self.paragraph))
        new = model.get_object(self.id)
        ctx.emit(model.objects_changed(new.container, changed=(new,)))
        return SetParagraph(self.id, old.body.paragraph)

    def to_data(self) -> dict:
        return {"id": self.id, "paragraph": self.paragraph.to_data()}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetParagraph:
        return cls(data["id"], Paragraph.from_data(data["paragraph"]))

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, ObjectModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        kinds = SetText | SetParagraph | RemoveObject | AddObject
        return None if isinstance(other, kinds) and _target(other) == self.id else self

    def redacted(self) -> Command:
        return SetParagraph(self.id, self.paragraph.with_text("", ()))

    def stub(self) -> dict:
        return {"id": self.id}


@core_commands.register
@dataclass(frozen=True)
class SetObjectStyle(Command):
    """Put an object under another style of its own: what the *box* looks like — ``fill``, ``stroke`` and
    ``stroke-width`` (D178).

    Not what its words look like; those follow the paragraph's own style (:class:`SetParagraphStyle`), and keeping
    the two apart is the whole point of an object having two styles (D181). Until this command existed an object's
    style was settled by :class:`AddObject` and could never be changed again, which left the style menu with
    nothing to do: picking a style for the shape you have selected is the most ordinary thing it offers.
    """

    kind: ClassVar[str] = "core.SetObjectStyle"
    id: str
    style: str

    @property
    def label(self) -> str:
        return "Object style"

    @property
    def summary(self) -> str:
        return f"put an object under {self.style}"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        old = model.get_object(self.id)
        new = old.with_body(style=self.style)
        model.replace_object(new)  # checks that the style exists, as it checks everything else about an object
        ctx.emit(model.objects_changed(new.container, changed=(new,)))
        return SetObjectStyle(self.id, old.body.style)

    def to_data(self) -> dict:
        return {"id": self.id, "style": self.style}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetObjectStyle:
        return cls(data["id"], data["style"])

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, ObjectModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        kinds = SetObjectStyle | RemoveObject | AddObject
        return None if isinstance(other, kinds) and _target(other) == self.id else self

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class SetParagraphStyle(Command):
    """Put an object's words under another paragraph style.

    This is the object's *text* style, not the object's own: a shape's style says what its background and border
    look like, its paragraph's style says what its words look like (D181). The same core style commands change
    either, because both are entries in the one :class:`~claudia_core.StyleBook`."""

    kind: ClassVar[str] = "core.SetParagraphStyle"
    id: str
    style: str

    @property
    def label(self) -> str:
        return "Paragraph style"

    @property
    def summary(self) -> str:
        return f"put an object's words under {self.style}"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        old = model.get_object(self.id)
        if old.body.paragraph is None:
            raise ValueError("an image carries no text")
        new = old.with_body(paragraph=old.body.paragraph.with_style(self.style))
        model.replace_object(new)
        ctx.emit(model.objects_changed(new.container, changed=(new,)))
        return SetParagraphStyle(self.id, old.body.paragraph.style)

    def to_data(self) -> dict:
        return {"id": self.id, "style": self.style}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetParagraphStyle:
        return cls(data["id"], data["style"])

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, ObjectModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        kinds = SetParagraphStyle | RemoveObject | AddObject
        return None if isinstance(other, kinds) and _target(other) == self.id else self

    def redacted(self) -> Command:
        return self


@core_commands.register
@dataclass(frozen=True)
class SetSnap(Command):
    """Hold or release an object's snap to the grid (E10.15, D214). The grid itself is only a helper the view
    draws, never part of the document, but whether an object follows it is a real, persisted choice with its own
    history entry — so it keeps holding (or not) even if the grid is hidden, and survives for everyone who opens
    the document."""

    kind: ClassVar[str] = "core.SetSnap"
    id: str
    snap: bool

    @property
    def label(self) -> str:
        return "Snap to grid" if self.snap else "Release from grid"

    @property
    def summary(self) -> str:
        return "Snapped an object to the grid" if self.snap else "Released an object from the grid"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        old = model.get_object(self.id)
        new = old.with_body(snap=self.snap)
        model.replace_object(new)
        ctx.emit(model.objects_changed(new.container, changed=(new,)))
        return SetSnap(self.id, old.body.snap)

    def to_data(self) -> dict:
        return {"id": self.id, "snap": self.snap}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetSnap:
        return cls(data["id"], data["snap"])

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, ObjectModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        """Moving, resizing or editing the box does not matter to its snap; another snap change or a
        removal/re-creation does."""
        return None if isinstance(other, SetSnap | RemoveObject | AddObject) and _target(other) == self.id else self

    def redacted(self) -> Command:
        return self


@core_commands.upcaster("core.AddObject", 1)
def _objects_with_descriptions(data: dict) -> dict:
    """Schema 1 bodies had no description and no decorative flag: a picture is described by its import's alt text."""
    body = dict(data["body"])
    imported = body.get("imported")
    body.setdefault("description", "" if imported is None else imported["alt"])
    body.setdefault("decorative", False)
    return {**data, "body": body}


@core_commands.upcaster("core.AddObject", 2)
def _objects_without_renderings(data: dict) -> dict:
    """Schema 2 bodies had no ``rendered``: none of those objects shows a rendered container."""
    return {**data, "body": {**data["body"], "rendered": None}}


@core_commands.register
@dataclass(frozen=True)
class RenameThing(Command):
    """Give an object, a slide, a sheet or a chart tab another name (D550). The id stays, so everything that points at
    the thing (a tag in the chat, a formula) keeps pointing at it. Refused with a sentence when somebody else has that
    name already, whatever kind of thing they are."""

    kind: ClassVar[str] = "core.RenameThing"
    schema: ClassVar[int] = 2  # 2: names are shared with named ranges (D552); see ``legacy_names``
    id: str
    name: str
    legacy_names: bool = False  # written before ranges shared the names: the others are not looked at again

    @property
    def label(self) -> str:
        return "Rename"

    @property
    def summary(self) -> str:
        return f"Renamed something to “{self.name}”"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        name = clean_name(self.name)
        model.check_thing_name(self.id, name, shared=not self.legacy_names)
        old, restores = model.rename_thing(ctx, self.id, name)
        ctx.emit(ThingRenamed(self.id, name))
        if self.id in model.objects:
            changed = model.objects[self.id]
            ctx.emit(model.objects_changed(changed.container, changed=(changed,)))
        undo = RenameThing(self.id, old)
        return Batch((undo, *restores)) if restores else undo

    def to_data(self) -> dict:
        data: dict = {"id": self.id, "name": self.name}
        if self.legacy_names:
            data["legacy_names"] = True
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> RenameThing:
        return cls(data["id"], data["name"], data.get("legacy_names", False))

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, ObjectModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        """A rename undoes cleanly unless the thing was renamed, removed or made again by somebody since."""
        return None if isinstance(other, RenameThing | RemoveObject | AddObject) and _target(other) == self.id else self

    def stub(self) -> dict:
        return {"id": self.id}


@core_commands.upcaster("core.AddObject", 4)
@core_commands.upcaster("core.RenameThing", 1)
def _names_not_yet_shared_with_ranges(data: dict) -> dict:
    """Schema 1 and 4 were written before named ranges shared the names (D552): replay them under the old rule."""
    return {**data, "legacy_names": True}


@core_commands.upcaster("core.AddObject", 5)
def _objects_with_one_pointer(data: dict) -> dict:
    """Schema 5 bodies had a pointer field for each kind of object: the one of the body's kind is its ``ref``."""
    body = data["body"]
    return {**data, "body": ObjectBody._from_legacy(body) if "ref" not in body else body}


@core_commands.upcaster("core.AddObject", 3)
def _objects_without_names(data: dict) -> dict:
    """Schema 3 bodies had no ``name``: those objects have none yet."""
    return {**data, "body": {**data["body"], "name": ""}}


@core_commands.register
@dataclass(frozen=True)
class DescribeObject(Command):
    """Say what an object is to someone who cannot see it, or that it is only decoration (BITV 1.1.1).

    A decorative object has no description, so the two are set together: marking one decorative drops its
    description, and giving a description un-marks it. An object left with neither is simply not described yet —
    the model allows it, a picture's entry points do not. The inverse restores both."""

    kind: ClassVar[str] = "core.DescribeObject"
    id: str
    description: str
    decorative: bool = False

    @property
    def label(self) -> str:
        return "Mark as decorative" if self.decorative else "Describe object"

    @property
    def summary(self) -> str:
        if self.decorative:
            return "Marked an object as decorative"
        if self.description.strip():
            return f"Described an object: {_quote(self.description)}"
        return "Removed an object's description"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        old = model.get_object(self.id)
        new = old.with_body(description=self.description, decorative=self.decorative)
        model.replace_object(new)
        ctx.emit(model.objects_changed(new.container, changed=(new,)))
        return DescribeObject(self.id, old.body.description, old.body.decorative)

    def to_data(self) -> dict:
        return {"id": self.id, "description": self.description, "decorative": self.decorative}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> DescribeObject:
        return cls(data["id"], data["description"], data["decorative"])

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        return model.selection_of(self.id) if isinstance(model, ObjectModel) else ()

    def shifted_by(self, other: Command) -> Command | None:
        """Moving, sizing or retexting the object does not matter to how it is described; another description or
        a removal/re-creation does."""
        return (
            None if isinstance(other, DescribeObject | RemoveObject | AddObject) and _target(other) == self.id else self
        )

    def redacted(self) -> Command:
        return DescribeObject(self.id, "", self.decorative)

    def stub(self) -> dict:
        return {"id": self.id}
