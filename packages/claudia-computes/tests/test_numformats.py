"""Number formats (D348): reading a code, naming what it shows, and showing a value through it -- checked against the
cases the web client's renderer is checked against too, so the two cannot drift apart."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claudia_computes.numformats import (
    ENGLISH,
    GERMAN,
    NumberFormat,
    NumberFormatBook,
    check_code,
    describe,
    kind_of,
    render,
)

CASES = json.loads((Path(__file__).parent / "number_format_cases.json").read_text(encoding="utf-8"))["cases"]
SYMBOLS = {"en": ENGLISH, "de": GERMAN}


@pytest.mark.parametrize("case", CASES, ids=[f"{c['code']}|{c['value']}|{c['locale']}" for c in CASES])
def test_a_value_shows_as_excel_shows_it(case):
    assert render(case["value"], case["code"], SYMBOLS[case["locale"]]) == case["shows"]


@pytest.mark.parametrize(
    ("code", "kind"),
    [
        ("General", "general"),
        ("0.00", "number"),
        ('#,##0 "MWh"', "number"),
        ("0.0%", "percent"),
        ("0.00E+00", "scientific"),
        ("# ?/?", "fraction"),
        ("dd.mm.yyyy", "date"),
        ("[$-407]mmm/\\ yy;@", "date"),
        ("h:mm", "time"),
        ("[h]:mm:ss", "time"),
        ("@", "text"),
    ],
)
def test_a_code_says_what_it_shows(code, kind):
    assert kind_of(code) == kind


@pytest.mark.parametrize(
    ("code", "name"),
    [
        ('0 "MWh"', "MWh"),
        ('#,##0.00 "€"', "€, 2 decimals"),
        ("0.0%", "percent, 1 decimal"),
        ("0.000", "3 decimals"),
        ("#,##0", "whole number, thousands"),
        ("dd.mm.yyyy", "date"),
        ("m/d/yyyy", "short date"),
        ('0 "°C"', "°C"),
        ('"Betrachtungszeitraum: "0" Jahre"', "Betrachtungszei…"),
    ],
)
def test_an_imported_format_is_named_by_what_it_shows(code, name):
    assert describe(code) == name


def test_the_book_refuses_a_second_format_of_the_same_name_or_a_bad_code():
    book = NumberFormatBook()
    book.add(NumberFormat("mwh", "MWh", '0 "MWh"', to_name=True))
    with pytest.raises(ValueError, match="called"):
        book.add(NumberFormat("other", "mwh", "0"))
    with pytest.raises(ValueError, match="1 to 255"):
        check_code("")
    with pytest.raises(ValueError, match="four sections"):
        check_code("0;0;0;@;0")
    assert book.free_name("MWh") == "MWh 2"
    assert book.by_code('0 "MWh"') is book.get("mwh")
    assert NumberFormatBook.from_data(book.to_data()).get("mwh") == book.get("mwh")


def test_text_shows_a_number_through_a_code_the_english_way():
    from claudia_computes import Sheet, SheetId, WorkbookModel  # noqa: PLC0415

    model = WorkbookModel()
    sheet = Sheet(SheetId("s1"), "S")
    model.sheets[sheet.id] = sheet
    sheet.cells[(0, 0)] = {"t": "formula", "v": '=TEXT(1234.5,"#,##0.00 ""MWh""")'}
    sheet.cells[(0, 1)] = {"t": "formula", "v": '=TEXT(46339,"mmmm yyyy")'}
    sheet.cells[(0, 2)] = {"t": "formula", "v": '=TEXT("abc","0;0;0;""<""@"">""")'}
    sheet.cells[(0, 3)] = {"t": "formula", "v": '=TEXT(1,"")'}
    sheet.cells[(0, 4)] = {"t": "formula", "v": '=TEXT(1/0,"0")'}
    model.open_container("s1")
    model._calculate_loaded()  # noqa: SLF001
    grid = sheet.grid
    assert grid.get((0, 0)) == "1,234.50 MWh"
    assert grid.get((0, 1)) == "November 2026"
    assert grid.get((0, 2)) == "<abc>"
    assert grid.get((0, 3)).code == "#VALUE!"
    assert grid.get((0, 4)).code == "#DIV/0!"
