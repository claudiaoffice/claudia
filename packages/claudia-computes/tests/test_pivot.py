"""Pivot tables, step one (E6.30, D620-D625): the definition, the SQL it is made into, and the grid it gives.

The tests read the source from a plain dictionary of tables: a pivot is a query over a named table, and nothing in
these tests needs a workbook."""

from __future__ import annotations

import math

import pytest

from claudia_computes import (
    Aggregation,
    PivotDefinition,
    PivotError,
    PivotFilter,
    PivotLabels,
    PivotRole,
    ValueField,
    compute_pivot,
)
from claudia_computes import sql as sql_engine
from claudia_computes.pivot_sql import literal
from claudia_computes.spill import Matrix

HEADERS = ["Region", "Product", "Quarter", "Units", "Unit price", "Amount"]
ROWS = [
    ("North", "Desk", "Q1", 12, 75, 900),
    ("North", "Lamp", "Q2", 40, 25, 1000),
    ("North", "Chair", "Q3", 8, 100, 800),
    ("South", "Desk", "Q1", 20, 75, 1500),
    ("South", "Chair", "Q2", 16, 98.75, 1580),
    ("South", "Desk", "Q3", 17, 100, 1700),
    ("East", "Lamp", "Q1", 40, 25, 1000),
    ("East", "Desk", "Q2", 10, 77.5, 775),
    ("East", "Lamp", "Q3", 40, 25, 1000),
    ("West", "Chair", "Q1", 12, 100, 1200),
]
TABLES = {"Sales": (HEADERS, ROWS)}


def tables(name):
    return TABLES.get(name)


AMOUNT = (ValueField("Amount"),)


def pivot(*, rows=(), columns=(), values=AMOUNT, filters=(), source="Sales", **flags):
    return PivotDefinition(source, tuple(rows), tuple(columns), tuple(values), tuple(filters), **flags)


def compute(definition, source=tables, **kwargs):
    return compute_pivot(definition, source, **kwargs)


def shown(result):
    return [list(row) for row in result.rows]


def roles(result):
    return [list(row) for row in result.roles]


# ------------------------------------------------------------------------------------ the definition
def test_a_definition_has_both_totals_by_default():
    definition = PivotDefinition("Sales")
    assert definition.total_row and definition.total_column
    assert definition.rows == definition.columns == definition.values == definition.filters == ()


def test_a_definition_survives_its_plain_data_form():
    definition = pivot(
        rows=["Region"],
        columns=["Quarter"],
        values=[ValueField("Amount"), ValueField("Units", Aggregation.AVERAGE, "Mean units")],
        filters=[PivotFilter("Product", ("Desk", None, 3)), PivotFilter("Unit price")],
        total_column=False,
    )
    data = definition.to_data()
    assert data["format"] == 1
    assert PivotDefinition.from_data(data) == definition


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"nonsense": 1}, "unknown key 'nonsense'"),
        ({"format": 2}, "format"),
        ({"rows": "Region"}, "rows"),
        ({"values": [{"field": "Amount", "aggregation": "median"}]}, "aggregation"),
        ({"filters": [{"field": "Product", "keep": []}]}, "keep"),
        ({"total_row": "yes"}, "total_row"),
        ({"source": ""}, "source"),
    ],
)
def test_data_that_is_not_a_definition_is_refused_with_the_part_that_is_wrong(change, message):
    with pytest.raises(PivotError, match=message):
        PivotDefinition.from_data(pivot(rows=["Region"]).to_data() | change)


def test_a_definition_is_one_json_object():
    with pytest.raises(PivotError, match="one JSON object"):
        PivotDefinition.from_data([])


def test_this_version_takes_one_row_field_and_one_column_field():
    with pytest.raises(PivotError, match="one row field"):
        pivot(rows=["Region", "Product"])
    with pytest.raises(PivotError, match="one column field"):
        pivot(columns=["Region", "Product"])


def test_a_field_is_in_one_area_only_but_a_value_may_repeat_a_row_field():
    with pytest.raises(PivotError, match="Region"):
        pivot(rows=["Region"], columns=["region"])
    with pytest.raises(PivotError, match="Product"):
        pivot(rows=["Region"], filters=[PivotFilter("Product"), PivotFilter("product")])
    pivot(rows=["Region"], values=[ValueField("Region", Aggregation.COUNT)])


# ------------------------------------------------------------------------------------ rows, columns, values
def test_rows_and_columns_and_one_value_with_both_totals():
    result = compute(pivot(rows=["Region"], columns=["Quarter"]))
    assert shown(result) == [
        ["Sum of Amount", "Quarter", None, None, None],
        ["Region", "Q1", "Q2", "Q3", "Total"],
        ["East", 1000, 775, 1000, 2775],
        ["North", 900, 1000, 800, 2700],
        ["South", 1500, 1580, 1700, 4780],
        ["West", 1200, None, None, 1200],
        ["Total", 4600, 3355, 3500, 11455],
    ]
    assert (result.height, result.width, result.header_rows) == (7, 5, 2)


def test_every_cell_has_the_role_a_style_can_follow():
    result = compute(pivot(rows=["Region"], columns=["Quarter"]))
    corner, field, head, label, value, total = (
        PivotRole.CORNER,
        PivotRole.FIELD,
        PivotRole.HEADER,
        PivotRole.LABEL,
        PivotRole.VALUE,
        PivotRole.TOTAL,
    )
    assert roles(result) == [
        [corner, field, head, head, head],
        [field, head, head, head, head],
        [label, value, value, value, total],
        [label, value, value, value, total],
        [label, value, value, value, total],
        [label, value, value, value, total],
        [total, total, total, total, total],
    ]


def test_the_totals_can_be_left_out():
    result = compute(pivot(rows=["Region"], columns=["Quarter"], total_row=False, total_column=False))
    assert shown(result) == [
        ["Sum of Amount", "Quarter", None, None],
        ["Region", "Q1", "Q2", "Q3"],
        ["East", 1000, 775, 1000],
        ["North", 900, 1000, 800],
        ["South", 1500, 1580, 1700],
        ["West", 1200, None, None],
    ]


def test_rows_and_one_value():
    result = compute(pivot(rows=["Region"]))
    assert shown(result) == [
        ["Region", "Sum of Amount"],
        ["East", 2775],
        ["North", 2700],
        ["South", 4780],
        ["West", 1200],
        ["Total", 11455],
    ]
    assert roles(result)[0] == [PivotRole.FIELD, PivotRole.HEADER]
    assert roles(result)[-1] == [PivotRole.TOTAL, PivotRole.TOTAL]


def test_rows_and_two_values_are_two_columns():
    result = compute(pivot(rows=["Region"], values=[ValueField("Amount"), ValueField("Units", Aggregation.AVERAGE)]))
    assert result.rows[0] == ("Region", "Sum of Amount", "Average of Units")
    east, total = result.rows[1], result.rows[-1]
    assert east[:2] == ("East", 2775) and east[2] == pytest.approx(30.0)
    assert total[:2] == ("Total", 11455) and total[2] == pytest.approx(21.5)


def test_columns_alone_give_one_row_of_totals():
    result = compute(pivot(columns=["Quarter"]))
    assert shown(result) == [
        ["Sum of Amount", "Quarter", None, None, None],
        [None, "Q1", "Q2", "Q3", "Total"],
        ["Total", 4600, 3355, 3500, 11455],
    ]
    assert roles(result)[1][0] == PivotRole.HEADER
    assert roles(result)[2] == [PivotRole.TOTAL] * 5


def test_values_alone_give_one_row_of_totals():
    result = compute(pivot(values=[ValueField("Amount"), ValueField("Units", Aggregation.MAX)]))
    assert shown(result) == [[None, "Sum of Amount", "Max of Units"], ["Total", 11455, 40]]


def test_with_rows_and_columns_and_two_values_the_values_sit_under_each_column_member():
    result = compute(
        pivot(rows=["Region"], columns=["Quarter"], values=[ValueField("Amount"), ValueField("Units", Aggregation.MAX)])
    )
    assert (result.height, result.width, result.header_rows) == (3 + 4 + 1, 1 + 8, 3)
    assert result.rows[0] == (None, "Quarter") + (None,) * 7
    assert result.rows[1] == (None, "Q1", None, "Q2", None, "Q3", None, "Total", None)
    assert result.rows[2] == ("Region",) + ("Sum of Amount", "Max of Units") * 4
    assert result.rows[3] == ("East", 1000, 40, 775, 10, 1000, 40, 2775, 40)
    assert result.rows[-1] == ("Total", 4600, 40, 3355, 40, 3500, 40, 11455, 40)


@pytest.mark.parametrize(
    ("aggregation", "expected"),
    [
        (Aggregation.SUM, 6),
        (Aggregation.COUNT, 3),
        (Aggregation.AVERAGE, 2.0),
        (Aggregation.MIN, 1),
        (Aggregation.MAX, 3),
    ],
)
def test_the_five_aggregations(aggregation, expected):
    data = {"T": (["g", "n"], [("a", 1), ("a", 2), ("a", 3), ("a", None), ("b", 10)])}
    result = compute(pivot(source="T", rows=["g"], values=[ValueField("n", aggregation)], total_row=False), data.get)
    assert result.rows[1][0] == "a" and result.rows[1][1] == pytest.approx(expected)


def test_a_value_field_can_be_given_a_name():
    result = compute(pivot(rows=["Region"], values=[ValueField("Amount", name="Revenue")]))
    assert result.rows[0] == ("Region", "Revenue")


def test_a_filter_keeps_some_members_and_the_columns_follow_what_is_left():
    result = compute(
        pivot(rows=["Product"], columns=["Quarter"], filters=[PivotFilter("Region", ("West",))]),
    )
    assert shown(result) == [
        ["Sum of Amount", "Quarter", None],
        ["Product", "Q1", "Total"],
        ["Chair", 1200, 1200],
        ["Total", 1200, 1200],
    ]


def test_a_filter_without_a_selection_keeps_everything():
    assert (
        compute(pivot(rows=["Region"], filters=[PivotFilter("Product")])).rows == compute(pivot(rows=["Region"])).rows
    )


def test_blank_members_are_a_member_of_their_own_and_come_last():
    data = {"B": (["g", "h", "n"], [("a", "x", 1), (None, "x", 2), ("a", None, 3), ("b", "y", 4)])}
    result = compute(pivot(source="B", rows=["g"], columns=["h"], values=[ValueField("n")]), data.get)
    assert shown(result) == [
        ["Sum of n", "h", None, None, None],
        ["g", "x", "y", "(blank)", "Total"],
        ["a", 1, None, 3, 4],
        ["b", None, 4, None, 4],
        ["(blank)", 2, None, None, 2],
        ["Total", 3, 4, 3, 10],
    ]


def test_members_are_sorted_numbers_first_then_text_without_regard_to_case():
    data = {"K": (["k", "n"], [("banana", 1), ("Apple", 1), ("cherry", 1), (10, 1), (2, 1)])}
    result = compute(
        pivot(source="K", rows=["k"], values=[ValueField("n", Aggregation.COUNT)], total_row=False), data.get
    )
    assert [row[0] for row in result.rows[1:]] == [2, 10, "Apple", "banana", "cherry"]


def test_quotes_in_names_and_members_are_only_text():
    data = {"Sales 2026": (["Name", "Unit price"], [("O'Brien", 5), ("Zoe", 7), ('say "hi"', 1)])}
    by_row = compute(
        pivot(source="Sales 2026", rows=["Name"], values=[ValueField("Unit price")], total_row=False), data.get
    )
    assert shown(by_row)[1:] == [["O'Brien", 5], ['say "hi"', 1], ["Zoe", 7]]
    by_column = compute(
        pivot(source="Sales 2026", columns=["Name"], values=[ValueField("Unit price")], total_column=False), data.get
    )
    assert shown(by_column)[1:] == [[None, "O'Brien", 'say "hi"', "Zoe"], ["Total", 5, 1, 7]]


def test_an_infinite_member_is_still_a_member():
    data = {"I": (["x", "n"], [(math.inf, 1), (-math.inf, 2)])}
    result = compute(pivot(source="I", columns=["x"], values=[ValueField("n")], total_column=False), data.get)
    assert result.rows[2] == ("Total", 2, 1)


def test_an_empty_source_gives_the_headers_and_empty_totals():
    data = {"E": (HEADERS, [])}
    result = compute(pivot(source="E", rows=["Region"], columns=["Quarter"]), data.get)
    assert shown(result) == [["Sum of Amount", "Quarter"], ["Region", "Total"], ["Total", None]]


def test_nothing_chosen_gives_an_empty_result():
    result = compute(pivot(rows=["Region"], values=()))
    assert (result.height, result.width, result.rows, result.sql) == (0, 0, (), "")


def test_fields_are_found_without_regard_to_case_and_shown_as_the_source_writes_them():
    result = compute(pivot(rows=["region"], values=[ValueField("amount")]))
    assert result.rows[0] == ("Region", "Sum of Amount")


def test_a_field_the_source_does_not_have_is_named_with_the_ones_it_has():
    with pytest.raises(PivotError, match=r"no field 'Regoin' in Sales: Region, Product"):
        compute(pivot(rows=["Regoin"]))


def test_a_source_that_is_no_table_is_named():
    with pytest.raises(PivotError, match="no table or range named 'Nope'"):
        compute(pivot(source="Nope"))


def test_two_values_with_one_title_are_refused():
    with pytest.raises(PivotError, match="Sum of Amount"):
        compute(pivot(rows=["Region"], values=[ValueField("Amount"), ValueField("amount")]))
    compute(pivot(rows=["Region"], values=[ValueField("Amount"), ValueField("Amount", Aggregation.MAX)]))


def test_the_words_a_pivot_shows_come_from_the_labels():
    german = PivotLabels(total="Gesamt", blank="(leer)", sum_of="Summe von {field}")
    result = compute(pivot(rows=["Region"], columns=["Quarter"]), labels=german)
    assert result.rows[0][0] == "Summe von Amount" and result.rows[1][-1] == "Gesamt" and result.rows[-1][0] == "Gesamt"


def test_too_many_columns_are_refused_in_words():
    data = {"W": (["c", "n"], [(i, 1) for i in range(1001)])}
    with pytest.raises(PivotError, match="1,002 columns"):
        compute(pivot(source="W", columns=["c"], values=[ValueField("n")]), data.get)


def test_what_the_engine_refuses_is_a_pivot_error_with_its_reason(monkeypatch):
    monkeypatch.setattr(sql_engine, "MAX_RESULT_ROWS", 2)
    with pytest.raises(PivotError, match="more than 2 rows"):
        compute(pivot(rows=["Region"], columns=["Quarter"]))


# ------------------------------------------------------------------------------------ the query
def test_the_query_without_totals_is_one_group_by():
    result = compute(pivot(rows=["Region"], columns=["Quarter"], total_row=False, total_column=False))
    assert result.sql == "\n".join(
        [
            'SELECT "Region",',
            '       SUM(CASE WHEN "Quarter" = \'Q1\' THEN "Amount" END) AS "Q1",',
            '       SUM(CASE WHEN "Quarter" = \'Q2\' THEN "Amount" END) AS "Q2",',
            '       SUM(CASE WHEN "Quarter" = \'Q3\' THEN "Amount" END) AS "Q3"',
            'FROM "Sales"',
            'GROUP BY "Region"',
            'ORDER BY "Region" IS NULL, "Region" COLLATE NOCASE, "Region"',
        ]
    )


def test_the_total_row_is_a_second_select_in_the_same_query():
    result = compute(
        pivot(rows=["Region"], values=[ValueField("Amount")], filters=[PivotFilter("Product", ("Desk", None))])
    )
    assert result.sql == "\n".join(
        [
            'SELECT "Region", "Sum of Amount"',
            "FROM (",
            '  SELECT 0 AS "_order",',
            '         "Region",',
            '         SUM("Amount") AS "Sum of Amount"',
            '  FROM "Sales"',
            '  WHERE ("Product" IN (\'Desk\') OR "Product" IS NULL)',
            '  GROUP BY "Region"',
            "  UNION ALL",
            "  SELECT 1,",
            "         'Total',",
            '         SUM("Amount")',
            '  FROM "Sales"',
            '  WHERE ("Product" IN (\'Desk\') OR "Product" IS NULL)',
            ")",
            'ORDER BY "_order", "Region" IS NULL, "Region" COLLATE NOCASE, "Region"',
        ]
    )


@pytest.mark.parametrize(
    "definition",
    [
        pivot(rows=["Region"], columns=["Quarter"]),
        pivot(rows=["Region"]),
        pivot(columns=["Quarter"], values=[ValueField("Units", Aggregation.MAX), ValueField("Amount")]),
        pivot(rows=["Product"], columns=["Quarter"], filters=[PivotFilter("Region", ("North", "South"))]),
    ],
)
def test_the_query_is_all_the_pivot_there_is_run_by_itself_it_gives_the_same_rows(definition):
    result = compute(definition)
    table = sql_engine.run_query(result.sql, (), tables)
    assert [list(row) for row in table.rows] == shown(result)[result.header_rows :]


# ------------------------------------------------------------------------------------ as cells
def test_a_result_fills_cells_like_any_other_table_of_values():
    result = compute(pivot(rows=["Region"]))
    assert result.value_at(1, 0) == "East" and result.role_at(1, 0) == PivotRole.LABEL
    assert result.as_matrix() == Matrix(result.rows)
    with pytest.raises(ValueError, match="at least one cell"):
        compute(pivot(values=())).as_matrix()


# ------------------------------------------------------------------------------------ what is refused
@pytest.mark.parametrize(
    ("build", "message"),
    [
        (lambda: ValueField(" "), "names a field"),
        (lambda: ValueField("Amount", name="two\nlines"), "name"),
        (lambda: PivotFilter(""), "names a field"),
        (lambda: PivotFilter("Product", (object(),)), "keep"),
    ],
)
def test_a_field_without_a_name_or_a_member_that_is_not_a_member_is_refused(build, message):
    with pytest.raises(PivotError, match=message):
        build()


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"format": 1}, "missing 'source'"),
        ({"format": 1, "source": "S", "rows": [1]}, "rows: a list of field names"),
        ({"format": 1, "source": "S", "values": [3]}, "values: each is one JSON object"),
        ({"format": 1, "source": "S", "values": [{"field": "a", "color": 1}]}, "unknown key 'color'"),
        ({"format": 1, "source": "S", "filters": [3]}, "filters: each is one JSON object"),
        ({"format": 1, "source": "S", "filters": [{"field": "a", "keep": 3}]}, "keep: a list of members"),
    ],
)
def test_data_that_is_not_a_definition_names_the_part_that_is_wrong(data, message):
    with pytest.raises(PivotError, match=message):
        PivotDefinition.from_data(data)


def test_the_words_of_a_query_literal():
    assert [literal(value) for value in (None, True, False, 7, 1.5, "it's", math.inf, -math.inf)] == [
        "NULL",
        "1",
        "0",
        "7",
        "1.5",
        "'it''s'",
        "9e999",
        "-9e999",
    ]
    with pytest.raises(TypeError, match="no SQL literal"):
        literal(b"bytes")


def test_a_filter_that_keeps_only_the_blanks_asks_for_nothing_else():
    result = compute(pivot(rows=["Region"], filters=[PivotFilter("Product", (None,))], total_row=False))
    assert 'WHERE "Product" IS NULL' in result.sql and shown(result) == [["Region", "Sum of Amount"]]


def test_a_member_called_like_the_helper_column_does_not_confuse_the_query():
    data = {"O": (["g", "c", "n"], [("a", "_order", 1), ("a", "x", 2)])}
    result = compute(pivot(source="O", rows=["g"], columns=["c"], values=[ValueField("n")]), data.get)
    assert shown(result)[2:] == [["a", 1, 2, 3], ["Total", 1, 2, 3]]
    assert '"_order_"' in result.sql


def test_a_long_list_of_columns_is_one_to_a_line_in_the_outer_select():
    values = [ValueField("Amount"), ValueField("Units", Aggregation.MAX)]
    result = compute(pivot(rows=["Region"], columns=["Quarter"], values=values))
    assert result.sql.startswith('SELECT "Region",\n       "Q1 · Sum of Amount",\n       "Q1 · Max of Units",')


# ------------------------------------------------------------------------------------ which totals it has
@pytest.mark.parametrize(
    ("changes", "total_row", "total_column"),
    [
        ({"rows": ["Region"], "columns": ["Quarter"]}, True, True),
        ({"rows": ["Region"], "columns": ["Quarter"], "total_row": False, "total_column": False}, False, False),
        ({"rows": ["Region"], "columns": ["Quarter"], "total_row": False}, False, True),
        ({"rows": ["Region"]}, True, False),
        ({"columns": ["Quarter"]}, True, True),
        ({}, True, False),
    ],
)
def test_the_result_says_which_totals_it_has(changes, total_row, total_column):
    result = compute(pivot(**changes))
    assert (result.total_row, result.total_column) == (total_row, total_column)


def test_a_pivot_with_nothing_to_add_up_has_no_totals():
    result = compute(pivot(rows=["Region"], values=()))
    assert (result.total_row, result.total_column) == (False, False)
