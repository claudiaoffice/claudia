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
commands below — define and forget a shape or an image, add, remove, move, resize, retext, rotate and snap an
object — are written once, against the anchor protocol, and are the same command in every app.

An anchor crosses the wire and the log as plain data, exactly as a :class:`~claudia_core.Region` does, and is
read back by the one app-specific door, :meth:`~claudia_core.ObjectModel.anchor_from_data`. A command
therefore stays what the kernel requires it to be: immutable plain data, buildable without a model.

What an app brings: its anchor type, ``containers()``, ``check_anchor``, ``anchor_from_data``, and whatever its
own geometry needs. What it does *not* bring is its own copy of place-an-object, take-it-away, stack-it, size-it
or style-it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, Self, TypeIs, runtime_checkable

from .assets import ImageAsset, ImageImport
from .commands import Command, CommandRegistry, core_commands
from .paragraphs import Paragraph
from .shapes import ShapeDefinition

if TYPE_CHECKING:
    from .context import Context

#: Kinds of object every app understands. A text box carries only words; a shape carries an outline and may carry
#: words; an image carries an asset.
OBJECT_KINDS: tuple[str, ...] = ("text", "shape", "image")

MIN_OBJECT_SIZE = 20  # an object is at least this wide and this tall, in its app's own units
MAX_OBJECTS_PER_CONTAINER = 500
MAX_SELECTION = 64  # objects in one selection that arrives from a client
ASPECT_TOLERANCE = 1  # units a width may differ from height * aspect (whole units cannot match exactly)
MAX_LISTED_TEXT = 40  # characters of an object's text that a history sentence quotes

_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}")
_BODY_FIELDS = ("id", "kind", "w", "h", "style", "paragraph", "shape", "image", "imported", "rotation", "snap")


def _is_whole(value: object) -> TypeIs[int]:
    """``True`` for a plain ``int`` (not a ``bool``), narrowing the type for the caller."""
    return type(value) is int


def paragraph_for(object_id: str, style: str, text: str = "", author: str | None = None) -> Paragraph:
    """The paragraph a new text box or shape starts with.

    It takes the object's own id (it is the only paragraph in there, so nothing else can collide with it) and,
    to begin with, the object's own style — so a new object looks exactly as it did before paragraphs existed,
    and pointing its words at a different style later is a deliberate act rather than a migration."""
    return Paragraph(object_id, style, text).written_by(author)


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
    ``shape`` is the id of an outline the document knows, ``image`` the id of an
    :class:`~claudia_core.ImageAsset` and ``imported`` the record of how that image got there. ``rotation`` is
    whole degrees clockwise. ``snap`` is whether the object holds to its app's grid (E10.15, D151): the grid is a
    helper the view draws, but each object's own choice to follow it is real, persisted document state."""

    id: str
    kind: str
    w: int
    h: int
    style: str
    paragraph: Paragraph | None = None
    shape: str | None = None
    image: str | None = None
    imported: ImageImport | None = None
    rotation: int = 0
    snap: bool = True

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
        (:meth:`~claudia_core.ObjectModel.check_object`)."""
        if set(data) != set(_BODY_FIELDS):
            raise ValueError("an object body has exactly these fields: " + ", ".join(_BODY_FIELDS))
        imported, paragraph = data["imported"], data["paragraph"]
        return cls(
            **{
                **data,
                "imported": None if imported is None else ImageImport.from_data(imported),
                "paragraph": None if paragraph is None else Paragraph.from_data(paragraph),
            }
        )


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


# --------------------------------------------------------------------------- the model mixin
class ObjectModel[A: Anchor]:
    """Objects, their stacking order, their shapes and their image assets: the state and the operations all three
    apps share.

    An app's model inherits this next to :class:`~claudia_core.DocumentModel` and brings only what is its own:

    * ``containers()`` — the ids of the slides, sheets or paragraphs objects may sit on, in order.
    * ``check_anchor(anchor, body)`` — whether an object with this body fits where the anchor says it does (a
      slide's bounds, a cell of the sheet, an offset inside a paragraph). Raise ``ValueError`` with a sentence.
    * ``anchor_from_data(data)`` — read its own anchor.
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
        self._stack: dict[str, list[str]] = {}  # container id -> object ids, bottom first

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

    def users_of_image(self, image_id: str) -> list[str]:
        """The ids of the objects that use this image asset."""
        return [obj.id for obj in self.objects.values() if obj.body.image == image_id]

    def users_of_shape(self, shape_id: str) -> list[str]:
        """The ids of the objects that use this shape outline."""
        return [obj.id for obj in self.objects.values() if obj.body.shape == shape_id]

    def style_in_use(self, style_id: str) -> bool:
        """Does any object have this style? (Asked by the core style commands before they take a style back.)"""
        return any(obj.body.style == style_id for obj in self.objects.values())

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
        return self.images.pop(image_id)

    # -- checking ----------------------------------------------------------------
    def check_object(self, obj: VisualObject[A]) -> None:
        """``ValueError`` with a sentence if this object cannot exist in this document as it is now.

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
        if styles is not None and body.style not in styles:
            raise ValueError(f"unknown style {body.style!r}")
        aspect = self._check_visual(body)
        self._check_size(body, aspect)
        if body.kind == "image":
            if body.paragraph is not None:
                raise ValueError("an image carries no text")
        else:
            if body.paragraph is None:
                raise ValueError(f"a {body.kind} object carries a paragraph, even an empty one")
            body.paragraph.check()
            styles = getattr(self, "styles", None)
            if styles is not None and body.paragraph.style not in styles:
                raise ValueError(f"unknown paragraph style {body.paragraph.style!r}")
        if not _is_whole(body.rotation) or not 0 <= body.rotation < 360:
            raise ValueError("the rotation must be whole degrees from 0 to 359")
        if type(body.snap) is not bool:
            raise ValueError("snap must be true or false")
        self.check_anchor(obj.anchor, body)

    def _check_visual(self, body: ObjectBody) -> float | None:
        """What ``body.kind`` requires of ``shape``/``image``/``imported``, and the aspect ratio (if any) it
        keeps."""
        if body.kind == "text":
            if body.shape is not None or body.image is not None or body.imported is not None:
                raise ValueError("a text box has no shape or image")
            return None
        if body.kind == "shape":
            if body.image is not None or body.imported is not None:
                raise ValueError("a shape object has no image")
            if body.shape is None:
                raise ValueError("a shape object needs a shape")
            definition = self.shapes.get(body.shape)
            if definition is None:
                raise ValueError(f"this document does not know the shape {body.shape!r}")
            return definition.aspect
        # body.kind == "image"
        if body.shape is not None:
            raise ValueError("an image object has no shape")
        if body.image is None or body.imported is None:
            raise ValueError("an image object needs an image and its import record")
        asset = self.images.get(body.image)
        if asset is None:
            raise ValueError(f"this document does not know the image {body.image!r}")
        if body.imported.asset != body.image:
            raise ValueError("the import record's asset does not match the object's image")
        return asset.aspect

    def _check_size(self, body: ObjectBody, aspect: float | None) -> None:
        if not all(_is_whole(value) for value in (body.w, body.h)):
            raise ValueError("w and h must be whole numbers")
        if body.w < self.min_object_size or body.h < self.min_object_size:
            raise ValueError(f"the size must be at least {self.min_object_size} by {self.min_object_size} units")
        if aspect is not None and abs(body.w - aspect * body.h) > ASPECT_TOLERANCE:
            raise ValueError(f"this object keeps its proportions (width divided by height is {aspect:g})")

    # -- changing (used by the commands) -----------------------------------------
    def insert_object(self, obj: VisualObject[A], at: int | None = None) -> None:
        """Add a checked object on top of its container, or at stacking place ``at``."""
        if obj.id in self.objects:
            raise ValueError(f"object {obj.id!r} exists already")
        self.check_object(obj)
        stack = self._stack[obj.container]
        if len(stack) >= self.max_objects_per_container:
            raise ValueError(f"a container holds at most {self.max_objects_per_container} objects")
        if at is not None and not 0 <= at <= len(stack):
            raise ValueError(f"there is no stacking place {at} among {len(stack)} objects")
        stack.insert(len(stack) if at is None else at, obj.id)
        self.objects[obj.id] = obj

    def delete_object(self, object_id: str) -> tuple[VisualObject[A], int]:
        """Take an object away; returns it and the stacking place it had."""
        obj = self.get_object(object_id)
        stack = self._stack[obj.container]
        place = stack.index(object_id)
        del stack[place]
        del self.objects[object_id]
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

    def restore_objects(
        self,
        objects: Iterable[dict],
        images: Iterable[dict] = (),
        shapes: Iterable[dict] = (),
    ) -> None:
        """Put back what the three ``*_to_data`` methods stored (the containers must already exist)."""
        for data in shapes:
            shape = ShapeDefinition.from_data(data)
            self.shapes[shape.id] = shape
        for data in images:
            image = ImageAsset.from_data(data)
            self.images[image.id] = image
        for data in objects:
            obj = VisualObject.from_data(data, self.anchor_from_data)
            self.objects[obj.id] = obj
            self._stack.setdefault(obj.container, []).append(obj.id)


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
        MoveObject | ResizeObject | SetText | SetParagraph | SetSnap | SetParagraphStyle | RotateObject | RemoveObject
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
        return self


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
class AddObject(Command):
    """Put a text box, a shape or an image on a slide, a sheet or a paragraph: on top of the others, or at
    stacking place ``at``.

    The body is the shared part; ``anchor`` is plain data the app reads back (see the module description)."""

    kind: ClassVar[str] = "core.AddObject"
    body: ObjectBody
    anchor: dict
    at: int | None = None

    @property
    def object_id(self) -> str:
        """The id of the object this command adds."""
        return self.body.id

    @property
    def label(self) -> str:
        return {"text": "Add text box", "shape": "Add shape", "image": "Add image"}[self.body.kind]

    @property
    def summary(self) -> str:
        if self.body.kind == "text":
            words = self.body.paragraph.text if self.body.paragraph else ""
            return f"Added a text box: {_quote(words)}" if words.strip() else "Added a text box"
        if self.body.kind == "image":
            alt = self.body.imported.alt if self.body.imported else ""
            return f"Added an image: {_quote(alt)}" if alt.strip() else "Added an image"
        return f"Added a {self.body.shape}"

    def apply(self, ctx: Context) -> Command:
        model = _host(ctx)
        obj = VisualObject(self.body, _anchor_of(ctx, self.anchor))
        model.insert_object(obj, self.at)
        ctx.emit(model.objects_changed(obj.container, changed=(obj,)))
        return RemoveObject(obj.id)

    def to_data(self) -> dict:
        return {"body": self.body.to_data(), "anchor": dict(self.anchor), "at": self.at}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> AddObject:
        return cls(ObjectBody.from_data(data["body"]), dict(data["anchor"]), data.get("at"))

    def regions(self, model: object) -> tuple[ObjectSet, ...]:
        container = self.anchor.get("container")
        return (ObjectSet(container, frozenset({self.object_id})),) if isinstance(container, str) else ()

    def shifted_by(self, other: Command) -> Command | None:
        """Bringing an object back is refused when somebody made another one with its id, or took its shape or
        image away."""
        if isinstance(other, AddObject) and other.object_id == self.object_id:
            return None
        if isinstance(other, ForgetShape) and other.id == self.body.shape:
            return None
        return None if isinstance(other, ForgetImage) and other.id == self.body.image else self

    def redacted(self) -> Command:
        # The object stays, its words go — but a paragraph that exists must keep existing (an empty one), or the
        # body would no longer be a valid object of its kind.
        emptied = None if self.body.paragraph is None else self.body.paragraph.with_text("", ())
        return AddObject(replace(self.body, paragraph=emptied), self.anchor, self.at)

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
    """Turn an object to ``rotation`` whole degrees clockwise; its frame stays."""

    kind: ClassVar[str] = "core.RotateObject"
    id: str
    rotation: int

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
        model.replace_object(new)
        ctx.emit(model.objects_changed(new.container, changed=(new,)))
        return RotateObject(self.id, old.body.rotation)

    def to_data(self) -> dict:
        return {"id": self.id, "rotation": self.rotation}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> RotateObject:
        return cls(data["id"], data["rotation"])

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
        written = old.body.paragraph.with_text(self.text, ()).written_by(ctx.author)
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
    """Hold or release an object's snap to the grid (E10.15, D151). The grid itself is only a helper the view
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
