"""claudia-computes: the spreadsheet app, here only the mini-port that proves claudia-core.

refs      CellRef / RangeRef / structural edits (from the demo)
model     WorkbookModel, CellAnchor, SheetObject, Chart: sheets, typed cells, and this app's own part of an object
commands  AddSheet, RemoveSheet, SetCells, Structure, ResizeLines, AddChart, RemoveChart (objects and diagrams: core)
name_commands  DefineName, RemoveName, RenameName, RestoreNames: named ranges and tables (E6.5)
names     NamedRange, Names: what a name is, where it is looked up, and which cells ``Sales[Amount]`` means
charts    ChartSpec: what a diagram draws, computes' own ``DiagramDefinition`` (E6.6)
region    CellRegion: moves with structural edits (core's ``ObjectSet``, re-exported, does not)
styles    BUILTIN_STYLES: the styles a workbook starts with, as core StyleDef entries in the document's own book
entry     parse_input: what typing into a cell means


A floating object is a shared ``ObjectBody`` plus a ``CellAnchor``: only the anchor is this app's. The anchor and
the object's pixel size never change because of a row/column insert, delete or resize — only ``MoveObject`` (the
person dragging it) moves it. Placing, stacking, moving, resizing, rotating, styling and the image, shape and
diagram assets are ``claudia_core.objects``, shared with creates and composes.

A chart (E6.6) may be shown as its own tab (``Chart``, ``AddChart``/``RemoveChart``, this app's own) or as a
floating diagram object on a sheet (``ObjectBody.diagram``, shared) — the two may show the very same
``ChartSpec``, exactly as two image objects may share one image asset.

functions.help  function_catalog/search_functions/get_function: every cell function, library and core alike, as one
searchable list (E13.5's "Documentation" for computes).

"""

# The object commands, the object types and the object region are shared by all three apps and live in
# ``claudia_core`` (E10.16). They are re-exported here so that an app package names everything it can do.
from claudia_core import (  # noqa: F401
    AddObject,
    DefineDiagram,
    DefineImage,
    DefineShape,
    DiagramDefinition,
    ForgetDiagram,
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
    UpdateDiagram,
    VisualObject,
    paragraph_for,
)

from . import commands, name_commands  # noqa: F401  (registers the commands)
from ._version import __version__
from .charts import CHART_KINDS, ChartError, ChartSpec
from .commands import AddChart, AddSheet, RemoveChart, RemoveSheet, ResizeLines, SetCells, Structure
from .entry import parse_input
from .events import ChartsChanged, DiagramsChanged, ImagesChanged, NamesChanged, ObjectsChanged, ShapesChanged
from .functions.help import FunctionHelp, function_catalog, get_function, search_functions
from .model import (
    MAX_OBJECTS_PER_SHEET,
    MIN_OBJECT_SIZE,
    OBJECT_KINDS,
    CellAnchor,
    Chart,
    Content,
    Sheet,
    SheetObject,
    WorkbookModel,
    content_of,
)
from .name_commands import DefineName, RemoveName, RenameName, RestoreNames
from .names import PURPOSES, NamedRange, Names
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
    "__version__",
    "AddChart",
    "AddObject",
    "AddSheet",
    "builtin_styles",
    "BUILTIN_STYLES",
    "CellAnchor",
    "CellRef",
    "CellRegion",
    "Chart",
    "CHART_KINDS",
    "ChartError",
    "ChartsChanged",
    "ChartSpec",
    "column_name",
    "Content",
    "content_of",
    "DEFAULT_STYLE",
    "DefineDiagram",
    "DefineName",
    "DefineImage",
    "DefineShape",
    "DeleteCols",
    "DeleteRows",
    "DiagramDefinition",
    "DiagramsChanged",
    "ForgetDiagram",
    "ForgetImage",
    "FunctionHelp",
    "ForgetShape",
    "ImagesChanged",
    "InsertCols",
    "InsertRows",
    "MAX_OBJECTS_PER_SHEET",
    "MIN_OBJECT_SIZE",
    "MoveObject",
    "NamedRange",
    "Names",
    "NamesChanged",
    "OBJECT_KINDS",
    "PURPOSES",
    "ObjectBody",
    "ObjectsChanged",
    "ObjectSet",
    "Paragraph",
    "paragraph_for",
    "parse_input",
    "parse_range_ref",
    "RangeRef",
    "RefParseError",
    "RemoveChart",
    "RemoveName",
    "RenameName",
    "RestoreNames",
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
    "UpdateDiagram",
    "VisualObject",
    "WorkbookModel",
    "function_catalog",
    "get_function",
    "search_functions",
]
