"""claudia-creates: the presentation app. Slides holding text boxes, shapes and images, on the claudia-core
kernel (E10.1, E10.8).

shapes    ShapeDefinition, ShapeLibrary: outlines as JSON files that users can add to
styles    BUILTIN_STYLES: named looks, CSS from an allow-list
model     SlideModel, SlideObject: slides, the shapes and images a document knows, objects and their stacking order
commands  AddObject, MoveObject, ResizeObject, SetText, RemoveObject, DefineShape, ForgetShape, DefineImage,
          ForgetImage, AddSlide, RemoveSlide
region    ObjectSet: the Region of this app (a selection, a lock)
events    ObjectsChanged, ShapesChanged, ImagesChanged, SlidesChanged: what views are told

An image is imported from disk (the clipboard is a later addition); decoding and the import record are
``claudia_core``'s (``ImageAsset``, ``ImageImport``, re-exported there), shared with composes and computes. This
draft has one slide space (1600 by 900 units), three built-in styles and three shapes. Templates, layouts and
groups come later (E10.4).
"""

from . import commands  # noqa: F401  (registers the commands)
from ._version import __version__
from .commands import (
    AddObject,
    AddSlide,
    DefineImage,
    DefineShape,
    ForgetImage,
    ForgetShape,
    MoveObject,
    RemoveObject,
    RemoveSlide,
    ResizeObject,
    SetText,
)
from .events import ImagesChanged, ObjectsChanged, ShapesChanged, SlidesChanged
from .model import (
    ASPECT_TOLERANCE,
    MAX_OBJECT_TEXT,
    MAX_OBJECTS_PER_SLIDE,
    MIN_OBJECT_SIZE,
    OBJECT_KINDS,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    SlideModel,
    SlideObject,
)
from .region import ObjectSet
from .shapes import ShapeDefinition, ShapeError, ShapeLibrary, parse_shape
from .styles import ALLOWED_CSS, BUILTIN_STYLES, Style

__all__ = [
    "ALLOWED_CSS",
    "ASPECT_TOLERANCE",
    "BUILTIN_STYLES",
    "MAX_OBJECTS_PER_SLIDE",
    "MAX_OBJECT_TEXT",
    "MIN_OBJECT_SIZE",
    "OBJECT_KINDS",
    "SLIDE_HEIGHT",
    "SLIDE_WIDTH",
    "AddObject",
    "AddSlide",
    "DefineImage",
    "DefineShape",
    "ForgetImage",
    "ForgetShape",
    "ImagesChanged",
    "MoveObject",
    "ObjectSet",
    "ObjectsChanged",
    "RemoveObject",
    "RemoveSlide",
    "ResizeObject",
    "SetText",
    "ShapeDefinition",
    "ShapeError",
    "ShapeLibrary",
    "ShapesChanged",
    "SlideModel",
    "SlideObject",
    "SlidesChanged",
    "Style",
    "__version__",
    "parse_shape",
]
