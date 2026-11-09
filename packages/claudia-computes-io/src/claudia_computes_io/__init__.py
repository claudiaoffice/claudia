"""claudia-computes-io: xlsx import/export for the spreadsheet app, outside the kernel (E6.9, D147, D204).

This is not the ODF-first import/export story of E6.9 (D5, D70): a minimal base export (``workbook_to_xlsx``), a
real import and edit-and-reexport round trip (``xlsx_to_workbook``, ``apply_edits_to_xlsx``, D204, mirroring D177's
docx and D179's pptx), and one additive extension openpyxl itself cannot write, pivot tables (``add_pivot_table``),
built against openpyxl's own element/part layer rather than a fork of it (D147). odfdo is not a dependency yet:
nothing here is ODF, and D70 wants ods before xlsx when that story is built.

xlsx   workbook_to_xlsx, xlsx_to_workbook, apply_edits_to_xlsx, UnsupportedEdit, add_pivot_table
"""

from .xlsx import UnsupportedEdit, add_pivot_table, apply_edits_to_xlsx, workbook_to_xlsx, xlsx_to_workbook

__all__ = [
    "UnsupportedEdit",
    "add_pivot_table",
    "apply_edits_to_xlsx",
    "workbook_to_xlsx",
    "xlsx_to_workbook",
]
