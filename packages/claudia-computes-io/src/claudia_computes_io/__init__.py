"""claudia-computes-io: xlsx and ods import/export for the spreadsheet app, outside the kernel (E6.9, D147, D220, D413).

xlsx (D5's other half): a minimal base export (``workbook_to_xlsx``), a real import and edit-and-reexport round trip
(``xlsx_to_workbook``, ``apply_edits_to_xlsx``, D220, mirroring D217's docx and D219's pptx), and one additive extension
openpyxl itself cannot write, pivot tables (``add_pivot_table``), built against openpyxl's own element/part layer
rather than a fork of it (D147).

ods (D70, D408, D413): the OpenDocument counterpart, with the promise of maximum preservation (D403): a new file
(``workbook_to_ods``), a file read as a model (``ods_to_workbook``) and an edited import written back by patching
only the cells that changed onto the original bytes (``apply_edits_to_ods``), each with its list of what could not
be kept (``ods_export_losses``, ``ods_import_losses``). Formulas are translated between the model's Excel language
and OpenFormula by :func:`to_openformula` and :func:`from_openformula`.

xlsx   workbook_to_xlsx, xlsx_to_workbook, apply_edits_to_xlsx, xlsx_export_losses, UnsupportedEdit, add_pivot_table
ods    workbook_to_ods, ods_to_workbook, apply_edits_to_ods, ods_export_losses, ods_import_losses
formulas   to_openformula, from_openformula, Untranslatable
"""

from ._version import __version__
from .ods import apply_edits_to_ods, ods_export_losses, ods_import_losses, ods_to_workbook, workbook_to_ods
from .openformula import Untranslatable, from_openformula, to_openformula
from .xlsx import (
    UnsupportedEdit,
    add_pivot_table,
    apply_edits_to_xlsx,
    workbook_to_xlsx,
    xlsx_export_losses,
    xlsx_to_workbook,
)

__all__ = [
    "__version__",
    "UnsupportedEdit",
    "Untranslatable",
    "add_pivot_table",
    "apply_edits_to_ods",
    "apply_edits_to_xlsx",
    "from_openformula",
    "ods_export_losses",
    "ods_import_losses",
    "ods_to_workbook",
    "to_openformula",
    "workbook_to_ods",
    "workbook_to_xlsx",
    "xlsx_export_losses",
    "xlsx_to_workbook",
]
