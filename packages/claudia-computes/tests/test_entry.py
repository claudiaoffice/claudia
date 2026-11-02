"""What typing into a cell means: numbers, text, TRUE/FALSE, an empty cell."""

import pytest

from claudia_computes import parse_input


@pytest.mark.parametrize(
    ("typed", "content"),
    [
        ("", None),
        ("   ", None),
        ("'", None),
        ("42", {"t": "int", "v": 42}),
        (" -7 ", {"t": "int", "v": -7}),
        ("+3", {"t": "int", "v": 3}),
        ("3.5", {"t": "float", "v": 3.5}),
        (".5", {"t": "float", "v": 0.5}),
        ("2.", {"t": "float", "v": 2.0}),
        ("1e3", {"t": "float", "v": 1000.0}),
        ("-2.5E-1", {"t": "float", "v": -0.25}),
        ("true", {"t": "bool", "v": True}),
        ("False", {"t": "bool", "v": False}),
        ("hello world", {"t": "text", "v": "hello world"}),
        ("'007", {"t": "text", "v": "007"}),
        ("'true", {"t": "text", "v": "true"}),
        ("1,5", {"t": "text", "v": "1,5"}),
        ("12abc", {"t": "text", "v": "12abc"}),
        ("nan", {"t": "text", "v": "nan"}),
        ("inf", {"t": "text", "v": "inf"}),
        ("1e999", {"t": "text", "v": "1e999"}),
        ("١٢٣", {"t": "text", "v": "١٢٣"}),
    ],
)
def test_typing_is_read_like_a_spreadsheet_reads_it(typed, content):
    assert parse_input(typed) == content


def test_huge_whole_numbers_become_floats_rather_than_overflow():
    assert parse_input("123456789012345678901234567890")["t"] == "float"
