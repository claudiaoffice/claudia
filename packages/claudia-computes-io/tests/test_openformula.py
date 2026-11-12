"""to_openformula / from_openformula: the model's Excel formulas and OpenFormula, as LibreOffice 24.2 writes it.

The pairs are what LibreOffice itself wrote when it converted a workbook holding every function the model implements
(D413), so the translation is checked against the program that reads the file, not only against the standard."""

from __future__ import annotations

import pytest
from claudia_computes_io import Untranslatable, from_openformula, to_openformula

from claudia_computes import function_catalog

PAIRS = [
    ("=ABS(-4.5)", "of:=ABS(-4.5)"),
    ("=AND(TRUE,FALSE)", "of:=AND(TRUE();FALSE())"),
    ("=AVERAGE(A1:A5)", "of:=AVERAGE([.A1:.A5])"),
    ('=AVERAGEIF(A1:A5,">2",B1:B5)', 'of:=AVERAGEIF([.A1:.A5];">2";[.B1:.B5])'),
    ("=CEILING(4.2,1)", "of:=COM.MICROSOFT.CEILING(4.2;1)"),
    ('=_xlfn.CONCAT("a","b")', 'of:=COM.MICROSOFT.CONCAT("a";"b")'),
    ("=COLUMN(B2)", "of:=COLUMN([.B2])"),
    ("=FALSE()", "of:=FALSE()"),
    ("=FLOOR(4.2,1)", "of:=COM.MICROSOFT.FLOOR(4.2;1)"),
    ("=HLOOKUP(2,A1:C2,2,FALSE)", "of:=HLOOKUP(2;[.A1:.C2];2;FALSE())"),
    ('=IF(A1>1,"y","n")', 'of:=IF([.A1]>1;"y";"n")'),
    ('=_xlfn.IFS(A1>1,"a",TRUE,"b")', 'of:=COM.MICROSOFT.IFS([.A1]>1;"a";TRUE();"b")'),
    ('=_xlfn.MAXIFS(A1:A5,B1:B5,">2")', 'of:=COM.MICROSOFT.MAXIFS([.A1:.A5];[.B1:.B5];">2")'),
    ("=_xlfn.STDEV.P(A1:A5)", "of:=COM.MICROSOFT.STDEV.P([.A1:.A5])"),
    ('=_xlfn.SWITCH(2,1,"a",2,"b")', 'of:=COM.MICROSOFT.SWITCH(2;1;"a";2;"b")'),
    ('=_xlfn.TEXTJOIN(",",TRUE,A1:A3)', 'of:=COM.MICROSOFT.TEXTJOIN(",";TRUE();[.A1:.A3])'),
    ("=_xlfn.VAR.P(A1:A5)", "of:=COM.MICROSOFT.VAR.P([.A1:.A5])"),
    ("=_xlfn.XOR(TRUE,FALSE)", "of:=XOR(TRUE();FALSE())"),
    ("='My Sheet'!A1+Data!A1", "of:=[$'My Sheet'.A1]+[$Data.A1]"),
    ("=SUM('My Sheet'!A1:A3)", "of:=SUM([$'My Sheet'.A1:.A3])"),
    ("=SUM($A$1:B$2)", "of:=SUM([.$A$1:.B$2])"),
    ("=SUM(A:A)", "of:=SUM([.A:.A])"),
    ("=SUM(1:1)", "of:=SUM([.1:.1])"),
    ('=A1&"x"&B1', 'of:=[.A1]&"x"&[.B1]'),
    ("=-A1^2", "of:=-[.A1]^2"),
    ("=A1%", "of:=[.A1]%"),
    ("=A1<>B1", "of:=[.A1]<>[.B1]"),
    ("=SUM(A1:A3,C1:C3)", "of:=SUM([.A1:.A3];[.C1:.C3])"),
    ('=IF(A1>=1,1500,"say ""hi""")', 'of:=IF([.A1]>=1;1500;"say ""hi""")'),
    ("=#REF!+1", "of:=#REF!+1"),
    ("=SUM({1,2;3,4})", "of:=SUM({1;2|3;4})"),
    ("=SUM( A1 , B1 )", "of:=SUM( [.A1] ; [.B1] )"),
]


@pytest.mark.parametrize(("excel", "open_formula"), PAIRS)
def test_the_model_formula_is_written_as_libreoffice_writes_it(excel, open_formula):
    assert to_openformula(excel) == open_formula


@pytest.mark.parametrize(("excel", "open_formula"), PAIRS)
def test_what_libreoffice_wrote_is_read_back_as_the_same_formula(excel, open_formula):
    back = from_openformula(open_formula)
    assert to_openformula(back) == open_formula


def test_a_formula_the_model_reads_back_calls_only_functions_the_model_has():
    names = {entry.name for entry in function_catalog()}
    assert from_openformula("of:=SUM([.A1:.A3])", names) == "=SUM(A1:A3)"
    assert from_openformula('of:=COM.MICROSOFT.TEXTJOIN(",";TRUE();[.A1:.A3])', names) == '=TEXTJOIN(",",TRUE(),A1:A3)'
    with pytest.raises(Untranslatable) as problem:
        from_openformula("of:=NOSUCH(1)", names)
    assert problem.value.reason == "function"
    assert problem.value.detail == "NOSUCH"


def test_sheet_names_that_need_quotes_get_them_and_plain_ones_do_not():
    assert from_openformula("of:=[$'My Sheet'.A1]+[$Data.B2]") == "='My Sheet'!A1+Data!B2"
    assert from_openformula("of:=SUM([$Data.A1:.B2])") == "=SUM(Data!A1:B2)"
    assert from_openformula("of:=[$'It''s'.A1]") == "='It''s'!A1"


@pytest.mark.parametrize(
    ("excel", "reason"),
    [
        ("=A1:A3 B1:B3", "operator"),  # an intersection
        ("=SUM((A1:A3,C1:C3))", "operator"),  # a union
    ],
)
def test_what_openformula_says_differently_is_not_translated(excel, reason):
    with pytest.raises(Untranslatable) as problem:
        to_openformula(excel)
    assert problem.value.reason == reason


@pytest.mark.parametrize(
    "attribute",
    [
        "msoxl:=SUM(A1)",  # another language
        "=SUM([.A1])",  # no language named
        "of:=SUM([.A1]",  # a bracket not closed
        "of:=[.A1",  # a reference not closed
        "of:=[.A1]![.B1]",  # an intersection
        "of:=([.A1]~[.B1])",  # a union
        "of:=[$$Other.A1]",
        "of:=[$'file.ods'#$Sheet1.A1]",  # another file
        "of:=SUM(MyName)",  # a name defined in the file
        "of:=CEILING(4.2;1)",  # means something else without the prefix
        "of:=ORG.OPENOFFICE.EASTERDATE(2020)",
        "of:=[.A1:.B2:.C3]",
    ],
)
def test_what_the_model_cannot_say_is_not_guessed(attribute):
    with pytest.raises(Untranslatable):
        from_openformula(attribute)


def test_an_untranslatable_formula_says_why_in_a_code_and_in_words():
    with pytest.raises(Untranslatable) as problem:
        from_openformula("msoxl:=SUM(A1)")
    assert problem.value.reason == "dialect"
    assert "dialect" in str(problem.value)


def test_translating_what_the_model_cannot_read_is_a_matter_of_punctuation_only():
    # the formula need not be one the model can read: only its punctuation and names change
    assert to_openformula('=FOO(A1,"b;c")') == 'of:=FOO([.A1];"b;c")'
