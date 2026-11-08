"""claudia-computes: the spreadsheet app, here only the mini-port that proves claudia-core.

refs      CellRef / RangeRef / structural edits (from the demo)
model     WorkbookModel, CellAnchor, SheetObject: sheets, typed cells, and this app's own part of an object
commands  AddSheet, RemoveSheet, SetCells, Structure, ResizeLines (objects are shared: see ``claudia_core``)
region    CellRegion: moves with structural edits (core's ``ObjectSet``, re-exported, does not)
styles    BUILTIN_STYLES: the styles a workbook starts with, as core StyleDef entries in the document's own book
entry     parse_input: what typing into a cell means

A floating object is a shared ``ObjectBody`` plus a ``CellAnchor``: only the anchor is this app's. The anchor and
the object's pixel size never change because of a row/column insert, delete or resize — only ``MoveObject`` (the
person dragging it) moves it. Placing, stacking, moving, resizing, rotating, styling and the image and shape
assets are ``claudia_core.objects``, shared with creates and composes.
"""

# The object commands, the object types and the object region are shared by all three apps and live in
# ``claudia_core`` (E10.16). They are re-exported here so that an app package names everything it can do.
from claudia_core import (  # noqa: F401
    AddObject,
    DefineImage,
    DefineShape,
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
    SetParagraphStyle,
    SetSnap,
    SetText,
    VisualObject,
    paragraph_for,
)

from . import commands  # noqa: F401  (registers the commands)
from .commands import AddSheet, RemoveSheet, ResizeLines, SetCells, Structure
from .entry import parse_input
from .events import ImagesChanged, ObjectsChanged, ShapesChanged
from .model import (
    MAX_OBJECTS_PER_SHEET,
    MIN_OBJECT_SIZE,
    OBJECT_KINDS,
    CellAnchor,
    Content,
    Sheet,
    SheetObject,
    WorkbookModel,
    content_of,
)
from .refs import (
    CellRef,
    DeleteCols,
    DeleteRows,
    InsertCols,
    InsertRows,
    RangeRef,
    RefParseError,
    SheetId,
    column_name,
    parse_range_ref,
)
from .region import CellRegion
from .styles import BUILTIN_STYLES, DEFAULT_STYLE, builtin_styles

__all__ = [
    "AddObject",
    "AddSheet",
    "builtin_styles",
    "BUILTIN_STYLES",
    "CellAnchor",
    "CellRef",
    "CellRegion",
    "column_name",
    "Content",
    "content_of",
    "DEFAULT_STYLE",
    "DefineImage",
    "DefineShape",
    "DeleteCols",
    "DeleteRows",
    "ForgetImage",
    "ForgetShape",
    "ImagesChanged",
    "InsertCols",
    "InsertRows",
    "MAX_OBJECTS_PER_SHEET",
    "MIN_OBJECT_SIZE",
    "MoveObject",
    "OBJECT_KINDS",
    "ObjectBody",
    "ObjectsChanged",
    "ObjectSet",
    "Paragraph",
    "paragraph_for",
    "parse_input",
    "parse_range_ref",
    "RangeRef",
    "RefParseError",
    "RemoveObject",
    "RemoveSheet",
    "ResizeLines",
    "ResizeObject",
    "RotateObject",
    "Run",
    "SetCells",
    "SetParagraphStyle",
    "SetSnap",
    "SetText",
    "ShapesChanged",
    "Sheet",
    "SheetId",
    "SheetObject",
    "Structure",
    "VisualObject",
    "WorkbookModel",
]
