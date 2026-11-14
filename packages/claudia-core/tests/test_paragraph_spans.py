"""Replacing stretches of a paragraph without making the replacer the author of the rest (E9.28, E10.19)."""

from claudia_core import Paragraph, Run, replace_spans


def paragraph(text, *runs):
    return Paragraph("p1", "body-text", text, tuple(Run(n, who) for n, who in runs))


def test_the_stretch_is_replaced_and_what_the_replacer_wrote_is_theirs():
    made = replace_spans(paragraph("the red fox", (11, "ana")), [(4, 7, "grey")], "ben")
    assert made.text == "the grey fox"
    assert made.runs == (Run(4, "ana"), Run(4, "ben"), Run(4, "ana"))


def test_the_rest_keeps_whoever_wrote_it():
    made = replace_spans(paragraph("a red fox", (2, "ana"), (7, "ben")), [(2, 5, "blue")], "cy")
    assert made.text == "a blue fox"
    assert [(r.length, r.author) for r in made.runs] == [(2, "ana"), (4, "cy"), (4, "ben")]


def test_several_stretches_are_replaced_whatever_order_they_come_in():
    first = replace_spans(paragraph("red, red", (8, "ana")), [(0, 3, "x"), (5, 8, "yy")], "ben")
    second = replace_spans(paragraph("red, red", (8, "ana")), [(5, 8, "yy"), (0, 3, "x")], "ben")
    assert first == second
    assert first.text == "x, yy"
    assert sum(r.length for r in first.runs) == len(first.text)


def test_replacing_by_nothing_takes_the_stretch_out_with_its_run():
    made = replace_spans(paragraph("a red fox", (9, "ana")), [(1, 5, "")], "ben")
    assert made.text == "a fox"
    assert made.runs == (Run(5, "ana"),)


def test_the_style_and_the_list_item_stay():
    original = Paragraph("p1", "heading-1", "red", (Run(3, "ana"),))
    assert replace_spans(original, [(0, 3, "blue")], "ben").style == "heading-1"


def test_no_edits_changes_nothing():
    original = paragraph("red", (3, "ana"))
    assert replace_spans(original, [], "ben") == original
