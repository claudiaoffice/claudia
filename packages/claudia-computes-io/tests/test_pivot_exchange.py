"""What a file says of a pivot, the same for ods and xlsx (D625, D628): the pivots of a model as FilePivots, the cells
they fill as plain cells, and the pivots of a file taken in only when the engine makes the file's cells."""

from __future__ import annotations

from dataclasses import replace

from claudia_computes_io.pivot_exchange import FilePivot, adopt_pivots, sheet_cells, source_table, written_pivots
from pivot_helpers import a_headerless_pivot_model, a_pivot_model, by_region_and_quarter, grid_of

from claudia_computes import (
    Aggregation,
    CellRef,
    NamedRange,
    PivotFilter,
    PivotLabels,
    RangeRef,
    Sheet,
    ValueField,
    WorkbookModel,
)

DATA, PIVOT = "s1", "s2"


def box(sheet: str, first: tuple[int, int], last: tuple[int, int]) -> RangeRef:
    return RangeRef.between(CellRef(*first, sheet), CellRef(*last, sheet))


def flat(model: WorkbookModel, *, shift: int = 0, filter_row: bool = False) -> WorkbookModel:
    """What a file gives: the model with every pivot's cells as plain values, no pivot and no result name. ``shift``
    rows are put above the pivot's cells (a file's filter buttons, with ``filter_row`` a word in the first)."""
    out = WorkbookModel()
    for sheet in model.sheets.values():
        copy = Sheet(sheet.id, sheet.name)
        for (row, col), (content, _) in sheet_cells(model, sheet).items():
            copy.cells[(row + (shift if sheet.id == PIVOT else 0), col)] = content
        if filter_row and sheet.id == PIVOT:
            copy.cells[(0, 0)] = {"t": "text", "v": "Filter"}
        out.sheets[sheet.id] = copy
        out.open_container(str(sheet.id))
    for named in model.names:
        if not named.is_result:
            out.names.put(named)
    out._calculate_loaded()
    return out


def as_read(model: WorkbookModel, pivot: FilePivot, **changes) -> FilePivot:
    """``pivot`` as a format module hands it over: no grid, the words of no language."""
    return replace(pivot, result=None, labels=PivotLabels(), **changes)


def kinds(losses) -> dict[str, int]:
    return {f"{loss.kind}:{loss.detail}": loss.count for loss in losses}


# -- writing ---------------------------------------------------------------------------------------------------------
def test_a_pivot_is_what_a_file_says_of_it():
    written = written_pivots(a_pivot_model(by_region_and_quarter(rows=("region",))))
    [pivot] = written.pivots
    assert pivot.name == "P"
    assert pivot.source == box(DATA, (0, 0), (5, 3))
    assert pivot.target == box(PIVOT, (0, 0), (5, 3))
    assert (pivot.rows, pivot.columns) == (("Region",), ("Quarter",))  # (as the source writes the field)
    assert pivot.values == (ValueField("Amount"),)
    assert (pivot.total_row, pivot.total_column) == (True, True)
    assert pivot.result is not None
    assert written.losses == ()


def test_the_words_of_a_pivot_go_with_it():
    labels = PivotLabels(total="Gesamt", sum_of="Summe von {field}")
    [pivot] = written_pivots(a_pivot_model(labels=labels)).pivots
    assert pivot.labels == labels


def test_a_pivot_over_a_range_with_no_header_is_not_written_as_a_pivot():
    written = written_pivots(a_headerless_pivot_model())
    assert written.pivots == ()
    assert kinds(written.losses) == {"pivot-table:source": 1}


def test_a_pivot_that_has_no_value_field_yet_fills_nothing_and_is_said():
    written = written_pivots(a_pivot_model(by_region_and_quarter(values=())))
    assert written.pivots == ()
    assert kinds(written.losses) == {"pivot-table:empty": 1}


def test_the_cells_a_pivot_fills_are_values_and_its_formula_is_not_written():
    model = a_pivot_model()
    cells = sheet_cells(model, model.sheet(PIVOT))
    assert cells[(0, 0)] == ({"t": "text", "v": "Sum of Amount"}, "Sum of Amount")
    assert cells[(2, 1)] == ({"t": "int", "v": 60}, 60)  # East, Q1
    assert (2, 2) not in cells  # East has no Q2: an empty cell stays empty
    assert cells[(5, 3)] == ({"t": "int", "v": 510}, 510)  # the total of all
    assert all(content["t"] != "formula" for content, _ in cells.values())


def test_the_cells_of_other_sheets_are_as_they_are():
    model = a_pivot_model()
    data = model.sheet(DATA)
    assert sheet_cells(model, data) == {
        position: (content, data.grid.get(position)) for position, content in data.cells.items()
    }


def test_the_source_of_a_pivot_is_read_as_the_engine_reads_a_table():
    model = a_pivot_model()
    header, rows = source_table(model, box(DATA, (0, 0), (5, 3)))
    assert header == ["Region", "Quarter", "Amount", "Units"]
    assert rows[0] == ("North", "Q1", 100, 1)
    assert len(rows) == 5


# -- reading ---------------------------------------------------------------------------------------------------------
def test_a_pivot_whose_cells_the_engine_makes_is_taken_in():
    model = a_pivot_model()
    [pivot] = written_pivots(model).pivots
    file = flat(model)
    done = adopt_pivots(file, [as_read(model, pivot)])
    assert (done.adopted, done.losses) == (1, ())
    entry = file.pivots.get("P")
    assert entry is not None
    assert entry.definition == by_region_and_quarter()  # (over the table that is exactly its source)
    assert file.sheet(PIVOT).cells == {(0, 0): {"t": "formula", "v": '=PIVOT("P")'}}
    named = file.names.get((None, "p"))
    assert named is not None
    assert named.anchor == (PIVOT, 0, 0)
    assert grid_of(file, PIVOT, 6, 4) == grid_of(model, PIVOT, 6, 4)


def test_a_source_no_name_covers_gets_one_made_for_it():
    model = a_pivot_model()
    [pivot] = written_pivots(model).pivots
    file = flat(model)
    file.names.put(None, (None, "sales"))
    adopt_pivots(file, [as_read(model, pivot)])
    made = file.names.get((None, "p_source"))
    assert made == NamedRange("P_Source", None, box(DATA, (0, 0), (5, 3)), header=True)
    entry = file.pivots.get("P")
    assert entry is not None
    assert entry.definition.source == "P_Source"


def test_the_words_of_the_file_are_read_off_its_cells():
    labels = PivotLabels(total="Gesamtergebnis", sum_of="Summe - {field}", blank="(leer)")
    model = a_pivot_model(labels=labels)
    [pivot] = written_pivots(model).pivots
    file = flat(model)
    done = adopt_pivots(file, [as_read(model, pivot)])
    assert done.adopted == 1
    entry = file.pivots.get("P")
    assert entry is not None
    assert entry.labels.total == "Gesamtergebnis"
    assert entry.definition.values == (ValueField("Amount", Aggregation.SUM, "Summe - Amount"),)
    assert grid_of(file, PIVOT, 6, 4) == grid_of(model, PIVOT, 6, 4)


def test_a_file_that_puts_its_filter_buttons_above_the_cells_is_read_from_where_they_end():
    model = a_pivot_model()
    [pivot] = written_pivots(model).pivots
    file = flat(model, shift=2, filter_row=True)
    shifted = as_read(model, pivot, target=box(PIVOT, (0, 0), (7, 3)))
    assert adopt_pivots(file, [shifted]).adopted == 1
    assert file.sheet(PIVOT).cells[(0, 0)] == {"t": "text", "v": "Filter"}
    assert file.sheet(PIVOT).cells[(2, 0)] == {"t": "formula", "v": '=PIVOT("P")'}
    named = file.names.get((None, "p"))
    assert named is not None
    assert named.anchor == (PIVOT, 2, 0)


def test_a_header_that_says_row_labels_is_read_and_said():
    model = a_pivot_model()
    [pivot] = written_pivots(model).pivots
    file = flat(model)
    file.sheet(PIVOT).cells[(1, 0)] = {"t": "text", "v": "Row Labels"}
    file.sheet(PIVOT).cells[(0, 1)] = {"t": "text", "v": "Column Labels"}
    file._calculate_loaded()
    done = adopt_pivots(file, [as_read(model, pivot)])
    assert done.adopted == 1
    assert kinds(done.losses) == {"pivot-table:layout": 1}


def test_a_pivot_whose_numbers_are_not_the_engines_stays_cells():
    model = a_pivot_model()
    [pivot] = written_pivots(model).pivots
    file = flat(model)
    file.sheet(PIVOT).cells[(3, 1)] = {"t": "int", "v": 901}  # North, Q1 was 900... in the file
    file._calculate_loaded()
    before = dict(file.sheet(PIVOT).cells)
    done = adopt_pivots(file, [as_read(model, pivot)])
    assert (done.adopted, kinds(done.losses)) == (0, {"pivot-table:different": 1})
    assert file.sheet(PIVOT).cells == before
    assert file.pivots.get("P") is None
    assert file.names.get((None, "p")) is None


def test_a_pivot_with_more_fields_than_the_engine_has_stays_cells():
    model = a_pivot_model()
    [pivot] = written_pivots(model).pivots
    file = flat(model)
    two = as_read(model, pivot, rows=("Region", "Quarter"))
    assert kinds(adopt_pivots(file, [two]).losses) == {"pivot-table:fields": 1}


def test_a_pivot_with_no_value_to_add_up_stays_cells():
    model = a_pivot_model()
    [pivot] = written_pivots(model).pivots
    none = as_read(model, pivot, values=())
    assert kinds(adopt_pivots(flat(model), [none]).losses) == {"pivot-table:fields": 1}


def test_a_field_the_source_does_not_have_stays_cells():
    model = a_pivot_model()
    [pivot] = written_pivots(model).pivots
    wrong = as_read(model, pivot, rows=("Country",))
    assert kinds(adopt_pivots(flat(model), [wrong]).losses) == {"pivot-table:source": 1}


def test_a_name_a_file_gives_that_is_no_name_here_is_made_one():
    model = a_pivot_model()
    [pivot] = written_pivots(model).pivots
    file = flat(model)
    adopt_pivots(file, [as_read(model, pivot, name="Pivot Table 1")])
    assert file.pivots.get("Pivot_Table_1") is not None


def test_two_pivots_of_one_name_get_two_names():
    model = a_pivot_model()
    [pivot] = written_pivots(model).pivots
    file = flat(model)
    done = adopt_pivots(file, [as_read(model, pivot), as_read(model, pivot, target=box(PIVOT, (0, 0), (5, 3)))])
    assert done.adopted == 2
    assert file.pivots.get("P") is not None
    assert file.pivots.get("P_2") is not None


def test_two_pivots_over_one_source_share_the_name_made_for_it():
    model = a_pivot_model()
    [pivot] = written_pivots(model).pivots
    file = flat(model)
    file.names.put(None, (None, "sales"))
    done = adopt_pivots(file, [as_read(model, pivot), as_read(model, pivot)])
    assert done.adopted == 2
    assert sorted(named.name for named in file.names if named.range is not None) == ["P_Source"]


def test_a_pivot_with_a_filter_is_taken_in_with_its_filter():
    definition = by_region_and_quarter(
        rows=("Quarter",), columns=(), filters=(PivotFilter("Region", ("North", "East")),)
    )
    model = a_pivot_model(definition)
    [pivot] = written_pivots(model).pivots
    file = flat(model)
    assert adopt_pivots(file, [as_read(model, pivot)]).adopted == 1
    entry = file.pivots.get("P")
    assert entry is not None
    assert entry.definition.filters == (PivotFilter("Region", ("North", "East")),)
    assert grid_of(file, PIVOT, 4, 3) == grid_of(model, PIVOT, 4, 3)
