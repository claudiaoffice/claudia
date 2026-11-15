"""Pivot tables in a workbook (E6.30 step 2, D620, D623): a definition kept by name, a ``PIVOT("name")`` formula in the
cell where the pivot starts, and the pivot's name for the cells it fills. Creating, changing and deleting one are each
a single step of the history."""

from __future__ import annotations

import pytest
from conftest import S1, reopen
from names_helpers import at, code, define, fill, shown

from claudia_computes import (
    Aggregation,
    DefineName,
    InsertRows,
    NamedRange,
    PivotDefinition,
    PivotEntry,
    PivotError,
    PivotLabels,
    PivotRole,
    RemoveName,
    RenameName,
    SetCells,
    SetPivot,
    Structure,
    ValueField,
    create_pivot,
    delete_pivot,
    pivot_to_sql,
    update_pivot,
)
from claudia_computes.values import ErrorValue

SALES = {
    "A1": "Region",
    "B1": "Quarter",
    "C1": "Amount",
    "A2": "North",
    "B2": "Q1",
    "C2": 900,
    "A3": "North",
    "B3": "Q2",
    "C3": 1000,
    "A4": "South",
    "B4": "Q1",
    "C4": 1500,
    "A5": "South",
    "B5": "Q2",
    "C5": 1580,
    "A6": "East",
    "B6": "Q1",
    "C6": 1000,
}
ANCHOR = (S1, *at("F1"))


def by_region_and_quarter(**changes) -> PivotDefinition:
    fields = {"source": "Sales", "rows": ("Region",), "columns": ("Quarter",), "values": (ValueField("Amount"),)}
    return PivotDefinition(**{**fields, **changes})


@pytest.fixture
def sales(doc):
    fill(doc, SALES)
    define(doc, "Sales", "A1:C6", header=True, grows=True)
    return doc


def make(doc, name="SalesPivot", definition=None, labels=None, anchor=ANCHOR):
    return doc.execute(
        create_pivot(doc.model, name, anchor, definition or by_region_and_quarter(), labels), author="ana"
    )


def grid(doc, first="F1", last="J6"):
    (r0, c0), (r1, c1) = at(first), at(last)
    return [[doc.model.value(S1, r, c) for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]


# ------------------------------------------------------------------------------------ making one
def test_a_pivot_fills_the_cells_from_its_anchor(sales):
    make(sales)
    assert grid(sales, "F1", "I6") == [
        ["Sum of Amount", "Quarter", None, None],
        ["Region", "Q1", "Q2", "Total"],
        ["East", 1000, None, 1000],
        ["North", 900, 1000, 1900],
        ["South", 1500, 1580, 3080],
        ["Total", 3400, 2580, 5980],
    ]


def test_the_anchor_cell_holds_a_formula_naming_the_pivot_and_the_other_cells_are_not_stored(sales):
    make(sales)
    sheet = sales.model.sheet(S1)
    assert sheet.cells[at("F1")] == {"t": "formula", "v": '=PIVOT("SalesPivot")'}
    assert at("G3") not in sheet.cells
    assert sheet.spilled[at("G3")] == ANCHOR


def test_the_pivots_name_is_a_result_that_other_formulas_and_queries_can_use(sales):
    make(sales, definition=by_region_and_quarter(columns=()))
    named = sales.model.names.get((None, "salespivot"))
    assert named is not None
    assert named.is_result
    assert named.anchor == ANCHOR
    fill(sales, {"L1": '=SQL("SELECT Region, ""Sum of Amount"" FROM SalesPivot WHERE Region = \'North\'")'})
    assert shown(sales, "L2") == "North"
    assert shown(sales, "M2") == 1900


def test_making_a_pivot_is_one_step_and_undo_takes_all_of_it_away(sales):
    before = sales.model.serialize()
    make(sales)
    sales.undo("ana")
    assert sales.model.serialize() == before
    assert sales.model.pivots.get("SalesPivot") is None
    assert shown(sales, "F1") is None


def test_it_keeps_the_words_the_pivot_was_made_with(sales):
    labels = PivotLabels(total="Gesamt", sum_of="Summe von {field}", blank="(leer)")
    make(sales, labels=labels)
    assert shown(sales, "F1") == "Summe von Amount"
    assert shown(sales, "I2") == "Gesamt"
    assert sales.model.pivots.get("SalesPivot").labels == labels


def test_the_name_must_be_free_and_a_name(sales):
    make(sales)
    with pytest.raises(ValueError, match="exists|already"):
        make(sales, anchor=(S1, *at("F20")))
    with pytest.raises(ValueError, match="name"):
        make(sales, name="not a name", anchor=(S1, *at("F20")))
    with pytest.raises(ValueError, match="name"):
        make(sales, name="Sales", anchor=(S1, *at("F20")))  # (a table's)


def test_a_pivot_that_does_not_fit_shows_the_blocking_cell_like_any_result(sales):
    fill(sales, {"G2": "in the way"})
    make(sales)
    assert code(sales, "F1") == "#SPILL!"


# ------------------------------------------------------------------------------------ it is live
def test_a_changed_source_value_changes_the_pivot(sales):
    make(sales)
    fill(sales, {"C2": 100})
    assert shown(sales, "G4") == 100
    assert shown(sales, "I6") == 5180


def test_a_row_typed_below_a_growing_table_is_in_the_pivot(sales):
    make(sales)
    fill(sales, {"A7": "West", "B7": "Q2", "C7": 400})
    assert shown(sales, "F6") == "West"
    assert shown(sales, "H6") == 400


def test_a_new_member_makes_a_new_column(sales):
    make(sales)
    fill(sales, {"A2": "North", "B2": "Q4", "C2": 5})
    assert [shown(sales, a) for a in ("G2", "H2", "I2", "J2")] == ["Q1", "Q2", "Q4", "Total"]


def test_the_pivot_follows_a_pivot_it_reads(sales):
    make(sales, definition=by_region_and_quarter(columns=()))
    make(
        sales,
        name="Counts",
        definition=PivotDefinition("SalesPivot", values=(ValueField("Sum of Amount", Aggregation.COUNT),)),
        anchor=(S1, *at("L1")),
    )
    assert shown(sales, "M2") == 4  # (four regions' rows, the total row among them: it is a table of cells)
    fill(sales, {"A7": "West", "B7": "Q1", "C7": 1})
    assert shown(sales, "M2") == 5


# ------------------------------------------------------------------------------------ errors
def test_a_field_the_source_lacks_is_an_sql_error_that_says_which(sales):
    make(sales, definition=by_region_and_quarter(rows=("Country",)))
    value = shown(sales, "F1")
    assert isinstance(value, ErrorValue)
    assert value.code == "#SQL!"
    assert "Country" in value.detail


def test_a_source_that_is_no_name_is_an_error_until_there_is_one(sales):
    make(sales, definition=by_region_and_quarter(source="Orders"))
    assert code(sales, "F1") == "#SQL!"
    define(sales, "Orders", "A1:C6", header=True)
    assert shown(sales, "F1") == "Sum of Amount"


def test_a_formula_naming_no_pivot_is_a_name_error(sales):
    fill(sales, {"F1": '=PIVOT("Nothing")'})
    assert code(sales, "F1") == "#NAME?"


# ------------------------------------------------------------------------------------ changing and deleting
def test_changing_the_definition_changes_the_cells_and_undo_brings_the_old_ones_back(sales):
    make(sales)
    before = grid(sales)
    sales.execute(update_pivot(sales.model, "SalesPivot", by_region_and_quarter(columns=())), author="ana")
    assert grid(sales, "F1", "G5") == [
        ["Region", "Sum of Amount"],
        ["East", 1000],
        ["North", 1900],
        ["South", 3080],
        ["Total", 5980],
    ]
    assert shown(sales, "H2") is None  # (the cells the first layout had to the right are empty again)
    sales.undo("ana")
    assert grid(sales) == before


def test_the_new_labels_can_be_given_with_a_new_definition(sales):
    make(sales)
    labels = PivotLabels(total="Summe")
    sales.execute(update_pivot(sales.model, "SalesPivot", by_region_and_quarter(), labels), author="ana")
    assert shown(sales, "I2") == "Summe"


def test_deleting_a_pivot_empties_its_cells_and_takes_its_name_and_definition(sales):
    make(sales)
    sales.execute(delete_pivot(sales.model, "SalesPivot"), author="ana")
    assert shown(sales, "F1") is None
    assert shown(sales, "H4") is None
    assert sales.model.pivots.get("SalesPivot") is None
    assert sales.model.names.get((None, "salespivot")) is None


def test_undoing_a_delete_brings_back_the_cells_the_name_and_the_definition(sales):
    make(sales)
    before = sales.model.serialize()
    sales.execute(delete_pivot(sales.model, "SalesPivot"), author="ana")
    sales.undo("ana")
    assert sales.model.serialize() == before
    assert shown(sales, "H4") == 1000


def test_changing_or_deleting_what_is_not_a_pivot_is_refused(sales):
    with pytest.raises(ValueError, match="no pivot"):
        update_pivot(sales.model, "Sales", by_region_and_quarter())
    with pytest.raises(ValueError, match="no pivot"):
        delete_pivot(sales.model, "Sales")


def test_the_name_of_a_pivot_is_not_removed_or_renamed_on_its_own(sales):
    make(sales)
    with pytest.raises(ValueError, match="pivot"):
        sales.execute(RemoveName(None, "SalesPivot"), author="ana")
    with pytest.raises(ValueError, match="pivot"):
        sales.execute(RenameName(None, "SalesPivot", "Other"), author="ana")


def test_renaming_the_table_a_pivot_reads_keeps_the_pivot_reading_it_and_undo_goes_back(sales):
    make(sales)
    before = grid(sales)
    sales.execute(RenameName(None, "Sales", "Orders"), author="ana")
    assert sales.model.pivots.get("SalesPivot").definition.source == "Orders"
    assert grid(sales) == before
    sales.undo("ana")
    assert sales.model.pivots.get("SalesPivot").definition.source == "Sales"
    assert grid(sales) == before


def test_the_cells_of_a_pivot_are_not_to_be_written(sales):
    make(sales)
    with pytest.raises(ValueError, match="formula in F1"):
        sales.execute(SetCells(S1, ((*at("G3"), {"t": "number", "v": 1}),)), author="ana")


def test_clearing_the_anchor_cell_empties_the_pivot_and_keeps_its_definition(sales):
    make(sales)
    sales.execute(SetCells(S1, ((*at("F1"), None),)), author="ana")
    assert shown(sales, "H4") is None
    assert sales.model.pivots.get("SalesPivot") is not None
    sales.undo("ana")
    assert shown(sales, "H4") == 1000


# ------------------------------------------------------------------------------------ the rest of the workbook
def test_inserting_rows_above_moves_the_pivot_and_it_still_computes(sales):
    make(sales)
    sales.execute(Structure(InsertRows(S1, 0, 2)), author="ana")
    assert shown(sales, "F3") == "Sum of Amount"
    assert sales.model.names.get((None, "salespivot")).anchor == (S1, 2, 5)
    fill(sales, {"C4": 100})  # (the first data row, now on row 4)
    assert shown(sales, "G6") == 100


def test_the_pivot_is_there_again_when_the_document_is_reopened(sales):
    make(sales)
    again = reopen(sales)
    assert grid(again) == grid(sales)
    assert again.model.pivots.get("SalesPivot") == sales.model.pivots.get("SalesPivot")


def test_a_snapshot_of_the_workbook_carries_the_pivot(sales):
    make(sales)
    restored = type(sales.model).restore(sales.model.serialize())
    assert restored.pivots.get("SalesPivot") == sales.model.pivots.get("SalesPivot")
    assert restored.value(S1, *at("H4")) == 1000


# ------------------------------------------------------------------------------------ what a client is given
def test_the_roles_of_the_cells_are_there_for_the_client(sales):
    make(sales)
    result = sales.model.pivots.result("SalesPivot")
    assert result.height == 6
    assert result.role_at(1, 0) is PivotRole.FIELD
    assert result.role_at(2, 1) is PivotRole.VALUE
    assert result.role_at(5, 3) is PivotRole.TOTAL
    assert "SUM(CASE" in result.sql


def test_there_is_no_result_for_a_pivot_that_failed(sales):
    make(sales, definition=by_region_and_quarter(rows=("Country",)))
    assert sales.model.pivots.result("SalesPivot") is None


def test_an_entry_is_plain_data_and_comes_back_from_it():
    entry = PivotEntry("SalesPivot", by_region_and_quarter(), PivotLabels(total="Gesamt"))
    assert PivotEntry.from_data(entry.to_data()) == entry
    with pytest.raises(PivotError):
        PivotEntry.from_data({"name": "x"})


def test_the_name_command_helpers_know_about_pivots(sales):
    # (a pivot is not a range: DefineName for its own name, but with a range, is a different name and is refused)
    make(sales)
    other = NamedRange("SalesPivot", None, sales.model.names.get((None, "sales")).range, header=True)
    with pytest.raises(ValueError, match="pivot"):
        sales.execute(DefineName(other), author="ana")


# ------------------------------------------------------------------------------------ formula, command and data
def test_a_pivot_without_a_value_field_shows_nothing_yet(sales):
    make(sales, definition=by_region_and_quarter(values=()))
    assert shown(sales, "F1") == ""
    assert sales.model.pivots.result("SalesPivot") is None


def test_inside_another_formula_a_pivot_gives_its_first_cell(sales):
    make(sales)
    fill(sales, {"L1": '=PIVOT("SalesPivot")&"!"'})
    assert shown(sales, "L1") == "Sum of Amount!"
    assert shown(sales, "L2") is None


def test_the_formula_wants_one_name_as_text(sales):
    fill(sales, {"F1": "=PIVOT()", "F2": "=PIVOT(1)", "F3": '=PIVOT("a", "b")'})
    assert [code(sales, a) for a in ("F1", "F2", "F3")] == ["#VALUE!"] * 3


def test_a_pivot_over_a_query_result_that_is_not_there_yet_is_made_when_it_is(sales):
    sales.execute(DefineName(NamedRange("Big", None, None, True, False, "result", (), (S1, *at("A9")))), author="ana")
    make(sales, definition=PivotDefinition("Big", ("Region",), (), (ValueField("Amount"),)))
    assert code(sales, "F1") == "#REF!"  # (the name has no result: its SQL() formula is not there)
    fill(sales, {"A9": '=SQL("SELECT Region, Amount FROM Sales WHERE Amount > 1000")'})
    assert shown(sales, "F1") == "Region"
    assert shown(sales, "F2") == "South"


def test_the_command_is_plain_data_and_says_what_it_does(sales):
    entry = PivotEntry("SalesPivot", by_region_and_quarter())
    command = SetPivot("SalesPivot", entry)
    assert (command.label, command.summary) == ("Pivot table", "pivot SalesPivot")
    assert SetPivot.from_data(command.to_data(), None) == command
    gone = SetPivot("SalesPivot", None)
    assert (gone.label, gone.summary) == ("Delete pivot table", "delete SalesPivot")
    assert SetPivot.from_data(gone.to_data(), None) == gone


def test_two_changes_to_one_pivot_do_not_both_survive_a_rebase():
    first = SetPivot("A", None)
    assert first.shifted_by(SetPivot("a", None)) is None
    assert first.shifted_by(SetPivot("B", None)) is first


def test_the_words_are_plain_data_too():
    labels = PivotLabels(total="Gesamt")
    assert PivotLabels.from_data(labels.to_data()) == labels
    assert PivotLabels.from_data({"total": "Σ"}).blank == "(blank)"
    with pytest.raises(PivotError, match="object"):
        PivotLabels.from_data("Total")
    with pytest.raises(PivotError, match="unknown key"):
        PivotLabels.from_data({"totl": "x"})
    with pytest.raises(PivotError, match="text"):
        PivotLabels.from_data({"total": 1})


def test_a_pivot_cannot_start_on_a_sheet_that_is_not_there(sales):
    with pytest.raises(ValueError, match="sheet"):
        create_pivot(sales.model, "Elsewhere", ("s9", 0, 0), by_region_and_quarter())


def test_the_registry_forgets_when_asked(sales):
    make(sales)
    sales.model.pivots.clear()
    assert len(sales.model.pivots) == 0
    assert sales.model.pivots.result("SalesPivot") is None


# ------------------------------------------------------------------------------------ on a new sheet, and as SQL
def test_a_pivot_can_be_made_on_a_new_sheet_in_the_same_step(sales):
    command = create_pivot(sales.model, "SalesPivot", ("s2", 2, 0), by_region_and_quarter(), new_sheet="Pivot")
    sales.execute(command, author="ana")
    assert sales.model.sheet_name_of("s2") == "Pivot"
    assert sales.model.value("s2", 2, 0) == "Sum of Amount"
    assert sales.model.value("s2", 7, 3) == 5980
    sales.undo("ana")
    assert "s2" not in sales.model.sheets


def test_a_new_sheet_needs_a_free_id_and_a_name(sales):
    with pytest.raises(ValueError, match="exists|already"):
        create_pivot(sales.model, "SalesPivot", (S1, 0, 5), by_region_and_quarter(), new_sheet="Pivot")
    with pytest.raises(ValueError, match="sheet"):
        create_pivot(sales.model, "SalesPivot", ("s2", 0, 5), by_region_and_quarter())


def test_a_pivot_is_turned_into_the_query_it_is_and_the_cells_stay_the_same(sales):
    make(sales, definition=by_region_and_quarter(columns=()))
    before = grid(sales, "F1", "G5")
    sales.execute(pivot_to_sql(sales.model, "SalesPivot"), author="ana")
    assert sales.model.pivots.get("SalesPivot") is None
    assert grid(sales, "F1", "G5") == before
    formula = sales.model.sheet(S1).cells[at("F1")]["v"]
    assert formula.startswith('=SQL("SELECT ') and "UNION ALL" in formula
    named = sales.model.names.get((None, "salespivot"))
    assert named is not None and named.is_result and named.anchor == ANCHOR
    fill(sales, {"C2": 100})  # (it is a query now: still live)
    assert shown(sales, "G3") == 1100


def test_a_pivot_with_a_column_field_loses_its_upper_header_rows_as_a_query(sales):
    make(sales)
    sales.execute(pivot_to_sql(sales.model, "SalesPivot"), author="ana")
    assert grid(sales, "F1", "I5") == [
        ["Region", "Q1", "Q2", "Total"],
        ["East", 1000, None, 1000],
        ["North", 900, 1000, 1900],
        ["South", 1500, 1580, 3080],
        ["Total", 3400, 2580, 5980],
    ]


def test_turning_a_pivot_into_sql_is_one_step_and_undo_brings_the_pivot_back(sales):
    make(sales)
    before = sales.model.serialize()
    sales.execute(pivot_to_sql(sales.model, "SalesPivot"), author="ana")
    sales.undo("ana")
    assert sales.model.serialize() == before


def test_a_pivot_that_gave_nothing_is_not_turned_into_sql(sales):
    make(sales, definition=by_region_and_quarter(rows=("Country",)))
    with pytest.raises(ValueError, match="nothing|no pivot|SQL"):
        pivot_to_sql(sales.model, "SalesPivot")
    with pytest.raises(ValueError, match="no pivot"):
        pivot_to_sql(sales.model, "Sales")
