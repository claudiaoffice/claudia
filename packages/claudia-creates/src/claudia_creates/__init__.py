"""claudia-creates: the presentation app. Slides holding text boxes and shapes, on the claudia-core kernel (E10.1).

shapes    ShapeDefinition, ShapeLibrary: outlines as JSON files that users can add to
styles    BUILTIN_STYLES: named looks, CSS from an allow-list
model     SlideModel, SlideObject: slides, the shapes a document knows, objects and their stacking order
commands  AddObject, MoveObject, ResizeObject, SetText, RemoveObject, DefineShape, ForgetShape, AddSlide, RemoveSlide
region    ObjectSet: the Region of this app (a selection, a lock)
events    ObjectsChanged, ShapesChanged, SlidesChanged: what views are told

This first draft has one slide space (1600 by 900 units), two built-in styles and three shapes. Templates, layouts,
images and groups come later (E10.4, E10.8).
"""

from . import commands  # noqa: F401  (registers the commands)
from ._version import __version__
from .commands import (
    AddObject,
    AddSlide,
    DefineShape,
    ForgetShape,
    MoveObject,
    RemoveObject,
    RemoveSlide,
    ResizeObject,
    SetText,
)
from .events import ObjectsChanged, ShapesChanged, SlidesChanged
from .model import (
    ASPECT_TOLERANCE,
    MAX_OBJECT_TEXT,
    MAX_OBJECTS_PER_SLIDE,
    MIN_OBJECT_SIZE,
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
    "SLIDE_HEIGHT",
    "SLIDE_WIDTH",
    "AddObject",
    "AddSlide",
    "DefineShape",
    "ForgetShape",
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
