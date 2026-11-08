"""claudia-computes: the spreadsheet app, here only the mini-port that proves claudia-core.

refs      CellRef / RangeRef / structural edits (from the demo)
model     WorkbookModel: sheets, typed cells, and the images/objects a document knows (E10.11)
commands  AddSheet, RemoveSheet, SetCells, Structure, ResizeLines, DefineImage, ForgetImage, AddObject, MoveObject,
RemoveObject
region    CellRegion: moves with structural edits; ObjectSet: a selection of floating objects (does not)
entry     parse_input: what typing into a cell means

An image is anchored to a cell (``row``, ``col``) with a fixed pixel size (``w``, ``h``): neither ever changes
because of a row/column insert, delete, or resize — only ``MoveObject`` (the person dragging it) moves it, and
there is no resize of an object yet. Decoding and the import record are ``claudia_core``'s (``ImageAsset``,
``ImageImport``, re-exported there), shared with creates and composes.

functions.help  function_catalog/search_functions/get_function: every cell function, library and core alike, as one
searchable list (E13.5's "Documentation" for computes).
"""

from . import commands  # noqa: F401  (registers the commands)
from .commands import (
    AddObject,
    AddSheet,
    DefineImage,
    ForgetImage,
    MoveObject,
    RemoveObject,
    RemoveSheet,
    ResizeLines,
    SetCells,
    Structure,
)
from .entry import parse_input
from .events import ImagesChanged, ObjectsChanged
from .functions.help import FunctionHelp, function_catalog, get_function, search_functions
from .model import OBJECT_KINDS, Content, Sheet, SheetObject, WorkbookModel, content_of
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
from .region import CellRegion, ObjectSet

__all__ = [
    "OBJECT_KINDS",
    "AddObject",
    "AddSheet",
    "CellRef",
    "CellRegion",
    "Content",
    "DefineImage",
    "DeleteCols",
    "DeleteRows",
    "ForgetImage",
    "FunctionHelp",
    "ImagesChanged",
    "InsertCols",
    "InsertRows",
    "MoveObject",
    "ObjectSet",
    "ObjectsChanged",
    "RangeRef",
    "RefParseError",
    "RemoveObject",
    "RemoveSheet",
    "ResizeLines",
    "SetCells",
    "Sheet",
    "SheetId",
    "SheetObject",
    "Structure",
    "WorkbookModel",
    "column_name",
    "content_of",
    "function_catalog",
    "get_function",
    "parse_input",
    "parse_range_ref",
    "search_functions",
]
