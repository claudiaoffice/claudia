"""The creates document model: slides holding text boxes, shapes and images (E10.1, E10.8).

State: the slides in order, the shape definitions and image assets the document has taken in (so that it opens
the same on any server), and the objects with their stacking order per slide. Objects sit in a slide space of
1600 by 900 integer units; a view scales it, an export (ODP, PPTX) maps it to centimetres or EMU.

What is not here yet: templates and layouts (E10.4), groups, free colours.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar, Self

from claudia_core import CommandRegistry, DocumentModel, ImageAsset, ImageImport, Region, new_registry

from .events import ObjectsChanged
from .region import ObjectSet
from .shapes import ShapeDefinition
from .styles import BUILTIN_STYLES

SLIDE_WIDTH = 1600
SLIDE_HEIGHT = 900
MIN_OBJECT_SIZE = 20  # units; an object is at least this wide and this tall
MAX_OBJECT_TEXT = 20_000  # characters of text in one object
MAX_OBJECTS_PER_SLIDE = 500
ASPECT_TOLERANCE = 1  # units a width may differ from height * aspect (whole units cannot match exactly)
OBJECT_KINDS = ("text", "shape", "image")
FIRST_SLIDE = "s1"  # the slide of a new presentation

_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}")
_FIELDS = ("id", "slide", "kind", "x", "y", "w", "h", "style", "text", "shape", "image", "imported", "snap")


@dataclass(frozen=True)
class SlideObject:
    """One thing on a slide: a text box (``kind`` ``"text"``), a shape (``"shape"``, with the id of its outline)
    or an image (``"image"``, with the id of its :class:`~claudia_core.ImageAsset` and the
    :class:`~claudia_core.ImageImport` record of how it got there).

    ``x``, ``y``, ``w`` and ``h`` are whole units in the slide space; ``style`` is the id of a built-in style.
    ``snap`` is whether the object holds to the grid (E10.15): a helper the view draws, not part of the slide
    itself, but each object's own choice to follow it is real, persisted document state."""

    id: str
    slide: str
    kind: str
    x: int
    y: int
    w: int
    h: int
    style: str
    text: str = ""
    shape: str | None = None
    image: str | None = None
    imported: ImageImport | None = None
    snap: bool = True

    def to_data(self) -> dict:
        """The plain-data form: what the log stores. Carries ``imported`` unmasked (the log is not a client)."""
        data = {name: getattr(self, name) for name in _FIELDS if name != "imported"}
        data["imported"] = None if self.imported is None else self.imported.to_data()
        return data

    def to_data_for(self, viewer: str) -> dict:
        """What ``viewer`` is sent: as :meth:`to_data`, but an image's import record is masked for anyone but the
        person who imported it (a colleague sees "imported from disk", not the importer's own filesystem path)."""
        data = self.to_data()
        if self.imported is not None:
            data["imported"] = self.imported.masked(viewer).to_data()
        return data

    @classmethod
    def from_data(cls, data: dict) -> SlideObject:
        """Inverse of :meth:`to_data`; whether the values make sense is the model's business (``check_object``)."""
        if set(data) != set(_FIELDS):
            raise ValueError("an object has exactly these fields: " + ", ".join(_FIELDS))
        imported = data["imported"]
        return cls(**{**data, "imported": None if imported is None else ImageImport.from_data(imported)})


def _is_whole(value: object) -> bool:
    return type(value) is int


class SlideModel(DocumentModel):
    """A presentation: slides, the shapes it knows and the objects on its slides. See the module description."""

    app: ClassVar[str] = "creates"
    state_schema: ClassVar[int] = 4
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(self) -> None:
        self.slides: list[str] = []
        self.shapes: dict[str, ShapeDefinition] = {}
        self.images: dict[str, ImageAsset] = {}
        self.objects: dict[str, SlideObject] = {}
        self._stack: dict[str, list[str]] = {}  # slide id -> object ids, bottom first

    @classmethod
    def empty(cls) -> Self:
        """A new presentation: one empty slide, ``s1``, so that there is always something to put things on."""
        model = cls()
        model.insert_slide(FIRST_SLIDE)
        return model

    def serialize(self) -> dict:
        return {
            "slides": list(self.slides),
            "shapes": [shape.to_data() for _, shape in sorted(self.shapes.items())],
            "images": [image.to_data() for _, image in sorted(self.images.items())],
            "objects": [obj.to_data() for slide in self.slides for obj in self.objects_on(slide)],
        }

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls()
        model.slides = list(state["slides"])
        model._stack = {slide: [] for slide in model.slides}
        for data in state["shapes"]:
            shape = ShapeDefinition.from_data(data)
            model.shapes[shape.id] = shape
        for data in state["images"]:
            image = ImageAsset.from_data(data)
            model.images[image.id] = image
        for data in state["objects"]:
            obj = SlideObject.from_data(data)
            model.objects[obj.id] = obj
            model._stack[obj.slide].append(obj.id)
        return model

    def region_from_data(self, data: dict) -> Region:
        return ObjectSet.from_data(data)

    # -- reading ---------------------------------------------------------------
    def get(self, object_id: str) -> SlideObject:
        """The object with this id; ``ValueError`` if there is none."""
        try:
            return self.objects[object_id]
        except KeyError:
            raise ValueError(f"no object {object_id!r}") from None

    def objects_on(self, slide: str) -> list[SlideObject]:
        """The objects of a slide, bottom first (the last one is in front)."""
        return [self.objects[object_id] for object_id in self._stack.get(slide, [])]

    def users_of(self, shape_id: str) -> list[str]:
        """The ids of the objects that use this shape."""
        return [obj.id for obj in self.objects.values() if obj.shape == shape_id]

    def users_of_image(self, image_id: str) -> list[str]:
        """The ids of the objects that use this image asset."""
        return [obj.id for obj in self.objects.values() if obj.image == image_id]

    # -- slides ----------------------------------------------------------------
    def insert_slide(self, slide: str, at: int | None = None) -> None:
        """Add a slide at position ``at`` (the end by default)."""
        if not _ID.fullmatch(slide):
            raise ValueError(f"slide id {slide!r}: lower-case letters, digits, '-' and '_', starting with a letter")
        if slide in self.slides:
            raise ValueError(f"slide {slide!r} exists already")
        if at is not None and not 0 <= at <= len(self.slides):
            raise ValueError(f"there is no place {at} among {len(self.slides)} slides")
        self.slides.insert(len(self.slides) if at is None else at, slide)
        self._stack[slide] = []

    def delete_slide(self, slide: str) -> int:
        """Remove an empty slide; returns the place it had."""
        if slide not in self.slides:
            raise ValueError(f"unknown slide {slide!r}")
        if self._stack[slide]:
            raise ValueError(f"slide {slide!r} still has objects; remove them first")
        place = self.slides.index(slide)
        del self.slides[place]
        del self._stack[slide]
        return place

    # -- shapes ----------------------------------------------------------------
    def define_shape(self, shape: ShapeDefinition) -> None:
        """Take a shape's outline into the document."""
        if shape.id in self.shapes:
            raise ValueError(f"shape {shape.id!r} is already defined in this document")
        self.shapes[shape.id] = shape

    def forget_shape(self, shape_id: str) -> ShapeDefinition:
        """Let go of a shape nobody uses; returns it."""
        if shape_id not in self.shapes:
            raise ValueError(f"this document does not know the shape {shape_id!r}")
        users = self.users_of(shape_id)
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

    # -- objects ---------------------------------------------------------------
    def check_object(self, obj: SlideObject) -> None:
        """Raise ``ValueError`` with a sentence if this object cannot exist in this document as it is now."""
        if not isinstance(obj.id, str) or not _ID.fullmatch(obj.id):
            raise ValueError(f"object id {obj.id!r}: lower-case letters, digits, '-' and '_', starting with a letter")
        if obj.slide not in self.slides:
            raise ValueError(f"unknown slide {obj.slide!r}")
        if obj.kind not in OBJECT_KINDS:
            raise ValueError(
                f"unknown kind {obj.kind!r}: an object is a text box ('text'), a shape ('shape') or an image ('image')"
            )
        if obj.style not in BUILTIN_STYLES:
            raise ValueError(f"unknown style {obj.style!r}; the styles are {', '.join(BUILTIN_STYLES)}")
        aspect = self._check_visual(obj)
        self._check_frame(obj, aspect)
        if not isinstance(obj.text, str) or len(obj.text) > MAX_OBJECT_TEXT:
            raise ValueError(f"the text must be text of at most {MAX_OBJECT_TEXT} characters")
        if type(obj.snap) is not bool:
            raise ValueError("snap must be true or false")

    def _check_visual(self, obj: SlideObject) -> float | None:
        """What ``obj.kind`` requires of ``shape``/``image``/``imported``, and the aspect ratio (if any) it keeps."""
        if obj.kind == "text":
            if obj.shape is not None or obj.image is not None or obj.imported is not None:
                raise ValueError("a text box has no shape or image")
            return None
        if obj.kind == "shape":
            if obj.image is not None or obj.imported is not None:
                raise ValueError("a shape object has no image")
            if obj.shape is None:
                raise ValueError("a shape object needs a shape")
            definition = self.shapes.get(obj.shape)
            if definition is None:
                raise ValueError(f"this document does not know the shape {obj.shape!r}")
            return definition.aspect
        # obj.kind == "image"
        if obj.shape is not None:
            raise ValueError("an image object has no shape")
        if obj.image is None or obj.imported is None:
            raise ValueError("an image object needs an image and its import record")
        asset = self.images.get(obj.image)
        if asset is None:
            raise ValueError(f"this document does not know the image {obj.image!r}")
        if obj.imported.asset != obj.image:
            raise ValueError("the import record's asset does not match the object's image")
        return asset.aspect

    @staticmethod
    def _check_frame(obj: SlideObject, aspect: float | None) -> None:
        if not all(_is_whole(v) for v in (obj.x, obj.y, obj.w, obj.h)):
            raise ValueError("x, y, w and h must be whole numbers")
        if obj.w < MIN_OBJECT_SIZE or obj.h < MIN_OBJECT_SIZE:
            raise ValueError(f"the size must be at least {MIN_OBJECT_SIZE} by {MIN_OBJECT_SIZE} units")
        if obj.x < 0 or obj.y < 0 or obj.x + obj.w > SLIDE_WIDTH or obj.y + obj.h > SLIDE_HEIGHT:
            raise ValueError(f"the object must stay on the slide ({SLIDE_WIDTH} by {SLIDE_HEIGHT} units)")
        if aspect is not None and abs(obj.w - aspect * obj.h) > ASPECT_TOLERANCE:
            raise ValueError(f"this shape keeps its proportions (width divided by height is {aspect:g})")

    def insert_object(self, obj: SlideObject, at: int | None = None) -> None:
        """Add a checked object on top of its slide, or at stacking place ``at``."""
        if obj.id in self.objects:
            raise ValueError(f"object {obj.id!r} exists already")
        self.check_object(obj)
        stack = self._stack[obj.slide]
        if len(stack) >= MAX_OBJECTS_PER_SLIDE:
            raise ValueError(f"a slide holds at most {MAX_OBJECTS_PER_SLIDE} objects")
        if at is not None and not 0 <= at <= len(stack):
            raise ValueError(f"there is no stacking place {at} among {len(stack)} objects")
        stack.insert(len(stack) if at is None else at, obj.id)
        self.objects[obj.id] = obj

    def delete_object(self, object_id: str) -> tuple[SlideObject, int]:
        """Take an object away; returns it and the stacking place it had."""
        obj = self.get(object_id)
        stack = self._stack[obj.slide]
        place = stack.index(object_id)
        del stack[place]
        del self.objects[object_id]
        return obj, place

    def replace_object(self, obj: SlideObject) -> SlideObject:
        """Swap in a changed (checked) version of an object that exists; returns the one it replaces."""
        old = self.get(obj.id)
        if obj.slide != old.slide:
            raise ValueError("an object cannot change its slide")
        self.check_object(obj)
        self.objects[obj.id] = obj
        return old

    def changed(
        self, slide: str, *, changed: tuple[SlideObject, ...] = (), removed: tuple[str, ...] = ()
    ) -> ObjectsChanged:
        """The event that tells views what happened on ``slide``, with its stacking order as it is now."""
        return ObjectsChanged(slide, changed, removed, tuple(self._stack[slide]))
