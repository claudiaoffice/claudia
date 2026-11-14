"""Information and reference functions: TYPE, N, T, ERROR.TYPE, NA, ISREF, ISFORMULA, FORMULATEXT, AREAS, SHEET,
SHEETS, CELL, INFO, ADDRESS, LOOKUP, HYPERLINK, LET, RANDARRAY, and subtotals that skip each other."""

from __future__ import annotations

from claudia_computes.functions.builtin import ScratchSheet
from claudia_computes.refs import SheetId
from excel_helpers import array, cases, check, code, column, raw, value

LIST = {**column("A1", [10, 20, 30]), "B1": "a", "B2": "b", "B3": "c", "C1": True}

TYPES = (
    ("=TYPE(5)", 1),
    ('=TYPE("x")', 2),
    ("=TYPE(TRUE)", 4),
    ("=TYPE(1/0)", 16),
    ("=TYPE(A1:A3)", 64),
    ("=TYPE(A1)", 1),
    ("=TYPE(B1)", 2),
    ("=TYPE(C1)", 4),
    ("=TYPE(D1)", 1),  # (empty)
    ("=TYPE(SEQUENCE(2))", 64),
    ("=N(5)", 5),
    ("=N(TRUE)", 1),
    ("=N(FALSE)", 0),
    ('=N("x")', 0),
    ("=N(A2)", 20),
    ("=N(B1)", 0),
    ("=N(D1)", 0),
    ("=N(1/0)", "#DIV/0!"),
    ('=T("x")', "x"),
    ("=T(5)", ""),
    ("=T(B2)", "b"),
    ("=T(A1)", ""),
    ("=T(TRUE)", ""),
    ("=ERROR.TYPE(1/0)", 2),
    ("=ERROR.TYPE(NA())", 7),
    ('=ERROR.TYPE(1+"x")', 3),
    ("=ERROR.TYPE(Nope)", 5),
    ("=ERROR.TYPE(SQRT(-1))", 6),
    ("=ERROR.TYPE(5)", "#N/A"),
    ("=NA()", "#N/A"),
    ("=ISNA(NA())", True),
    ("=IFERROR(NA(),7)", 7),
    ("=NA(1)", "#VALUE!"),
)


@cases(*[(f, e, LIST) for f, e in TYPES])
def test_what_a_value_is(formula, expected, cells):
    check(formula, expected, cells)


def test_a_reference_is_a_reference_and_a_value_is_not():
    for formula, expected in (
        ("=ISREF(A1)", True),
        ("=ISREF(A1:B2)", True),
        ("=ISREF(OFFSET(A1,1,0))", True),
        ('=ISREF(INDIRECT("A1"))', True),
        ("=ISREF(5)", False),
        ('=ISREF("A1")', False),
        ("=ISREF(A1+1)", False),
        ("=ISREF(Nope)", False),
        ("=ISREF(1/0)", False),
        ("=AREAS(A1:B2)", 1),
        ("=AREAS(A1)", 1),
    ):
        check(formula, expected, LIST)


class FormulaSheet(ScratchSheet):
    """A sheet that knows which cells hold formulas, as a document's sheets do (``sheet.cells``)."""

    def __init__(self, cells: dict, formulas: dict):
        super().__init__(cells)
        from claudia_computes.refs import parse_cell_ref

        self.cells = {}
        for address, text in formulas.items():
            ref = parse_cell_ref(address)
            self.cells[(ref.row, ref.col)] = {"t": "formula", "v": text}


def test_formulas_are_known_by_their_text():
    sheet = FormulaSheet({"A1": 5, "A2": 12}, {"A2": "=A1*2+2"})
    sheets = {SheetId("s1"): sheet}
    assert value("=ISFORMULA(A2)", sheets=sheets) is True
    assert value("=ISFORMULA(A1)", sheets=sheets) is False
    assert value("=ISFORMULA(B9)", sheets=sheets) is False
    assert value("=FORMULATEXT(A2)", sheets=sheets) == "=A1*2+2"
    assert code("=FORMULATEXT(A1)", sheets=sheets) == "#N/A"


def test_a_subtotal_leaves_out_the_subtotals_in_its_range():
    sheet = FormulaSheet(
        {"A1": 1, "A2": 2, "A3": 3, "A4": 4, "A5": 5, "A6": 15},
        {"A3": "=SUBTOTAL(9,A1:A2)", "A6": "=SUBTOTAL(9,A1:A5)"},
    )  # (A3 holds 3, a subtotal of A1:A2; A6 the total of all)
    sheets = {SheetId("s1"): sheet}
    assert value("=SUBTOTAL(9,A1:A6)", sheets=sheets) == 12  # 1+2+4+5, not 3 and not 15
    assert value("=SUBTOTAL(2,A1:A6)", sheets=sheets) == 4
    assert value("=SUM(A1:A6)", sheets=sheets) == 30  # (SUM counts them all)
    assert value("=AGGREGATE(9,0,A1:A6)", sheets=sheets) == 12
    assert value("=AGGREGATE(9,4,A1:A6)", sheets=sheets) == 12  # (the other subtotals are always left out)


def test_a_total_of_a_column_that_holds_a_formula_other_than_a_subtotal_counts_it():
    sheet = FormulaSheet({"A1": 1, "A2": 2}, {"A2": "=A1*2"})
    assert value("=SUBTOTAL(9,A1:A2)", sheets={SheetId("s1"): sheet}) == 3


def test_sheets_are_numbered_in_order():
    two = {SheetId("s1"): ScratchSheet({}), SheetId("s2"): ScratchSheet({"A1": 7})}
    assert value("=SHEET()", sheets=two) == 1
    assert value("=SHEETS()", sheets=two) == 2
    assert value("=SHEETS(A1:B2)", sheets=two) == 1
    assert value("=SHEET(A1)", sheets=two) == 1
    assert value('=SHEET("Sheet1")', sheets=two) == 1
    assert code('=SHEET("Nothing")', sheets=two) == "#N/A"
    assert code("=SHEET(SHEETS(), 1)", sheets=two) == "#VALUE!"


CELLS = (
    ('=CELL("address",B3)', "$B$3"),
    ('=CELL("address",AA10)', "$AA$10"),
    ('=CELL("address")', "$Z$99"),  # (the cell the formula is in)
    ('=CELL("row",B3)', 3),
    ('=CELL("col",B3)', 2),
    ('=CELL("contents",A2)', 20),
    ('=CELL("contents",B2)', "b"),
    ('=CELL("type",A1)', "v"),
    ('=CELL("type",B1)', "l"),
    ('=CELL("type",D1)', "b"),
    ('=CELL("sheet",A1)', 1),
    ('=CELL("format",A1)', "G"),
    ('=CELL("prefix",A1)', ""),
    ('=CELL("protect",A1)', 0),
    ('=CELL("ADDRESS",B3)', "$B$3"),  # (not case sensitive)
    ('=CELL("width",A1)', "#N/A"),
    ('=CELL("nonsense",A1)', "#N/A"),
    ("=CELL(5,A1)", "#VALUE!"),
    ('=INFO("recalc")', "Automatic"),
    ('=INFO("numfile")', 1),
    ('=INFO("origin")', "$A:$A$1"),
    ('=INFO("system")', "claudia"),
    ('=INFO("osversion")', "#N/A"),
    ("=INFO(5)", "#N/A"),
)


@cases(*[(f, e, LIST) for f, e in CELLS])
def test_information_about_cells_and_the_system(formula, expected, cells):
    check(formula, expected, cells)


ADDRESSES = (
    ("=ADDRESS(2,3)", "$C$2"),
    ("=ADDRESS(2,3,1)", "$C$2"),
    ("=ADDRESS(2,3,2)", "C$2"),
    ("=ADDRESS(2,3,3)", "$C2"),
    ("=ADDRESS(2,3,4)", "C2"),
    ("=ADDRESS(1,27)", "$AA$1"),
    ("=ADDRESS(1048576,16384)", "$XFD$1048576"),
    ("=ADDRESS(2,3,1,FALSE)", "R2C3"),
    ("=ADDRESS(2,3,4,FALSE)", "R[2]C[3]"),
    ("=ADDRESS(2,3,2,FALSE)", "R2C[3]"),
    ("=ADDRESS(2,3,3,FALSE)", "R[2]C3"),
    ('=ADDRESS(1,1,1,TRUE,"Sheet2")', "Sheet2!$A$1"),
    ('=ADDRESS(1,1,1,TRUE,"My sheet")', "'My sheet'!$A$1"),
    ('=ADDRESS(1,1,1,TRUE,"It\'s")', "'It''s'!$A$1"),
    ("=ADDRESS(0,1)", "#VALUE!"),
    ("=ADDRESS(1,0)", "#VALUE!"),
    ("=ADDRESS(1,16385)", "#VALUE!"),
    ("=ADDRESS(1,1,5)", "#VALUE!"),
)


@cases(*ADDRESSES)
def test_addresses(formula, expected, cells):
    check(formula, expected, cells)


LOOKUPS = (
    ("=LOOKUP(25,A1:A3,B1:B3)", "b"),
    ("=LOOKUP(2.5,A1:A3,B1:B3)", "#N/A"),  # below the first
    ("=LOOKUP(20,A1:A3,B1:B3)", "b"),
    ("=LOOKUP(9,A1:A3,B1:B3)", "#N/A"),  # below the first
    ("=LOOKUP(99,A1:A3,B1:B3)", "c"),  # above the last: the last
    ("=LOOKUP(25,A1:A3)", 20),  # one list: its own values
    ("=LOOKUP(25,A1:B3)", "b"),  # a table taller than wide: the last column
    ('=LOOKUP("b",B1:B3,A1:A3)', 20),
    ('=LOOKUP("B",B1:B3,A1:A3)', 20),  # (not case sensitive)
    ('=LOOKUP("bb",B1:B3,A1:A3)', 20),
    ('=LOOKUP("a",A1:A3,B1:B3)', "#N/A"),  # (text against numbers: no match)
    ("=LOOKUP(2,A1:C1)", "#N/A"),
)


@cases(*[(f, e, LIST) for f, e in LOOKUPS])
def test_lookup(formula, expected, cells):
    check(formula, expected, cells)


def test_lookup_in_a_table_wider_than_tall_uses_the_first_row_and_last_row():
    cells = {"A1": 1, "B1": 5, "C1": 9, "A2": "x", "B2": "y", "C2": "z"}
    check("=LOOKUP(6,A1:C2)", "y", cells)
    check("=LOOKUP(100,A1:C2)", "z", cells)
    check("=LOOKUP(0,A1:C2)", "#N/A", cells)


def test_hyperlink_shows_its_text():
    check('=HYPERLINK("https://example.org","Example")', "Example")
    check('=HYPERLINK("https://example.org")', "https://example.org")
    check('=HYPERLINK("https://example.org",42)', 42)
    check('=HYPERLINK(A1,"x")', "x", {"A1": "https://example.org"})


LETS = (
    ("=LET(x,5,x*2)", 10),
    ("=LET(x,5,y,x+1,x*y)", 30),
    ("=LET(x,A1,x+1)", 11),
    ("=LET(rng,A1:A3,SUM(rng))", 60),
    ("=LET(rng,A1:A3,MAX(rng)-MIN(rng))", 20),
    ("=LET(x,2,LET(x,3,x)+x)", 5),  # (the inner x is its own)
    ('=LET(name,"claudia",LEN(name))', 7),
    ("=LET(x,1/0,5)", "#DIV/0!"),
    ("=LET(x,5)", "#VALUE!"),
    ("=LET(x,5,6,7)", "#VALUE!"),
    ("=LET(5,5,5)", "#VALUE!"),
    ("=LET(x,5,x)+LET(x,7,x)", 12),
    ("=LET(a,2,b,a*a,c,b*a,c)", 8),
    ("=LET(x,3,IF(x>2,x*10,0))", 30),
)


@cases(*[(f, e, LIST) for f, e in LETS])
def test_let(formula, expected, cells):
    check(formula, expected, cells)


def test_a_let_name_does_not_leak():
    check("=LET(x,5,x)", 5)
    assert code("=x") == "#NAME?"
    check("=LET(x,5,x)+LET(y,1,y)", 6)


def test_random_arrays_have_the_size_and_the_limits_asked_for():
    result = raw("=RANDARRAY(3,4)")
    assert (result.height, result.width) == (3, 4)
    assert all(0 <= v < 1 for row in result.rows for v in row)
    assert len({v for row in result.rows for v in row}) == 12  # (all different)
    whole = raw("=RANDARRAY(5,5,10,12,TRUE)")
    assert {v for row in whole.rows for v in row} <= {10, 11, 12}
    assert all(isinstance(v, int) for row in whole.rows for v in row)
    ranged = raw("=RANDARRAY(4,1,-5,5)")
    assert all(-5 <= row[0] < 5 for row in ranged.rows)
    assert 0 <= value("=RANDARRAY()") < 1
    assert (raw("=RANDARRAY(2)").height, raw("=RANDARRAY(2)").width) == (2, 1)
    assert value("=SUM(RANDARRAY(3,3,1,1,TRUE))") == 9
    for formula in ("=RANDARRAY(0)", "=RANDARRAY(1,0)", "=RANDARRAY(1,1,5,1)", "=RANDARRAY(1,1,1.2,1.8,TRUE)"):
        assert code(formula) == "#VALUE!"
