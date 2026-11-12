"""A chart reading a named table or SQL() result instead of a frozen range (E6.5, D609)."""

from __future__ import annotations

import pytest
from conftest import S1, chart_spec, reopen
from names_helpers import SALES, define, fill
from test_sql import QUERY, result_name

from claudia_computes import ChartError, ChartSpec, DefineDiagram, RemoveName, UpdateDiagram
from claudia_computes.refs import SheetId


def sourced(spec_id="c1", source="Sales", scope=None, **changes) -> ChartSpec:
    return ChartSpec(spec_id, "bar", source=source, source_scope=scope, **changes)


def draw(doc, spec: ChartSpec) -> dict:
    doc.execute(DefineDiagram(spec.to_data()), author="ana")
    return doc.model.chart_figure(spec.id)


@pytest.fixture
def sales(doc):
    fill(doc, SALES)
    define(doc, "Sales", "A1:D4", header=True, grows=True)
    return doc


def test_a_chart_reads_either_a_range_or_a_source_and_never_both_or_neither():
    spec = sourced()
    assert ChartSpec.from_data(spec.to_data()) == spec
    assert "range" not in spec.to_data()
    with pytest.raises(ChartError, match="either a range or a named source"):
        ChartSpec("c1", "bar")
    with pytest.raises(ChartError, match="either a range or a named source"):
        ChartSpec.from_data({**spec.to_data(), "range": chart_spec().to_data()["range"]})
    with pytest.raises(ChartError, match="source_scope"):
        ChartSpec.from_data({**chart_spec().to_data(), "source_scope": "s1"})
    with pytest.raises(ChartError, match="source"):
        ChartSpec.from_data({**spec.to_data(), "source": "  "})


def test_a_chart_draws_the_columns_of_a_named_table(sales):
    figure = draw(sales, sourced())
    assert [trace["name"] for trace in figure["data"]] == ["Units", "Unit price", "Amount"]
    assert figure["data"][0]["x"] == ["North", "South", "East"]
    assert figure["data"][2]["y"] == [25.0, 40.0, 30.0]


def test_a_chart_follows_its_table_as_it_grows(sales):
    draw(sales, sourced())
    fill(sales, {"A5": "West", "B5": 1, "C5": 1, "D5": "=B5*C5"})
    figure = sales.model.chart_figure("c1")
    assert figure["data"][0]["x"] == ["North", "South", "East", "West"]


def test_a_chart_reads_the_result_of_a_query_and_follows_it(sales):
    fill(sales, {"F1": QUERY})
    result_name(sales, "ByRegion", "F1")
    figure = draw(sales, sourced(source="ByRegion"))
    assert [trace["name"] for trace in figure["data"]] == ["Revenue"]
    assert figure["data"][0]["x"] == ["South", "East", "North"]
    fill(sales, {"B2": 100})  # North now earns the most
    assert sales.model.chart_figure("c1")["data"][0]["x"][0] == "North"


def test_a_name_without_cells_draws_an_empty_chart_instead_of_failing(sales):
    draw(sales, sourced())
    sales.execute(RemoveName(None, "Sales"), author="ana")
    assert sales.model.chart_figure("c1")["data"] == []


def test_a_source_must_name_something_this_document_has(sales):
    with pytest.raises(ValueError, match="no name 'Nope'"):
        sales.model.diagram_from_data(sourced(source="Nope").to_data())
    with pytest.raises(ValueError, match="does not know the sheet"):
        sales.model.diagram_from_data(sourced(scope=SheetId("zz")).to_data())


def test_a_sheet_scoped_source_is_found_by_its_scope(sales):
    define(sales, "Local", "A1:B4", header=True, scope=SheetId(S1))
    figure = draw(sales, sourced(source="Local", scope=SheetId(S1)))
    assert [trace["name"] for trace in figure["data"]] == ["Units"]
    with pytest.raises(ValueError, match="no name 'Local'"):
        sales.model.diagram_from_data(sourced(source="Local").to_data())  # not a workbook-wide name


def test_a_named_range_without_a_header_row_reads_its_first_row_as_data(sales):
    define(sales, "Raw", "A2:B4", header=False)
    figure = draw(sales, sourced(source="Raw"))
    assert figure["data"][0]["x"] == ["North", "South", "East"]


def test_a_source_survives_the_log_and_may_replace_a_range(sales):
    draw(sales, sourced())
    sales.execute(UpdateDiagram("c1", sourced().to_data()), author="ana")
    again = reopen(sales)
    assert again.model.chart_figure("c1") == sales.model.chart_figure("c1")
    assert sales.model.charts_reading(SheetId(S1)) == []  # a name, not a sheet, is what it reads
