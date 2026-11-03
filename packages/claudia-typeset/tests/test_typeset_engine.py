"""The typesetter's own work, with stand-in programs for XeLaTeX and pdftocairo: no TeX is needed here.

The stand-ins record how they were called, so these tests show what the real engine is told to do.
"""

import asyncio
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from claudia_typeset import (
    HELP_TOPIC,
    Diagnosis,
    EngineUnavailable,
    FontUnavailable,
    Job,
    Limits,
    Mode,
    OutputTooLarge,
    Timeout,
    Typeset,
    TypesetFailed,
    Typesetter,
    UnsafeOutput,
)

GOOD_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><path d="M 0 0"/></svg>'

XELATEX = r"""#!{python}
import json, os, sys, time
from pathlib import Path

if "--version" in sys.argv:
    print("XeTeX fake {version}")
    print("second line")
    sys.exit(0)
source = Path("main.tex").read_text(encoding="utf-8")
Path({record!r}).write_text(json.dumps({{
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "fonts_conf_exists": os.path.exists(os.environ.get("FONTCONFIG_FILE", "")),
    "env": {{key: os.environ.get(key) for key in
            ("shell_escape", "openin_any", "openout_any", "FONTCONFIG_FILE", "SOURCE_DATE_EPOCH", "HOME", "PATH")}},
    "source": source,
}}))
with open({runs!r}, "a") as runs:
    runs.write("run\n")
if Path({marker!r}).exists():
    print("./main.tex:2: LaTeX Error: File `standalone.cls' not found.")
    sys.exit(1)
if "SLEEP" in source:
    time.sleep(60)
if "FLOOD" in source:
    while True:
        sys.stdout.write("x" * 65536)
lines = source.split("\n")
for number, line in enumerate(lines, 1):
    if "UNDEFINED" in line:
        print(f"./main.tex:{{number}}: Undefined control sequence.")
        print(f"l.{{number}} {{line}}")
        sys.exit(1)
if "SILENT" in source:
    sys.exit(1)
if "NOPDF" not in source:
    Path("main.pdf").write_bytes(b"%PDF fake" + (b" EVIL" if "EVIL" in source else b""))
"""

PDFTOCAIRO = r"""#!{python}
import sys
from pathlib import Path

if "-v" in sys.argv:
    print("pdftocairo version 24.02.0")
    sys.exit(0)
pdf, svg = sys.argv[-2:]
data = Path(pdf).read_bytes()
if b"CONVERTFAIL" in data:
    print("Syntax Error: broken")
    sys.exit(1)
if b"EVIL" in data:
    Path(svg).write_text("<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>")
else:
    Path(svg).write_text({svg!r})
"""


class Fake:
    """Stand-in programs in a folder, and what they saw."""

    def __init__(self, folder: Path, version: str = "1.0") -> None:
        self.folder = folder
        self.record = folder / "record.json"
        self.runs = folder / "runs.log"
        self.marker = folder / "missing-package"  # when this file exists, the engine complains about a missing package
        self.xelatex = self._program("xelatex", XELATEX, version=version)
        self.pdftocairo = self._program("pdftocairo", PDFTOCAIRO)

    def _program(self, name: str, template: str, **values: str) -> Path:
        text = template.format(
            python=sys.executable,
            record=str(self.record),
            runs=str(self.runs),
            marker=str(self.marker),
            svg=GOOD_SVG,
            **values,
        )
        if sys.platform == "win32":  # a script is started through a batch file there
            script = self.folder / f"{name}.py"
            script.write_text(text)
            program = self.folder / f"{name}.cmd"
            program.write_text(f'@"{sys.executable}" "{script}" %*\n')
            return program
        program = self.folder / name
        program.write_text(text)
        program.chmod(program.stat().st_mode | stat.S_IXUSR)
        return program

    @property
    def run_count(self) -> int:
        return self.runs.read_text().count("run") if self.runs.exists() else 0

    @property
    def seen(self) -> dict:
        return json.loads(self.record.read_text())


@pytest.fixture
def fake(tmp_path):
    folder = tmp_path / "fake"
    folder.mkdir()
    return Fake(folder)


@pytest.fixture
def typesetter(tmp_path, catalogue, fake):
    return make_typesetter(tmp_path / "work", catalogue, fake)


def make_typesetter(directory, catalogue, fake, **options):
    return Typesetter(catalogue, directory, xelatex=str(fake.xelatex), pdftocairo=str(fake.pdftocairo), **options)


def typeset(typesetter, job):
    return asyncio.run(typesetter.typeset(job))


def test_a_formula_comes_back_as_a_checked_svg(typesetter):
    result = typeset(typesetter, Job(Mode.MATH, r"\frac{x}{y}"))
    assert isinstance(result, Typeset)
    assert result.svg == GOOD_SVG
    assert result.cached is False


def test_the_engine_is_told_to_refuse_shell_commands_and_to_stop_at_the_first_error(typesetter, fake):
    typeset(typesetter, Job(Mode.MATH, "x"))
    argv = fake.seen["argv"]
    assert "-no-shell-escape" in argv
    assert "-halt-on-error" in argv
    assert "-file-line-error" in argv
    assert "-interaction=nonstopmode" in argv
    assert argv[-1] == "main.tex"


def test_the_engine_runs_in_a_clean_environment_that_only_reaches_its_own_folder_and_the_catalogue_fonts(
    typesetter, fake
):
    typeset(typesetter, Job(Mode.MATH, "x"))
    seen = fake.seen
    env = seen["env"]
    assert env["shell_escape"] == "f"
    assert env["openin_any"] == "p"
    assert env["openout_any"] == "p"
    assert env["SOURCE_DATE_EPOCH"] == "0"
    assert seen["fonts_conf_exists"] is True
    assert env["FONTCONFIG_FILE"].endswith("fonts.conf")
    assert env["HOME"] == seen["cwd"]


def test_the_job_folder_is_gone_afterwards_whatever_happened(typesetter, fake, tmp_path):
    typeset(typesetter, Job(Mode.MATH, "x"))
    with pytest.raises(TypesetFailed):
        typeset(typesetter, Job(Mode.MATH, "UNDEFINED"))
    jobs = tmp_path / "work" / "jobs"
    assert list(jobs.iterdir()) == []


def test_the_same_job_is_not_set_twice(typesetter, fake):
    first = typeset(typesetter, Job(Mode.MATH, "x"))
    second = typeset(typesetter, Job(Mode.MATH, "x"))
    assert second.svg == first.svg
    assert second.cached is True
    assert fake.run_count == 1


def test_a_cache_hit_survives_a_new_typesetter_on_the_same_folder(tmp_path, catalogue, fake):
    typeset(make_typesetter(tmp_path / "work", catalogue, fake), Job(Mode.MATH, "x"))
    again = typeset(make_typesetter(tmp_path / "work", catalogue, fake), Job(Mode.MATH, "x"))
    assert again.cached is True
    assert fake.run_count == 1


def test_another_engine_version_sets_it_again(tmp_path, catalogue, fake):
    typeset(make_typesetter(tmp_path / "work", catalogue, fake), Job(Mode.MATH, "x"))
    (tmp_path / "fake2").mkdir()
    newer = Fake(tmp_path / "fake2", version="2.0")
    result = typeset(make_typesetter(tmp_path / "work", catalogue, newer), Job(Mode.MATH, "x"))
    assert result.cached is False


def test_the_engine_version_is_the_first_line_of_what_it_says(typesetter):
    assert asyncio.run(typesetter.engine_version()) == "XeTeX fake 1.0"


def test_a_tex_error_comes_back_with_the_line_of_the_users_text(typesetter):
    with pytest.raises(TypesetFailed) as raised:
        typeset(typesetter, Job(Mode.PAGE, "fine\nfine\nUNDEFINED here"))
    error = raised.value.error
    assert error is not None
    assert error.message == "Undefined control sequence."
    assert error.line == 3
    assert "UNDEFINED" in error.context
    assert "Undefined control sequence." in str(raised.value)
    assert "line 3" in str(raised.value)


def test_a_failure_is_not_kept_in_the_cache(typesetter, fake):
    for _ in range(2):
        with pytest.raises(TypesetFailed):
            typeset(typesetter, Job(Mode.MATH, "UNDEFINED"))
    assert fake.run_count == 2


def test_a_failure_without_a_message_still_says_something(typesetter):
    with pytest.raises(TypesetFailed, match="without"):
        typeset(typesetter, Job(Mode.MATH, "SILENT"))


def test_an_engine_that_makes_no_pdf_is_a_failure(typesetter):
    with pytest.raises(TypesetFailed, match="no output"):
        typeset(typesetter, Job(Mode.MATH, "NOPDF"))


def test_a_converter_that_fails_is_a_failure(tmp_path, catalogue, fake):
    script = fake.xelatex.with_suffix(".py") if sys.platform == "win32" else fake.xelatex
    script.write_text(script.read_text().replace('b"%PDF fake"', 'b"%PDF CONVERTFAIL"'))
    with pytest.raises(TypesetFailed, match="convert"):
        typeset(make_typesetter(tmp_path / "work", catalogue, fake), Job(Mode.MATH, "x"))


def test_a_picture_with_active_content_is_never_returned_or_kept(typesetter, fake):
    with pytest.raises(UnsafeOutput):
        typeset(typesetter, Job(Mode.MATH, "EVIL"))
    with pytest.raises(UnsafeOutput):
        typeset(typesetter, Job(Mode.MATH, "EVIL"))
    assert fake.run_count == 2


def test_a_job_that_takes_too_long_is_stopped(tmp_path, catalogue, fake):
    typesetter = make_typesetter(tmp_path / "work", catalogue, fake, limits=Limits(seconds=0.7))
    with pytest.raises(Timeout):
        typeset(typesetter, Job(Mode.MATH, "SLEEP"))
    assert list((tmp_path / "work" / "jobs").iterdir()) == []


def test_a_job_that_floods_the_output_is_stopped(tmp_path, catalogue, fake):
    typesetter = make_typesetter(tmp_path / "work", catalogue, fake, limits=Limits(output_mb=1, seconds=20))
    with pytest.raises(OutputTooLarge):
        typeset(typesetter, Job(Mode.MATH, "FLOOD"))


def test_a_missing_engine_is_reported_as_such(tmp_path, catalogue, fake):
    typesetter = Typesetter(
        catalogue, tmp_path / "work", xelatex=str(tmp_path / "nowhere"), pdftocairo=str(fake.pdftocairo)
    )
    with pytest.raises(EngineUnavailable, match="nowhere"):
        typeset(typesetter, Job(Mode.MATH, "x"))


def test_a_font_that_is_not_in_the_catalogue_fails_before_the_engine_starts(typesetter, fake):
    with pytest.raises(FontUnavailable):
        typeset(typesetter, Job(Mode.PAGE, "x", font="Comic Papyrus"))
    assert fake.run_count == 0


def test_the_same_job_run_twice_at_once_gives_two_correct_answers(typesetter):
    async def both():
        return await asyncio.gather(typesetter.typeset(Job(Mode.MATH, "a")), typesetter.typeset(Job(Mode.MATH, "b")))

    first, second = asyncio.run(both())
    assert first.svg == second.svg == GOOD_SVG


def test_fonts_are_those_of_the_catalogue_only(typesetter, fake):
    typeset(typesetter, Job(Mode.MATH, "x"))
    conf = Path(fake.seen["env"]["FONTCONFIG_FILE"])
    # the fake removed nothing: the configuration is kept between jobs, per catalogue
    assert conf.exists()
    assert "<dir>" in conf.read_text()


def test_the_engine_is_given_the_directory_of_its_own_installation_to_find_its_helpers(typesetter, fake):
    """xelatex starts xdvipdfmx by name: the folder of a configured installation must be on the PATH."""
    typeset(typesetter, Job(Mode.MATH, "x"))
    assert fake.seen["env"]["PATH"].split(os.pathsep)[0] == str(fake.folder)


def test_a_folder_is_enough_to_say_where_the_installation_is(tmp_path, catalogue, fake):
    typesetter = Typesetter(catalogue, tmp_path / "work", xelatex=fake.folder, pdftocairo=fake.folder)
    assert typeset(typesetter, Job(Mode.MATH, "x")).svg == GOOD_SVG


def test_without_settings_the_programs_are_looked_for_on_the_path(tmp_path, catalogue, fake, monkeypatch):
    monkeypatch.setenv("PATH", str(fake.folder))
    typesetter = Typesetter(catalogue, tmp_path / "work")
    assert typeset(typesetter, Job(Mode.MATH, "x")).svg == GOOD_SVG


def test_a_wrong_setting_is_an_error_that_says_what_to_do(tmp_path, catalogue, fake):
    typesetter = Typesetter(catalogue, tmp_path / "work", xelatex=tmp_path / "nowhere", pdftocairo=fake.pdftocairo)
    with pytest.raises(EngineUnavailable) as raised:
        typeset(typesetter, Job(Mode.MATH, "x"))
    assert HELP_TOPIC in str(raised.value)
    assert "xelatex" in str(raised.value)


def test_a_server_without_latex_can_still_be_made_and_asked(tmp_path, catalogue, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    typesetter = Typesetter(catalogue, tmp_path / "work")  # no error here: the server starts without LaTeX
    with pytest.raises(EngineUnavailable):
        typeset(typesetter, Job(Mode.MATH, "x"))


def diagnose(typesetter):
    return asyncio.run(typesetter.diagnose())


def test_a_working_installation_is_diagnosed_as_working(typesetter):
    diagnosis = diagnose(typesetter)
    assert isinstance(diagnosis, Diagnosis)
    assert diagnosis.ok
    assert [step.name for step in diagnosis.steps] == ["xelatex", "pdftocairo", "fonts", "test document"]
    assert all(step.ok for step in diagnosis.steps)


def test_the_diagnosis_says_which_programs_were_found_and_their_versions(typesetter, fake):
    steps = {step.name: step for step in diagnose(typesetter).steps}
    assert str(fake.xelatex) in steps["xelatex"].detail
    assert "XeTeX fake 1.0" in steps["xelatex"].detail
    assert str(fake.pdftocairo) in steps["pdftocairo"].detail
    assert "pdftocairo version 24.02.0" in steps["pdftocairo"].detail


def test_the_diagnosis_keeps_no_result_in_the_cache(typesetter, fake):
    diagnose(typesetter)
    diagnose(typesetter)
    assert fake.run_count == 2  # the test document is set again each time, because the point is to try the installation


def test_both_missing_programs_are_reported_at_once_and_the_test_document_is_not_tried(tmp_path, catalogue):
    typesetter = Typesetter(catalogue, tmp_path / "work", xelatex=tmp_path / "a", pdftocairo=tmp_path / "b")
    diagnosis = diagnose(typesetter)
    assert not diagnosis.ok
    failed = [step.name for step in diagnosis.steps if not step.ok]
    assert failed[:2] == ["xelatex", "pdftocairo"]
    assert "test document" not in [step.name for step in diagnosis.steps]
    assert HELP_TOPIC in diagnosis.steps[0].hint


def test_a_missing_math_font_is_reported_with_what_to_add(tmp_path, fake):
    from claudia_fonts import Catalogue

    typesetter = make_typesetter(tmp_path / "work", Catalogue.from_collections([]), fake)
    diagnosis = diagnose(typesetter)
    fonts = next(step for step in diagnosis.steps if step.name == "fonts")
    assert not fonts.ok
    assert "Latin Modern" in fonts.detail
    assert "Latin Modern" in fonts.hint


def test_a_missing_tex_package_is_reported_with_how_to_install_it(typesetter, fake):
    fake.marker.write_text("x")
    diagnosis = diagnose(typesetter)
    step = diagnosis.steps[-1]
    assert step.name == "test document"
    assert not step.ok
    assert "standalone" in step.detail
    assert "tlmgr install standalone" in step.hint
    assert "MiKTeX" in step.hint
