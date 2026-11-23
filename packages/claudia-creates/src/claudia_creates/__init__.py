"""claudia-creates: the presentation app. Slides holding text boxes, shapes and images, on the claudia-core
kernel (E10.1, E10.8, E10.16).

shapes    ShapeLibrary: outlines read from JSON files on disk that users can add to (the format itself is
          ``claudia_core.shapes``)
styles    BUILTIN_STYLES: the styles a presentation starts with, as core StyleDef entries in the document's own book
model     SlideModel, SlideObject: slides and what is this app's own about an object (the slide, its frame and anchor
          are claudia_core.slides, D1470)
commands  AddSlide, RemoveSlide, SetSlideNotes, SetSlideTime, SetPrintSetup — everything about objects is shared
          and comes from ``claudia_core``, and so is SetLanguage (D917)
printing  PrintSetup: how the slides are printed, the layout and the kernel's PageSetup (D917)
events    SlidesChanged, SlideNotesChanged, SlideTimeChanged, PrintSetupChanged (``ObjectsChanged``,
          ``AssetsChanged`` are core's, re-exported)

An object is a shared ``ObjectBody`` plus a ``SlideAnchor``: only the anchor is this app's. Placing, stacking,
moving, resizing, rotating, styling and the image and shape assets are ``claudia_core.objects``, shared with
composes and computes. This draft has one slide space (1600 by 900 units), three built-in styles and three
shapes. Templates, layouts and groups come later (E10.4).
"""

# The object commands, the object types and the object region are shared by all three apps and live in
# ``claudia_core`` (E10.16). They are re-exported here so that an app package names everything it can do.
# The shape *format* is core's, shared by all three apps (E10.16); only the on-disk library is this
# package's. Both are re-exported here, where they have always been imported from. So are the slide's frame and anchor,
# which are core's since computes has slides too (D1470).
from claudia_core import (  # noqa: F401
    BOX,
    FORMAT,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    AddObject,
    DescribeObject,
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
    SlideAnchor,
    VisualObject,
    paragraph_for,
    parse_shape,
)

from . import commands, layout_commands  # noqa: F401  (registers the commands)
from ._version import __version__
from .commands import AddSlide, RemoveSlide, SetPrintSetup, SetSlideNotes, SetSlideTime
from .events import (
    LayoutsChanged,
    ObjectsChanged,
    PrintSetupChanged,
    SlideLayoutChanged,
    SlideNotesChanged,
    SlidesChanged,
    SlideTimeChanged,
    TemplateChanged,
)
from .layout_commands import DefineLayout, HideLayout, MoveLayout, RemoveLayout, RenameLayout, SetSlideLayout
from .model import (
    BASIC_LAYOUT,
    FIRST_SLIDE,
    MAX_NOTES_LENGTH,
    MAX_SLIDE_SECONDS,
    SlideModel,
    SlideObject,
)
from .printing import LAYOUTS, PrintSetup, PrintSetupError
from .shapes import BUILTIN_DIRECTORY, ShapeLibrary
from .styles import ALLOWED_CSS, BUILTIN_STYLES, DEFAULT_STYLE, builtin_styles
from .template import (
    SetTemplate,
    Template,
    TemplateRefused,
    basic_template,
    check_template,
    plan_change_template,
    plan_change_theme,
    start_from_template,
    template_state,
)
from .template_info import TemplateInfo

__all__ = [
    "__version__",
    "AddObject",
    "AddSlide",
    "BASIC_LAYOUT",
    "DefineLayout",
    "HideLayout",
    "MoveLayout",
    "RenameLayout",
    "LayoutsChanged",
    "TemplateChanged",
    "RemoveLayout",
    "SlideLayoutChanged",
    "ALLOWED_CSS",
    "BOX",
    "BUILTIN_DIRECTORY",
    "builtin_styles",
    "BUILTIN_STYLES",
    "DEFAULT_STYLE",
    "DescribeObject",
    "FIRST_SLIDE",
    "FORMAT",
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
    "basic_template",
    "plan_change_template",
    "plan_change_theme",
    "check_template",
    "start_from_template",
    "template_state",
    "SetLanguage",
    "ResizeObject",
    "RotateObject",
    "Run",
    "SetParagraphStyle",
    "SetPrintSetup",
    "SetSlideLayout",
    "SetTemplate",
    "Template",
    "TemplateInfo",
    "TemplateRefused",
    "SetSlideNotes",
    "SetSlideTime",
    "SetSnap",
    "SetText",
    "SLIDE_HEIGHT",
    "SLIDE_WIDTH",
    "SlideAnchor",
    "ShapeDefinition",
    "ShapeError",
    "ShapeLibrary",
    "SlideModel",
    "SlideObject",
    "SlideNotesChanged",
    "SlidesChanged",
    "SlideTimeChanged",
    "VisualObject",
]
