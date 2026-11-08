"""claudia-computes: the spreadsheet app, here only the mini-port that proves claudia-core.

refs      CellRef / RangeRef / structural edits (from the demo)
model     WorkbookModel: sheets, typed cells, and the images/objects a document knows (E10.11)
commands  AddSheet, RemoveSheet, SetCells, Structure, ResizeLines, DefineImage, ForgetImage, AddObject, MoveObject,
RemoveObject, ApplyCalculated (a worker's result for a deferred heavy call, D37, D177)
region    CellRegion: moves with structural edits; ObjectSet: a selection of floating objects (does not)
entry     parse_input: what typing into a cell means

An image is anchored to a cell (``row``, ``col``) with a fixed pixel size (``w``, ``h``): neither ever changes
because of a row/column insert, delete, or resize — only ``MoveObject`` (the person dragging it) moves it, and
there is no resize of an object yet. Decoding and the import record are ``claudia_core``'s (``ImageAsset``,
``ImageImport``, re-exported there), shared with creates and composes.
"""

from . import commands  # noqa: F401  (registers the commands)
from .commands import (
    AddObject,
    AddSheet,
    ApplyCalculated,
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
    "ApplyCalculated",
    "CellRef",
    "CellRegion",
    "Content",
    "DefineImage",
    "DeleteCols",
    "DeleteRows",
    "ForgetImage",
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
    "parse_input",
    "parse_range_ref",
]
