"""claudia-computes: the spreadsheet app, here only the mini-port that proves claudia-core.

refs      CellRef / RangeRef / structural edits (from the demo)
model     WorkbookModel: sheets and typed cells
commands  AddSheet, RemoveSheet, SetCells, Structure, ResizeLines
region    CellRegion: moves with structural edits
entry     parse_input: what typing into a cell means
"""

from . import commands  # noqa: F401  (registers the commands)
from .commands import AddSheet, RemoveSheet, ResizeLines, SetCells, Structure
from .entry import parse_input
from .model import Content, Sheet, WorkbookModel, content_of
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

__all__ = [
    "AddSheet",
    "CellRef",
    "CellRegion",
    "Content",
    "DeleteCols",
    "DeleteRows",
    "InsertCols",
    "InsertRows",
    "RangeRef",
    "RefParseError",
    "RemoveSheet",
    "ResizeLines",
    "SetCells",
    "Sheet",
    "SheetId",
    "Structure",
    "WorkbookModel",
    "column_name",
    "content_of",
    "parse_input",
    "parse_range_ref",
]
