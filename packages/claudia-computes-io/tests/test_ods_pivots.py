"""Pivot tables in ods files (D625, D628): written as ``table:data-pilot-table`` with the cells they fill, read back as
live pivots when the engine makes the file's cells, and left alone in a kept file."""

from __future__ import annotations

import re
from dataclasses import replace

from claudia_computes_io import (
    apply_edits_to_ods,
    ods_export_losses,
    ods_import_losses,
    ods_to_workbook,
    ods_unwritten_changes,
    workbook_to_ods,
)
from pivot_helpers import a_headerless_pivot_model, a_pivot_model, by_region_and_quarter, grid_of
from test_ods import an_ods, content_of, kinds, num, row, table, text

from claudia_computes import (
    Aggregation,
    CellRef,
    DefineName,
    NamedRange,
    PivotFilter,
    PivotLabels,
    RangeRef,
    ValueField,
    create_pivot,
)
from claudia_core import Document, MemoryStore
from claudia_odf_io import LossLog, OdfError, problems

PILOT = "table:data-pilot-tables"


def pilots(data: bytes) -> list[str]:
    """The ``table:data-pilot-table`` elements of a file, as text."""
    return re.findall(r"<table:data-pilot-table .*?</table:data-pilot-table>", content_of(data), re.DOTALL)


# -- writing ---------------------------------------------------------------------------------------------------------
def test_a_pivot_is_written_after_the_names_with_its_source_target_and_fields():
    data = workbook_to_ods(a_pivot_model())
    [pilot] = pilots(data)
    assert 'table:name="P"' in pilot
    assert '<table:source-cell-range table:cell-range-address="Data.A1:.D6"/>' in pilot
    assert 'table:target-range-address="Pivot.A1:.D6"' in pilot
    assert 'table:source-field-name="Region" table:orientation="row"' in pilot
    assert 'table:source-field-name="Quarter" table:orientation="column"' in pilot
    assert 'table:source-field-name="Amount" table:orientation="data"' in pilot
    assert 'table:function="sum"' in pilot
    text = content_of(data)
    assert text.index("table:database-ranges") < text.index(PILOT) < text.index("</office:spreadsheet>")


def test_the_cells_of_a_pivot_are_written_as_cells_with_no_formula():
    model = ods_to_workbook(workbook_to_ods(a_pivot_model(by_region_and_quarter(columns=()))))
    assert model.pivots.get("P") is not None
    data = workbook_to_ods(a_pivot_model())
    assert "PIVOT(" not in content_of(data)
    assert "<text:p>Sum of Amount</text:p>" in content_of(data)
    assert not problems(data)


def test_totals_and_functions_are_written_as_they_are_asked():
    definition = by_region_and_quarter(
        total_row=False,
        total_column=True,
        values=(ValueField("Amount", Aggregation.AVERAGE), ValueField("Units", Aggregation.COUNT)),
    )
    [pilot] = pilots(workbook_to_ods(a_pivot_model(definition)))
    assert 'table:grand-total="column"' in pilot  # (the column of totals at the right, no row of them below)
    assert 'table:function="average"' in pilot
    assert 'table:function="count"' in pilot
    assert 'table:is-data-layout-field="true"' in pilot  # (two values: the field that says which is which)


def test_a_filter_is_a_page_field_with_the_members_it_keeps():
    definition = by_region_and_quarter(
        rows=("Quarter",), columns=(), filters=(PivotFilter("Region", ("North", "East")),)
    )
    [pilot] = pilots(workbook_to_ods(a_pivot_model(definition)))
    assert 'table:source-field-name="Region" table:orientation="page"' in pilot
    assert '<table:data-pilot-member table:name="North" table:display="true"/>' in pilot
    assert '<table:data-pilot-member table:name="South" table:display="false"/>' in pilot


def test_a_pivot_that_cannot_be_written_as_one_is_written_as_the_values_and_said():
    model = a_headerless_pivot_model()
    data = workbook_to_ods(model)
    assert pilots(data) == []
    assert "<text:p>Sum of C</text:p>" in content_of(data)
    assert kinds(ods_export_losses(model)) == {"pivot-table:source": 1}


def test_a_fresh_export_says_nothing_of_a_pivot_it_wrote():
    assert kinds(ods_export_losses(a_pivot_model())) == {}


# -- round trip ------------------------------------------------------------------------------------------------------
def test_a_pivot_comes_back_as_the_pivot_it_was():
    model = a_pivot_model()
    back = ods_to_workbook(workbook_to_ods(model))
    entry = back.pivots.get("P")
    assert entry == model.pivots.get("P")  # (over the table Sales, with the words it had)
    assert grid_of(back, "s2", 6, 4) == grid_of(model, "s2", 6, 4)
    assert back.sheet("s2").cells == {(0, 0): {"t": "formula", "v": '=PIVOT("P")'}}
    assert ods_import_losses(workbook_to_ods(model)) == ()


def test_the_choices_of_a_pivot_come_back():
    for definition in (
        by_region_and_quarter(total_row=False),
        by_region_and_quarter(total_column=False),
        by_region_and_quarter(columns=()),
        by_region_and_quarter(columns=(), rows=(), values=(ValueField("Amount", Aggregation.MAX),)),
        by_region_and_quarter(
            values=(ValueField("Amount", Aggregation.AVERAGE), ValueField("Units", Aggregation.COUNT))
        ),
        by_region_and_quarter(rows=("Quarter",), columns=(), filters=(PivotFilter("Region", ("North", "East")),)),
        by_region_and_quarter(values=(ValueField("Amount", Aggregation.SUM, "Revenue"),)),
    ):
        model = a_pivot_model(definition)
        back = ods_to_workbook(workbook_to_ods(model))
        entry = back.pivots.get("P")
        assert entry is not None, definition
        assert entry.definition == definition, definition
        rows = model.pivots.result("P").height
        cols = model.pivots.result("P").width
        assert grid_of(back, "s2", rows, cols) == grid_of(model, "s2", rows, cols), definition


def test_the_words_a_pivot_was_made_with_come_back_from_its_cells():
    labels = PivotLabels(total="Gesamt", sum_of="Summe von {field}")
    model = a_pivot_model(labels=labels)
    entry = ods_to_workbook(workbook_to_ods(model)).pivots.get("P")
    assert entry is not None
    assert entry.labels.total == "Gesamt"
    assert entry.definition.values == (ValueField("Amount", Aggregation.SUM, "Summe von Amount"),)


# -- reading the files of LibreOffice --------------------------------------------------------------------------------
DATA = table(
    "Data",
    row(text("Region"), text("Quarter"), text("Amount"), text("Units"))
    + row(text("North"), text("Q1"), num(100), num(1))
    + row(text("North"), text("Q2"), num(150), num(2))
    + row(text("South"), text("Q1"), num(80), num(3))
    + row(text("South"), text("Q2"), num(120), num(4))
    + row(text("East"), text("Q1"), num(60), num(5))
    + row(text("East"), text("Q2"), num(90), num(6)),
)


def libreoffice_cells(*, east: str = "60") -> str:
    """The cells LibreOffice writes for a pivot: two rows for the filter buttons, then the table, in its words."""
    return (
        row(text("Filter"))
        + row()
        + row(text("Sum - Amount"), text("Quarter"))
        + row(text("Region"), text("Q1"), text("Q2"), text("Total Result"))
        + row(text("East"), num(east), num(90), num(150))
        + row(text("North"), num(100), num(150), num(250))
        + row(text("South"), num(80), num(120), num(200))
        + row(text("Total Result"), num(240), num(360), num(600))
    )


def libreoffice_pilot(extra: str = "", source: str | None = None, fields: str | None = None) -> str:
    source = source or '<table:source-cell-range table:cell-range-address="Data.A1:Data.D7"/>'
    level = '<table:data-pilot-level calcext:repeat-item-labels="false"/>'
    fields = fields or "".join(
        f'<table:data-pilot-field table:source-field-name="{name}" table:orientation="{kind}" '
        f'table:used-hierarchy="-1" table:function="{function}">{level}</table:data-pilot-field>'
        for name, kind, function in (
            ("Region", "row", "auto"),
            ("Quarter", "column", "auto"),
            ("Amount", "data", "sum"),
        )
    )
    return (
        f'<table:data-pilot-tables><table:data-pilot-table table:name="PivotSales" table:application-data="" '
        f'table:target-range-address="Pivot.A1:Pivot.D8" table:buttons="Pivot.A1 Pivot.A4 Pivot.B3"{extra}>'
        f"{source}{fields}</table:data-pilot-table></table:data-pilot-tables>"
    )


def a_libreoffice_file(*, east: str = "60", pilot: str | None = None) -> bytes:
    return an_ods(DATA, table("Pivot", libreoffice_cells(east=east)), after=pilot or libreoffice_pilot())


def test_a_pivot_made_by_libreoffice_is_read_in_its_own_words():
    model = ods_to_workbook(a_libreoffice_file())
    entry = model.pivots.get("PivotSales")
    assert entry is not None
    assert entry.definition.rows == ("Region",)
    assert entry.definition.columns == ("Quarter",)
    assert entry.definition.values == (ValueField("Amount", Aggregation.SUM, "Sum - Amount"),)
    assert entry.labels.total == "Total Result"
    assert model.sheet("s2").cells[(0, 0)] == {"t": "text", "v": "Filter"}  # (the buttons are cells of the file)
    assert model.sheet("s2").cells[(2, 0)] == {"t": "formula", "v": '=PIVOT("PivotSales")'}
    assert model.value("s2", 7, 3) == 600
    assert ods_import_losses(a_libreoffice_file()) == ()


def test_a_pivot_of_libreoffice_whose_cells_are_not_the_engines_stays_cells():
    data = a_libreoffice_file(east="61")
    model = ods_to_workbook(data)
    assert model.pivots.get("PivotSales") is None
    assert model.value("s2", 4, 1) == 61
    assert kinds(ods_import_losses(data)) == {"pivot-table:different": 1}


def test_a_pivot_over_a_database_or_a_service_stays_cells_and_is_said():
    source = '<table:database-source-sql table:database-name="db" table:sql-statement="select 1"/>'
    data = a_libreoffice_file(pilot=libreoffice_pilot(source=source))
    assert ods_to_workbook(data).pivots.get("PivotSales") is None
    assert kinds(ods_import_losses(data)) == {"pivot-table:external-source": 1}


def test_what_the_engine_cannot_do_is_said_with_its_name():
    for child, detail in (
        ('<table:data-pilot-field-reference table:type="percent"/>', "show-as"),
        ('<table:data-pilot-groups table:source-field-name="Region"/>', "grouping"),
        ('<table:data-pilot-sort-info table:sort-mode="manual"/>', "manual-sort"),
    ):
        fields = (
            '<table:data-pilot-field table:source-field-name="Region" table:orientation="row">'
            f"<table:data-pilot-level>{child}</table:data-pilot-level></table:data-pilot-field>"
            '<table:data-pilot-field table:source-field-name="Quarter" table:orientation="column"/>'
            '<table:data-pilot-field table:source-field-name="Amount" table:orientation="data" table:function="sum"/>'
        )
        data = a_libreoffice_file(pilot=libreoffice_pilot(fields=fields))
        assert kinds(ods_import_losses(data)) == {f"pivot-table:{detail}": 1}, detail
        assert ods_to_workbook(data).pivots.get("PivotSales") is None


def test_a_function_the_engine_does_not_have_is_said():
    fields = (
        '<table:data-pilot-field table:source-field-name="Region" table:orientation="row"/>'
        '<table:data-pilot-field table:source-field-name="Amount" table:orientation="data" table:function="product"/>'
    )
    data = a_libreoffice_file(pilot=libreoffice_pilot(fields=fields))
    assert kinds(ods_import_losses(data)) == {"pivot-table:aggregation": 1}


def test_a_hidden_member_of_a_row_is_said():
    fields = (
        '<table:data-pilot-field table:source-field-name="Region" table:orientation="row"><table:data-pilot-level>'
        '<table:data-pilot-members><table:data-pilot-member table:name="East" table:display="false"/>'
        "</table:data-pilot-members></table:data-pilot-level></table:data-pilot-field>"
        '<table:data-pilot-field table:source-field-name="Amount" table:orientation="data" table:function="sum"/>'
    )
    data = a_libreoffice_file(pilot=libreoffice_pilot(fields=fields))
    assert kinds(ods_import_losses(data)) == {"pivot-table:hidden-items": 1}


# -- a kept file -----------------------------------------------------------------------------------------------------
def test_a_kept_file_keeps_its_pivot_when_nothing_changed():
    data = a_libreoffice_file()
    baseline, current = ods_to_workbook(data), ods_to_workbook(data)
    assert apply_edits_to_ods(data, baseline, current) == data
    assert ods_unwritten_changes(current, baseline) == ()


def test_a_pivot_changed_in_a_kept_file_is_said_not_written():
    data = a_libreoffice_file()
    baseline, current = ods_to_workbook(data), ods_to_workbook(data)
    entry = current.pivots.get("PivotSales")
    assert entry is not None
    current.pivots.put("PivotSales", replace(entry, definition=replace(entry.definition, total_row=False)))
    current._calculate_loaded()
    assert kinds(ods_unwritten_changes(current, baseline)) == {"pivot-table": 1}


def test_the_source_of_a_kept_pivot_edited_gives_the_new_numbers_in_the_cells_the_file_keeps():
    data = a_libreoffice_file()
    baseline, current = ods_to_workbook(data), ods_to_workbook(data)
    current.sheet("s1").cells[(1, 2)] = {"t": "int", "v": 1000}  # North, Q1: 100 -> 1000
    current._calculate_loaded()
    assert ods_unwritten_changes(current, baseline) == ()  # (the definition is as it was; the numbers are written)
    out = apply_edits_to_ods(data, baseline, current)
    assert pilots(out) == pilots(data)
    back = ods_to_workbook(out)
    assert back.value("s2", 5, 1) == 1000
    assert back.value("s2", 7, 1) == 1140  # the total of Q1
    assert back.pivots.get("PivotSales") is not None


def test_a_pivot_made_in_a_kept_file_gives_its_cells_and_is_said_not_written():
    data = an_ods(DATA)
    baseline = ods_to_workbook(data)
    doc = Document(ods_to_workbook(data), store=MemoryStore())
    source = RangeRef.between(CellRef(0, 0, "s1"), CellRef(6, 3, "s1"))
    doc.execute(DefineName(NamedRange("Sales", None, source, True)), author="ana")
    doc.execute(
        create_pivot(doc.model, "P", ("s2", 0, 0), by_region_and_quarter(), None, new_sheet="Pivot"), author="ana"
    )
    losses = LossLog()
    out = apply_edits_to_ods(data, baseline, doc.model, losses=losses)
    back = ods_to_workbook(out)
    assert back.value("s2", 0, 0) == "Sum of Amount"
    assert back.value("s2", 5, 3) == 600
    assert pilots(out) == []
    assert kinds(ods_unwritten_changes(doc.model, baseline)).get("pivot-table") == 1


def test_a_file_that_is_not_ods_is_still_refused():
    try:
        ods_to_workbook(b"no")
    except OdfError:
        return
    raise AssertionError("an OdfError was expected")
