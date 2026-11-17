"""The TeX source that is built around a formula or a page, and how errors are found again in the user's text."""

import json
from pathlib import Path

import pytest

from claudia_fonts import Catalogue, Collection, CollectionRecord, builtin_folder, collection_folders
from claudia_fonts.testing import make_font
from claudia_typeset import FontUnavailable, Job, Mode, TexError, build_source, parse_log


def lines_of(built):
    return built.text.splitlines()


def test_a_formula_is_set_in_display_style_in_a_cropped_page(catalogue):
    built = build_source(Job(Mode.MATH, r"\frac{x}{y}"), catalogue)
    assert "{standalone}" in built.text
    assert r"\displaystyle" in built.text
    assert lines_of(built)[built.first_line - 1].endswith(r"\frac{x}{y}") or r"\frac{x}{y}" in built.text


def test_the_users_lines_can_be_found_by_line_number(catalogue):
    built = build_source(Job(Mode.PAGE, "first\nsecond\n\\third"), catalogue)
    text = lines_of(built)
    assert text[built.first_line - 1] == "first"
    assert text[built.first_line] == "second"
    assert text[built.first_line + 1] == "\\third"
    assert built.line_count == 3


def test_a_page_has_the_width_it_was_asked_for(catalogue):
    built = build_source(Job(Mode.PAGE, "x", width_mm=120), catalogue)
    assert "varwidth=120mm" in built.text


def test_the_default_fonts_come_from_the_catalogue_and_the_math_font_is_a_math_font(catalogue):
    built = build_source(Job(Mode.MATH, "x"), catalogue)
    assert r"\setmainfont{Latin Modern Roman}" in built.text
    assert r"\setmathfont{Latin Modern Math}" in built.text


def test_a_chosen_font_replaces_the_text_font_only(catalogue):
    built = build_source(Job(Mode.PAGE, "x", font="Liberation Serif"), catalogue)
    assert r"\setmainfont{Liberation Serif}" in built.text
    assert r"\setmathfont{Latin Modern Math}" in built.text


SAMPLE = Path(__file__).resolve().parents[3] / "test-documents" / "stand-in-fonts.json"


@pytest.mark.parametrize(
    "entry",
    [e for e in json.loads(SAMPLE.read_text(encoding="utf-8"))["fonts"] if e["stand_in"]],
    ids=lambda e: e["family"],
)
def test_a_font_of_the_sample_is_set_in_the_stand_in_a_server_with_the_shipped_fonts_has(tmp_path, entry):
    """E3.13: the shared sample's fonts are typeset in the same stand-ins as print and PDF use."""
    math = tmp_path / "math"
    math.mkdir()
    make_font(math / "lmmath.ttf", "Latin Modern Math", math=True)
    shipped = [Collection.from_folder(f) for f in collection_folders(builtin_folder())]
    catalogue = Catalogue.from_collections([*shipped, Collection(math, CollectionRecord("m", "test", True))])
    built = build_source(Job(Mode.PAGE, "x", font=entry["family"]), catalogue)
    assert rf"\setmainfont{{{entry['stand_in']}}}" in built.text


def test_a_font_that_nobody_provides_is_reported_by_name(catalogue):
    with pytest.raises(FontUnavailable, match="Comic Papyrus"):
        build_source(Job(Mode.PAGE, "x", font="Comic Papyrus"), catalogue)


def test_without_a_math_font_a_formula_cannot_be_set(tmp_path):
    folder = tmp_path / "f"
    folder.mkdir()
    make_font(folder / "lm.ttf", "Latin Modern Roman")
    record = CollectionRecord(name="test", licence="l", redistributable=True)
    catalogue = Catalogue.from_collections([Collection(folder, record)])
    with pytest.raises(FontUnavailable, match="math"):
        build_source(Job(Mode.MATH, "x"), catalogue)


def test_a_family_name_from_a_font_file_that_could_carry_tex_is_never_written_into_the_source(tmp_path):
    """The name comes from the catalogue (a substitution table, a font file), so it is checked again."""
    folder = tmp_path / "f"
    folder.mkdir()
    make_font(folder / "lm.ttf", "Latin Modern Roman")
    make_font(folder / "m.ttf", "Latin Modern Math", math=True)
    make_font(folder / "evil.ttf", "Evil}\\input{/etc/passwd}")
    record = CollectionRecord(name="test", licence="l", redistributable=True)
    catalogue = Catalogue.from_collections(
        [Collection(folder, record)], substitutions={"safe name": "Evil}\\input{/etc/passwd}"}
    )
    with pytest.raises(FontUnavailable, match="plain"):
        build_source(Job(Mode.PAGE, "x", font="Safe Name"), catalogue)


def test_a_document_is_not_built_yet(catalogue):
    with pytest.raises(NotImplementedError, match="document"):
        build_source(Job(Mode.DOCUMENT, r"\documentclass{article}"), catalogue)


def test_building_is_a_pure_function_of_its_inputs(catalogue):
    job = Job(Mode.MATH, r"a^2+b^2")
    assert build_source(job, catalogue) == build_source(job, catalogue)


LOG = """This is XeTeX, Version 3.141592653-2.6-0.999995 (TeX Live 2023/Debian)
entering extended mode
(./main.tex
LaTeX2e <2023-11-01>
./main.tex:9: Undefined control sequence.
l.9 \\foo
        {x}
"""


def test_the_first_error_of_a_log_is_found_with_its_line_and_context():
    error = parse_log(LOG, first_line=8, line_count=3)
    assert isinstance(error, TexError)
    assert error.message == "Undefined control sequence."
    assert error.line == 2  # line 9 of the file is the second line of the user's text
    assert error.context.startswith("\\foo")


def test_an_error_outside_the_users_lines_has_no_line():
    error = parse_log(LOG, first_line=1, line_count=3)
    assert error is not None
    assert error.line is None
    assert error.message == "Undefined control sequence."


def test_a_log_without_an_error_gives_none():
    assert parse_log("This is XeTeX\nOutput written on main.pdf (1 page).\n", first_line=1, line_count=1) is None


def test_an_error_without_a_file_and_line_is_still_found():
    log = "! Emergency stop.\n<*> main.tex\n\nNo pages of output.\n"
    error = parse_log(log, first_line=1, line_count=1)
    assert error is not None
    assert error.message == "Emergency stop."
    assert error.line is None


def test_a_missing_font_is_reported_as_such():
    log = '! fontspec error: "font-not-found"\n!\n! The font "Nope" cannot be found.\n'
    error = parse_log(log, first_line=1, line_count=1)
    assert error is not None
    assert "Nope" in error.message


def test_paths_of_our_machine_never_reach_the_message():
    log = "/srv/claudia/jobs/abc123/main.tex:3: Undefined control sequence.\nl.3 \\x\n"
    error = parse_log(log, first_line=3, line_count=1, job_folder="/srv/claudia/jobs/abc123")
    assert error is not None
    assert "/srv/claudia" not in error.message + error.context
    assert error.line == 1


# a real log (TeX Live 2023): the message goes on in the lines that begin with the name of the package in brackets
CONTINUED = "\n".join(
    [
        "/usr/share/texlive/texmf-dist/tex/latex/fontspec/fontspec.sty:45: Fatal Package fontspec Error: "
        "The fontspec package requires either XeTeX or",
        "(fontspec)                      LuaTeX.",
        "(fontspec)                      ",
        "(fontspec)                      You must change your typesetting engine to,",
        '(fontspec)                      e.g., "xelatex" or "lualatex" instead of',
        '(fontspec)                      "latex" or "pdflatex".',
        "",
        "Type <return> to continue.",
        " ...",
        "l.45 \\msg_fatal:nn {fontspec} {cannot-use-pdftex}",
        "",
    ]
)


def test_a_message_that_goes_on_in_the_next_lines_is_whole():
    error = parse_log(CONTINUED, first_line=1, line_count=1)
    assert error is not None
    assert error.message.startswith(
        "Fatal Package fontspec Error: The fontspec package requires either XeTeX or LuaTeX."
    )
    assert 'instead of "latex" or "pdflatex".' in error.message
    assert "(fontspec)" not in error.message and "Type <return>" not in error.message
    assert error.context.startswith("\\msg_fatal")


# the same kind of message when the engine cut its line at 79 characters (the first two lines are 79 characters long)
CUT = "\n".join(
    [
        "./e.tex:2: Package demo Error: This message is deliberately long so that TeX wr",
        "aps its first line of the log well before the end of it, and a second sentence ",
        "follows here..",
        "",
        "See the demo package documentation for explanation.",
        "Type  H <return>  for immediate help.",
        " ...",
        "l.2 ... second sentence follows here.}{Help text.}",
        "",
    ]
)


def test_a_line_that_was_cut_at_the_line_width_is_joined_again():
    assert all(len(line) == 79 for line in CUT.splitlines()[:2])
    error = parse_log(CUT, first_line=1, line_count=3)
    assert error is not None
    assert error.message == (
        "Package demo Error: This message is deliberately long so that TeX wraps its first line of the log well "
        "before the end of it, and a second sentence follows here.."
    )


def test_a_short_message_is_not_joined_with_what_follows_it():
    log = "./main.tex:9: Undefined control sequence.\nl.9 \\foo\n"
    assert parse_log(log, first_line=1, line_count=9).message == "Undefined control sequence."
