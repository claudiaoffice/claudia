"""What may be asked of the typesetting service: a job is checked before anything runs (E3.4)."""

import pytest

from claudia_typeset import BadJob, Job, Limits, Mode


def test_a_formula_is_a_job():
    job = Job(Mode.MATH, r"\frac{x}{y}")
    assert job.mode is Mode.MATH
    assert job.files == {}
    assert job.passes == 1


def test_a_blank_source_is_refused():
    with pytest.raises(BadJob, match="empty"):
        Job(Mode.PAGE, "  \n ")


def test_a_source_that_is_too_long_is_refused():
    with pytest.raises(BadJob, match="long"):
        Job(Mode.PAGE, "x" * 300_000)


def test_only_a_document_has_more_files_than_its_source():
    with pytest.raises(BadJob, match="document"):
        Job(Mode.MATH, "x", files={"figure.png": b"x"})


def test_a_document_may_bring_figures_and_a_bibliography():
    job = Job(Mode.DOCUMENT, r"\documentclass{article}", files={"figures/a.png": b"x", "refs.bib": b"@book{}"})
    assert set(job.files) == {"figures/a.png", "refs.bib"}


@pytest.mark.parametrize(
    "name",
    [
        "../x.tex",
        "/etc/passwd",
        "a/../../b.tex",
        "a\\b.tex",
        ".hidden.tex",
        "a/.git/x.tex",
        "",
        "x" * 120 + ".tex",
        "a//b.tex",
    ],
)
def test_a_file_that_could_reach_outside_the_job_folder_is_refused(name):
    with pytest.raises(BadJob, match="file name"):
        Job(Mode.DOCUMENT, "x", files={name: b"x"})


@pytest.mark.parametrize("name", ["style.sty", "class.cls", "setup.cfg", "tool.sh", "noextension", "x.exe"])
def test_code_for_the_engine_is_not_a_document_s_to_bring(name):
    """Class and package files are an administrator's decision, never a document's (D38)."""
    with pytest.raises(BadJob, match="file name|not allowed"):
        Job(Mode.DOCUMENT, "x", files={name: b"x"})


def test_too_many_files_are_refused():
    files = {f"f{i}.tex": b"x" for i in range(101)}
    with pytest.raises(BadJob, match="files"):
        Job(Mode.DOCUMENT, "x", files=files)


def test_files_that_are_together_too_big_are_refused():
    with pytest.raises(BadJob, match="big"):
        Job(Mode.DOCUMENT, "x", files={"a.png": b"x" * 15_000_000, "b.png": b"x" * 15_000_000})


def test_the_main_file_cannot_also_be_one_of_the_other_files():
    with pytest.raises(BadJob, match="main"):
        Job(Mode.DOCUMENT, "x", files={"main.tex": b"y"})


def test_the_main_file_has_a_safe_name_too():
    with pytest.raises(BadJob, match="main"):
        Job(Mode.DOCUMENT, "x", main="../main.tex")


@pytest.mark.parametrize("passes", [0, 4])
def test_the_number_of_passes_is_between_one_and_three(passes):
    with pytest.raises(BadJob, match="passes"):
        Job(Mode.DOCUMENT, "x", passes=passes)


@pytest.mark.parametrize("font", ["Liberation Serif", "Latin Modern Roman", "TeX Gyre Pagella", "Inter"])
def test_ordinary_family_names_are_accepted_for_a_font(font):
    assert Job(Mode.PAGE, "x", font=font).font == font


@pytest.mark.parametrize("font", ["A}\\input{/etc/passwd}", "A\\B", "100%", "a#b", "", "x" * 100])
def test_a_family_name_that_could_carry_tex_code_is_refused(font):
    with pytest.raises(BadJob, match="font"):
        Job(Mode.PAGE, "x", font=font)


@pytest.mark.parametrize("width", [5, 1000])
def test_the_page_width_must_be_reasonable(width):
    with pytest.raises(BadJob, match="width"):
        Job(Mode.PAGE, "x", width_mm=width)


def test_limits_have_sensible_defaults_and_must_be_positive():
    limits = Limits()
    assert limits.seconds > 0
    assert limits.memory_mb >= 1024
    assert limits.pages >= 1
    for field in ("seconds", "memory_mb", "output_mb", "pages"):
        with pytest.raises(ValueError, match=field):
            Limits(**{field: 0})
