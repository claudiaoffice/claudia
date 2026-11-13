"""The Markdown of speaker notes as the lines of a file that has no Markdown (D298): pptx and odp both."""

from __future__ import annotations

import pytest
from claudia_creates_io._notes import Run, lines_to_markdown, markdown_to_lines


def _plain(lines):
    """Each line as its text, to compare without the runs."""
    return ["".join(run.text for run in line) for line in lines]


def test_plain_text_is_one_line_per_line():
    lines, flattened = markdown_to_lines("Open with the story\nThen the numbers")
    assert _plain(lines) == ["Open with the story", "Then the numbers"]
    assert flattened == set()


def test_bold_and_italic_become_runs():
    lines, _ = markdown_to_lines("Say **this** first, *then* ***both***")
    assert lines == [
        [
            Run("Say "),
            Run("this", bold=True),
            Run(" first, "),
            Run("then", italic=True),
            Run(" "),
            Run("both", bold=True, italic=True),
        ]
    ]


def test_underscores_work_like_stars_but_not_inside_a_word():
    lines, _ = markdown_to_lines("_slow_ and snake_case_name")
    assert lines == [[Run("slow", italic=True), Run(" and snake_case_name")]]


def test_an_opening_marker_without_a_closing_one_is_just_text():
    lines, _ = markdown_to_lines("5 * 3 and **open")
    assert _plain(lines) == ["5 * 3 and **open"]
    assert all(not run.bold and not run.italic for run in lines[0])


def test_a_heading_is_a_bold_line():
    lines, flattened = markdown_to_lines("## Opening\nthen text")
    assert lines == [[Run("Opening", bold=True)], [Run("then text")]]
    assert "heading" in flattened


def test_bullets_and_numbers_keep_a_marker_in_the_text():
    lines, _ = markdown_to_lines("- one\n* two\n  - nested\n1. first\n2) second")
    assert _plain(lines) == ["• one", "• two", "  • nested", "1. first", "2) second"]


def test_a_blank_line_is_one_empty_line_however_many():
    lines, _ = markdown_to_lines("a\n\n\n\nb")
    assert _plain(lines) == ["a", "", "b"]


def test_a_link_shows_its_address_and_is_reported():
    lines, flattened = markdown_to_lines("see [the plan](https://example.org/plan) now")
    assert _plain(lines) == ["see the plan (https://example.org/plan) now"]
    assert "link" in flattened


def test_a_picture_shows_its_alt_text_and_is_reported():
    lines, flattened = markdown_to_lines("![a chart](https://example.org/c.png)")
    assert _plain(lines) == ["a chart"]
    assert "image" in flattened


def test_code_is_plain_text_and_reported():
    lines, flattened = markdown_to_lines("run `make all` then\n```\nx = *1*\n```")
    assert _plain(lines) == ["run make all then", "x = *1*"]
    assert flattened == {"code"}


def test_a_quote_loses_its_marker_and_is_reported():
    lines, flattened = markdown_to_lines("> careful here")
    assert _plain(lines) == ["careful here"]
    assert "quote" in flattened


def test_a_backslash_makes_a_marker_literal():
    lines, _ = markdown_to_lines(r"2 \* 3 \*\*not bold\*\*")
    assert _plain(lines) == ["2 * 3 **not bold**"]
    assert all(not run.bold for run in lines[0])


def test_adjacent_runs_with_the_same_look_are_one_run():
    lines, _ = markdown_to_lines("**a****b**")
    assert lines == [[Run("ab", bold=True)]]


@pytest.mark.parametrize(
    "markdown",
    [
        "Open with the story\nThen the numbers",
        "Say **this** first, *then* ***both***",
        "- one\n- two\n  - nested\n\n1. first\n2. second",
        "a\n\nb",
        "",
    ],
)
def test_markdown_survives_a_trip_through_lines(markdown):
    lines, _ = markdown_to_lines(markdown)
    assert lines_to_markdown(lines) == markdown


def test_plain_words_with_markers_in_them_come_back_as_the_same_words():
    """Words from a file are escaped, so what a person typed in Word is not read as Markdown afterwards."""
    markdown = lines_to_markdown([[Run("2 * 3 = 6, [a] _b_ `c` \\ d")]])
    again, _ = markdown_to_lines(markdown)
    assert _plain(again) == ["2 * 3 = 6, [a] _b_ `c` \\ d"]


def test_a_line_that_looks_like_a_heading_or_list_in_a_file_stays_text():
    markdown = lines_to_markdown([[Run("# not a heading")], [Run("+ not a bullet")], [Run("> not a quote")]])
    again, _ = markdown_to_lines(markdown)
    assert _plain(again) == ["# not a heading", "+ not a bullet", "> not a quote"]


def test_bullets_of_a_file_become_markdown_bullets():
    markdown = lines_to_markdown(
        [[Run("• one")], [Run("  • two")], [Run("- three")], [Run("1. four")]],
    )
    assert markdown == "- one\n  - two\n- three\n1. four"


def test_bold_and_italic_runs_become_markers_with_the_spaces_outside():
    markdown = lines_to_markdown([[Run("a "), Run(" b ", bold=True), Run("c"), Run(" d ", True, True), Run("e")]])
    assert markdown == "a  **b** c ***d*** e"


def test_a_run_of_nothing_but_spaces_gets_no_markers():
    assert lines_to_markdown([[Run("a"), Run("  ", bold=True), Run("b")]]) == "a  b"


def test_empty_lines_at_the_end_are_dropped():
    assert lines_to_markdown([[Run("a")], [], [Run("")]]) == "a"
