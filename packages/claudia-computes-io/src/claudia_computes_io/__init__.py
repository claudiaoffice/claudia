"""claudia-computes-io: xlsx export for the spreadsheet app, outside the kernel (E6.9, D135).

This is a first slice, not the ODF-first import/export story of E6.9 (D5, D70): a minimal base export
(``workbook_to_xlsx``) and one additive extension openpyxl itself cannot write, pivot tables (``add_pivot_table``),
built against openpyxl's own element/part layer rather than a fork of it (D135). odfdo is not a dependency yet:
nothing here is ODF, and D70 wants ods before xlsx when that story is built.

xlsx   workbook_to_xlsx, add_pivot_table
"""

from .xlsx import add_pivot_table, workbook_to_xlsx

__all__ = [
    "add_pivot_table",
    "workbook_to_xlsx",
]
