"""claudia-creates: the presentation app. Slides holding text boxes, shapes and images, on the claudia-core
kernel (E10.1, E10.8, E10.16).

shapes    ShapeLibrary: outlines read from JSON files on disk that users can add to (the format itself is
          ``claudia_core.shapes``)
styles    BUILTIN_STYLES: the styles a presentation starts with, as core StyleDef entries in the document's own book
model     SlideModel, SlideAnchor, SlideObject: slides, the slide space, and what is this app's own about an object
commands  AddSlide, RemoveSlide, SetSlideNotes, SetSlideTime, SetPrintSetup — everything about objects is shared
          and comes from ``claudia_core``, and so is SetLanguage (D917)
printing  PrintSetup: how the slides are printed, the layout and the kernel's PageSetup (D917)
events    SlidesChanged, SlideNotesChanged, SlideTimeChanged, PrintSetupChanged (``ObjectsChanged``,
          ``ShapesChanged``, ``ImagesChanged`` are core's, re-exported)

An object is a shared ``ObjectBody`` plus a ``SlideAnchor``: only the anchor is this app's. Placing, stacking,
moving, resizing, rotating, styling and the image and shape assets are ``claudia_core.objects``, shared with
composes and computes. This draft has one slide space (1600 by 900 units), three built-in styles and three
shapes. Templates, layouts and groups come later (E10.4).
"""

# The object commands, the object types and the object region are shared by all three apps and live in
# ``claudia_core`` (E10.16). They are re-exported here so that an app package names everything it can do.
# The shape *format* is core's, shared by all three apps (E10.16); only the on-disk library is this
# package's. Both are re-exported here, where they have always been imported from.
from claudia_core import (  # noqa: F401
    BOX,
    FORMAT,
    AddObject,
    DefineImage,
    DefineShape,
    DescribeObject,
    ForgetImage,
    ForgetShape,
    MoveObject,
    ObjectBody,
    ObjectSet,
    Paragraph,
    RemoveObject,
    ResizeObject,
    RotateObject,
    Run,
    SetLanguage,
    SetParagraphStyle,
    SetSnap,
    SetText,
    ShapeDefinition,
    ShapeError,
    VisualObject,
    paragraph_for,
    parse_shape,
)

from . import commands  # noqa: F401  (registers the commands)
from ._version import __version__
from .commands import AddSlide, RemoveSlide, SetPrintSetup, SetSlideNotes, SetSlideTime
from .events import (
    ImagesChanged,
    ObjectsChanged,
    PrintSetupChanged,
    ShapesChanged,
    SlideNotesChanged,
    SlidesChanged,
    SlideTimeChanged,
)
from .model import (
    FIRST_SLIDE,
    MAX_NOTES_LENGTH,
    MAX_SLIDE_SECONDS,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    SlideAnchor,
    SlideModel,
    SlideObject,
)
from .printing import LAYOUTS, PrintSetup, PrintSetupError
from .shapes import BUILTIN_DIRECTORY, ShapeLibrary
from .styles import ALLOWED_CSS, BUILTIN_STYLES, DEFAULT_STYLE, builtin_styles

__all__ = [
    "__version__",
    "AddObject",
    "AddSlide",
    "ALLOWED_CSS",
    "BOX",
    "BUILTIN_DIRECTORY",
    "builtin_styles",
    "BUILTIN_STYLES",
    "DEFAULT_STYLE",
    "DefineImage",
    "DefineShape",
    "DescribeObject",
    "FIRST_SLIDE",
    "ForgetImage",
    "ForgetShape",
    "FORMAT",
    "ImagesChanged",
    "LAYOUTS",
    "MAX_NOTES_LENGTH",
    "MAX_SLIDE_SECONDS",
    "MoveObject",
    "ObjectBody",
    "PrintSetup",
    "PrintSetupChanged",
    "PrintSetupError",
    "ObjectsChanged",
    "ObjectSet",
    "Paragraph",
    "paragraph_for",
    "parse_shape",
    "RemoveObject",
    "RemoveSlide",
    "SetLanguage",
    "ResizeObject",
    "RotateObject",
    "Run",
    "SetParagraphStyle",
    "SetPrintSetup",
    "SetSlideNotes",
    "SetSlideTime",
    "SetSnap",
    "SetText",
    "ShapeDefinition",
    "ShapeError",
    "ShapeLibrary",
    "ShapesChanged",
    "SLIDE_HEIGHT",
    "SLIDE_WIDTH",
    "SlideAnchor",
    "SlideModel",
    "SlideObject",
    "SlideNotesChanged",
    "SlidesChanged",
    "SlideTimeChanged",
    "VisualObject",
]
