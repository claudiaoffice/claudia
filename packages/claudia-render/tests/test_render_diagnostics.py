"""A tool complains in its own words; the person is told which line of their text it was (D393).

Each reader turns one tool's output into diagnostics with a line of the *person's* text: whatever the plugin put in
front of the text (a page setup for Typst) is not the person's and is not counted."""

import pytest

from claudia_render import DIAGNOSTIC_READERS, Diagnostic, read_diagnostics


def test_every_reader_a_manifest_may_name_exists():
    for name in DIAGNOSTIC_READERS:
        assert read_diagnostics(name, "") == ()


def test_a_diagnostic_is_a_severity_a_message_and_where():
    one = Diagnostic("error", "no such box", 3, 5)
    assert one.to_data() == {"severity": "error", "message": "no such box", "line": 3, "column": 5}
    assert Diagnostic("warning", "x").to_data()["line"] is None
    with pytest.raises(ValueError, match="severity"):
        Diagnostic("fatal", "x")


# -- typst, in its short format ----------------------------------------------------------------------------------------
def test_typst_short_lines_become_diagnostics_with_the_line_and_column():
    out = "input.typ:3:1: error: unknown variable: unknown\n"
    assert read_diagnostics("typst-short", out) == (Diagnostic("error", "unknown variable: unknown", 3, 1),)


def test_what_the_plugin_put_in_front_of_the_text_is_not_counted():
    out = "input.typ:4:1: error: unknown variable: x\n"
    assert read_diagnostics("typst-short", out, line_offset=2) == (Diagnostic("error", "unknown variable: x", 2, 1),)


def test_a_complaint_about_what_the_plugin_added_has_no_line_of_the_persons_text():
    out = "input.typ:1:1: error: something in the page setup\n"
    assert read_diagnostics("typst-short", out, line_offset=2)[0].line is None


def test_typst_warnings_and_errors_both_come_through_and_other_lines_are_ignored():
    out = "compiling...\ninput.typ:2:3: warning: this is deprecated\ninput.typ:5:1: error: oops\n"
    assert [(d.severity, d.line) for d in read_diagnostics("typst-short", out)] == [("warning", 2), ("error", 5)]


def test_typst_output_that_is_not_short_still_gives_one_message():
    out = "error: failed to download package\n  ┌─ main.typ:1:8\n"
    (only,) = read_diagnostics("typst-short", out)
    assert only.severity == "error" and "failed to download package" in only.message


# -- mermaid ---------------------------------------------------------------------------------------------------------
MERMAID = """
Error: Parse error on line 3:
...hart LR A -->  B[[[
---------------------^
Expecting 'TAGEND', 'STR', got 'SQS'
Parser.parseError (https://x.invalid/chunk.mjs:1451:21)
    at #evaluate (file:///opt/node_modules/puppeteer-core/lib/ExecutionContext.js:402:19)
"""


def test_mermaids_parse_error_gives_its_line_and_what_it_expected_without_the_stack():
    (only,) = read_diagnostics("mermaid-parse", MERMAID)
    assert only.line == 3 and only.severity == "error"
    assert (
        "Expecting 'TAGEND'" in only.message
        and "puppeteer" not in only.message
        and "Parser.parseError" not in only.message
    )


def test_another_mermaid_error_is_one_message_without_a_line():
    out = "Error: Lexical error on something\n    at foo (file:///x.js:1:1)\n"
    (only,) = read_diagnostics("mermaid-parse", out)
    assert only.line is None and only.message.startswith("Lexical error")


# -- the plain reader -------------------------------------------------------------------------------------------------
def test_the_plain_reader_gives_the_first_lines_as_one_message_without_colour_codes():
    out = "\x1b[31mboom\x1b[0m\n\nsecond line\n" + "\n".join(f"more {n}" for n in range(30))
    (only,) = read_diagnostics("plain", out)
    assert only.message.startswith("boom\nsecond line") and "\x1b" not in only.message
    assert len(only.message) <= 500 and only.line is None


def test_a_reader_nobody_knows_is_refused():
    with pytest.raises(ValueError, match="reader"):
        read_diagnostics("magic", "x")
