"""A few functions about cells and links: NA, ADDRESS, LOOKUP, HYPERLINK."""

from __future__ import annotations

from ...refs import column_name
from ...values import NA, VALUE
from ..base import Example, FunctionError, UserFunction
from ..range import Range
from .catalog import builtin


@builtin
class NA_(UserFunction):
    name = "NA"
    description = "The error #N/A (not available): a way to say a value is missing, which charts leave out."
    examples = (Example("=ISNA(NA())", True),)

    def call(self):
        raise FunctionError(NA, "NA() says this value is not available")


@builtin
class ADDRESS(UserFunction):
    description = (
        "The address of a cell as text, from its row and column number. The third argument is 1 (default) for $A$1, 2 "
        "for A$1, 3 for $A1, 4 for A1; the fourth FALSE for R1C1 style; the fifth names a sheet."
    )
    examples = (
        Example("=ADDRESS(2,3)", "$C$2"),
        Example("=ADDRESS(2,3,4)", "C2"),
        Example("=ADDRESS(2,3,1,FALSE)", "R2C3"),
        Example('=ADDRESS(1,1,1,TRUE,"Sheet 2")', "'Sheet 2'!$A$1"),
    )

    def call(self, row_num: int, column_num: int, abs_num: int = 1, a1: bool = True, sheet_text: str | None = None):
        if not 1 <= row_num <= 1_048_576 or not 1 <= column_num <= 16_384 or abs_num not in (1, 2, 3, 4):
            raise FunctionError(VALUE, "row 1 to 1048576, column 1 to 16384 and absolute 1 to 4")
        row_abs, col_abs = abs_num in (1, 2), abs_num in (1, 3)
        if a1:
            text = f"{'$' if col_abs else ''}{column_name(column_num - 1)}{'$' if row_abs else ''}{row_num}"
        else:
            text = f"R{row_num if row_abs else f'[{row_num}]'}C{column_num if col_abs else f'[{column_num}]'}"
        if sheet_text is None:
            return text
        quoted = (
            sheet_text
            if sheet_text.replace("_", "").isalnum() and not sheet_text[0].isdigit()
            else "'" + sheet_text.replace("'", "''") + "'"
        )
        return f"{quoted}!{text}"


def _compare(cell: object, wanted: object) -> int | None:
    """-1, 0 or 1 for a cell against the value looked up; ``None`` if they are not of one kind (they never match)."""
    if isinstance(wanted, bool) or isinstance(cell, bool):
        return None if not (isinstance(wanted, bool) and isinstance(cell, bool)) else (cell > wanted) - (cell < wanted)
    if isinstance(wanted, (int, float)) and isinstance(cell, (int, float)):
        return (cell > wanted) - (cell < wanted)
    if isinstance(wanted, str) and isinstance(cell, str):
        a, b = cell.casefold(), wanted.casefold()
        return (a > b) - (a < b)
    return None


@builtin
class LOOKUP(UserFunction):
    description = (
        "Finds the last value in an ascending list that is not above the value looked up, and gives the value at the "
        "same place in the result list (or, with one table, in its last column or row)."
    )
    examples = (
        Example("=LOOKUP(2.5,A1:A3,B1:B3)", "b", {"A1": 1, "A2": 2, "A3": 3, "B1": "a", "B2": "b", "B3": "c"}),
        Example("=LOOKUP(9,A1:A3,B1:B3)", "c", {"A1": 1, "A2": 2, "A3": 3, "B1": "a", "B2": "b", "B3": "c"}),
    )

    def call(self, lookup_value: object, lookup_vector: Range, result_vector: Range | None = None):
        if result_vector is None:
            across = lookup_vector.n_cols > lookup_vector.n_rows
            keys = lookup_vector.row(0).vector() if across else lookup_vector.column(0).vector()
            results = (
                lookup_vector.row(lookup_vector.n_rows - 1).vector()
                if across
                else lookup_vector.column(lookup_vector.n_cols - 1).vector()
            )
        else:
            if not lookup_vector.is_vector() or not result_vector.is_vector():
                raise FunctionError(VALUE, "the lists must each be a single row or column")
            keys, results = lookup_vector.vector(), result_vector.vector()
        if isinstance(lookup_value, Range):
            lookup_value = lookup_value.at(0, 0)
        found = None
        for index, key in enumerate(keys):
            order = _compare(key, lookup_value)
            if order is not None and order <= 0:
                found = index
        if found is None or found >= len(results):
            raise FunctionError(NA, "the value is below every value in the list")
        return results[found]


@builtin
class HYPERLINK(UserFunction):
    description = (
        "A link: gives the friendly text if there is one, otherwise the address. The cell shows the text; claudia does "
        "not follow the link from a formula."
    )
    examples = (
        Example('=HYPERLINK("https://example.org","Example")', "Example"),
        Example('=HYPERLINK("https://example.org")', "https://example.org"),
    )

    def call(self, link_location: str, friendly_name: object = None):
        return link_location if friendly_name is None else friendly_name
