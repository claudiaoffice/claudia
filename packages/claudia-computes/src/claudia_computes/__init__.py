"""claudia-computes: the spreadsheet app, here only the mini-port that proves claudia-core.

refs      CellRef / RangeRef / structural edits (from the demo)
model     WorkbookModel, CellAnchor, SheetObject, Tab: sheets and slides in one order of tabs, typed cells
commands  AddSheet, AddSlide, SetCells, Structure, ResizeLines, SetCellStyle, their inverses (rest: core)
chart_steps  NewChart, as_new_slide, on_slide, on_sheet, to_new_slide, removal: what a step with a chart takes along
heavy     ApplyCalculated, in commands: a worker's result for a deferred heavy call (E4.4, D37, D1314)
cellstyles CellStyles: a sheet's style ranges, in layers, for the box and the words of its cells (E6.13, D307)
name_commands  DefineName, RemoveName, RenameName, RestoreNames: named ranges and tables (E6.5)
names     NamedRange, Names: what a name is, where it is looked up, and which cells ``Sales[Amount]`` means
charts    ChartSpec: what a diagram draws, computes' own ``DiagramDefinition`` (E6.6)
region    CellRegion: moves with structural edits (core's ``ObjectSet``, re-exported, does not)
styles    BUILTIN_STYLES: the styles a workbook starts with, as core StyleDef entries in the document's own book
entry     parse_input: what typing into a cell means
pivot     PivotDefinition, ValueField, PivotFilter, PivotLabels: what a pivot table is (E6.30)
pivot_sql, pivot_render  a pivot as the SQL query it is, and that query's answer as a grid: compute_pivot
pivots, pivot_commands  PivotEntry, Pivots, create_pivot/update_pivot/delete_pivot: pivots in a workbook (E6.30)
search    scan and plan_replacement: search and replace in text, formulas and values (E6.20)


A floating object is a shared ``ObjectBody`` plus a ``CellAnchor``: only the anchor is this app's. The anchor and
the object's pixel size never change because of a row/column insert, delete or resize — only ``MoveObject`` (the
person dragging it) moves it. Placing, stacking, moving, resizing, rotating, styling and the image, shape and
diagram assets are ``claudia_core.objects``, shared with creates and composes.

A chart (E6.6) is an object on a sheet or a slide (``ObjectBody.diagram``, shared) with a ``ChartSpec`` of its own
(E6.31, D1475); :mod:`~claudia_computes.chart_steps` makes, moves and removes it with what it takes along.

functions.help  function_catalog/search_functions/get_function: every cell function, library and core alike, as one
searchable list (E13.5's "Documentation" for computes).

"""

# The object commands, the object types and the object region are shared by all three apps and live in
# ``claudia_core`` (E10.16). They are re-exported here so that an app package names everything it can do.
from claudia_core import (  # noqa: F401
    AddObject,
    DescribeObject,
    DiagramDefinition,
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

from . import commands, name_commands, pivot_commands  # noqa: F401  (registers the commands)
from ._version import __version__
from .cellstyles import CELL_SLOTS, DEFAULT_CELL_STYLE, LAYERS, MAX_STYLE_RANGES, CellStyles, layer_of
from .charts import CHART_KINDS, ChartError, ChartSpec
from .commands import (
    AddSheet,
    AddSlide,
    ApplyCalculated,
    RemoveSheet,
    RemoveSlide,
    Resample,
    ResizeLines,
    SetCells,
    SetCellStyle,
    SetPrintPage,
    SetRandomSeed,
    SetSheetPrint,
    Structure,
)
from .entry import parse_input
from .events import (
    CellStylesChanged,
    NamesChanged,
    ObjectsChanged,
    PivotsChanged,
    PrintSetupChanged,
    RandomChanged,
    TabsChanged,
)
from .functions.help import FunctionHelp, function_catalog, get_function, search_functions, translatable_texts
from .model import (
    MAX_OBJECTS_PER_SHEET,
    MIN_OBJECT_SIZE,
    OBJECT_KINDS,
    CellAnchor,
    Content,
    Sheet,
    SheetObject,
    Tab,
    WorkbookModel,
    content_of,
)
from .name_commands import DefineName, RemoveName, RenameName, RestoreNames
from .names import PURPOSES, NamedRange, Names
from .numformats import NumberFormat, NumberFormatBook
from .outcomes import AltInput, OutcomeRow, OutcomeTable, Swing
from .pivot import Aggregation, PivotDefinition, PivotError, PivotFilter, PivotLabels, ValueField
from .pivot_commands import SetPivot, create_pivot, delete_pivot, pivot_to_sql, update_pivot
from .pivot_render import PivotResult, PivotRole, compute_pivot
from .pivots import PivotEntry, Pivots
from .printing import DEFAULT_SHEET_PRINT, MAX_PERCENT, MIN_PERCENT, PrintSetupError, SheetPrintSetup
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
from .trace import Trace

__all__ = [
    "Aggregation",
    "PivotDefinition",
    "PivotEntry",
    "PivotError",
    "PivotFilter",
    "PivotLabels",
    "PivotResult",
    "PivotRole",
    "Pivots",
    "PivotsChanged",
    "ValueField",
    "compute_pivot",
    "create_pivot",
    "delete_pivot",
    "pivot_to_sql",
    "update_pivot",
    "DEFAULT_SHEET_PRINT",
    "MAX_PERCENT",
    "MIN_PERCENT",
    "PrintSetupChanged",
    "PrintSetupError",
    "SetPrintPage",
    "SetSheetPrint",
    "SheetPrintSetup",
    "NumberFormat",
    "NumberFormatBook",
    "Trace",
    "Swing",
    "OutcomeTable",
    "OutcomeRow",
    "AltInput",
    "__version__",
    "AddObject",
    "AddSheet",
    "AddSlide",
    "ApplyCalculated",
    "builtin_styles",
    "BUILTIN_STYLES",
    "CELL_SLOTS",
    "CellAnchor",
    "CellRef",
    "CellRegion",
    "CellStyles",
    "CellStylesChanged",
    "CHART_KINDS",
    "ChartError",
    "ChartSpec",
    "column_name",
    "Content",
    "content_of",
    "DEFAULT_CELL_STYLE",
    "DEFAULT_STYLE",
    "DefineName",
    "DescribeObject",
    "DeleteCols",
    "DeleteRows",
    "DiagramDefinition",
    "FunctionHelp",
    "InsertCols",
    "InsertRows",
    "layer_of",
    "LAYERS",
    "MAX_OBJECTS_PER_SHEET",
    "MAX_STYLE_RANGES",
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
    "RandomChanged",
    "RemoveName",
    "RenameName",
    "RestoreNames",
    "RemoveObject",
    "RemoveSheet",
    "RemoveSlide",
    "Resample",
    "ResizeLines",
    "ResizeObject",
    "RotateObject",
    "Run",
    "SetCells",
    "SetPivot",
    "SetCellStyle",
    "SetRandomSeed",
    "SetParagraphStyle",
    "SetSnap",
    "SetText",
    "Sheet",
    "SheetId",
    "SheetObject",
    "Structure",
    "Tab",
    "TabsChanged",
    "VisualObject",
    "WorkbookModel",
    "function_catalog",
    "get_function",
    "search_functions",
    "translatable_texts",
]
