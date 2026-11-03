"""Documents are written by people we may not trust: nothing in them may reach outside the job (E3.10).

Each test runs the real engine. What counts is the effect, never only the error: a file that
must not exist does not exist, a secret that must not be read is not in the answer.
"""

import asyncio
import os
import time

import pytest

from claudia_typeset import Job, Limits, Mode, OutputTooLarge, Timeout, TypesetFailed, Typesetter

pytestmark = pytest.mark.usefixtures("needs_tex")


@pytest.fixture
def typesetter(tmp_path, tex_catalogue):
    return Typesetter(tex_catalogue, tmp_path / "work")


def attempt(typesetter, source):
    """Typeset ``source`` as a page. Returns the outcome (a result or the exception) and never raises on a refusal."""
    try:
        return asyncio.run(typesetter.typeset(Job(Mode.PAGE, source)))
    except (TypesetFailed, Timeout, OutputTooLarge) as outcome:
        return outcome


def test_a_shell_command_is_not_run(typesetter, tmp_path):
    marker = tmp_path / "pwned-by-write18"
    attempt(typesetter, rf"\immediate\write18{{touch {marker}}}")
    assert not marker.exists()


def test_a_shell_command_through_a_pipe_is_not_run(typesetter, tmp_path):
    marker = tmp_path / "pwned-by-pipe"
    attempt(typesetter, rf'\input|"touch {marker}"')
    attempt(typesetter, rf'\immediate\openout3=|"touch {marker}"')
    assert not marker.exists()


def test_a_file_outside_the_job_cannot_be_read_by_absolute_path(typesetter, tmp_path):
    secret = tmp_path / "secret.tex"
    secret.write_text("TOPSECRETWORD")
    outcome = attempt(typesetter, rf"\input{{{secret}}}")
    assert isinstance(outcome, TypesetFailed)
    assert "TOPSECRETWORD" not in str(outcome) + outcome.error.context


def test_a_file_outside_the_job_cannot_be_read_by_going_up(typesetter, tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "up.tex").write_text("TOPSECRETWORD")  # two folders above the job's own
    outcome = attempt(typesetter, r"\input{../../up}")
    assert isinstance(outcome, TypesetFailed)
    assert "TOPSECRETWORD" not in str(outcome) + outcome.error.context


def test_a_file_of_the_system_cannot_be_read(typesetter):
    outcome = attempt(typesetter, r"\newread\f \openin\f=/etc/passwd \read\f to \line \line")
    text = outcome.svg if hasattr(outcome, "svg") else str(outcome) + outcome.error.context
    assert "root:" not in text


def test_a_file_cannot_be_written_outside_the_job(typesetter, tmp_path):
    absolute = tmp_path / "written-absolute.txt"
    attempt(typesetter, rf"\immediate\openout5={absolute}\immediate\write5{{x}}\immediate\closeout5")
    attempt(typesetter, r"\immediate\openout5=../../written-relative.txt\immediate\write5{x}\immediate\closeout5")
    assert not absolute.exists()
    assert not (tmp_path / "written-relative.txt").exists()
    assert not (tmp_path / "work" / "written-relative.txt").exists()


def test_a_dot_file_cannot_be_written_in_the_job_folder(typesetter):
    outcome = attempt(typesetter, r"\immediate\openout5=.hidden\immediate\write5{x}\immediate\closeout5")
    assert isinstance(outcome, TypesetFailed)
    assert "write" in outcome.error.message


def test_reading_from_the_terminal_does_not_wait_for_anyone(typesetter):
    started = time.monotonic()
    outcome = attempt(typesetter, r"\newread\t \read16 to \x")
    assert isinstance(outcome, TypesetFailed)
    assert time.monotonic() - started < 15


def test_a_macro_that_grows_without_end_is_stopped_by_tex_itself(typesetter):
    outcome = attempt(typesetter, r"\def\a{\a\a}\a")
    assert isinstance(outcome, (TypesetFailed, Timeout, OutputTooLarge))


def test_a_file_that_includes_itself_is_stopped(typesetter):
    outcome = attempt(typesetter, r"\input{main}")
    assert isinstance(outcome, (TypesetFailed, Timeout, OutputTooLarge))


def test_a_loop_that_never_ends_and_never_grows_is_stopped_by_the_clock(tmp_path, tex_catalogue):
    """Nothing here fills memory or output: only the wall clock can stop it."""
    typesetter = Typesetter(tex_catalogue, tmp_path / "work", limits=Limits(seconds=2))
    started = time.monotonic()
    outcome = attempt(typesetter, r"\def\a{\a}\a")
    assert isinstance(outcome, Timeout)
    assert time.monotonic() - started < 10


def test_a_flood_of_messages_is_stopped_by_the_output_limit(tmp_path, tex_catalogue):
    typesetter = Typesetter(tex_catalogue, tmp_path / "work", limits=Limits(output_mb=1, seconds=30))
    outcome = attempt(
        typesetter, r"\def\a{\message{xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx}\a}\a"
    )
    assert isinstance(outcome, (OutputTooLarge, TypesetFailed, Timeout))


def test_nothing_of_a_stopped_job_stays_behind(tmp_path, tex_catalogue):
    typesetter = Typesetter(tex_catalogue, tmp_path / "work", limits=Limits(seconds=1))
    attempt(typesetter, r"\def\a{\a}\a")
    assert list((tmp_path / "work" / "jobs").iterdir()) == []


def test_no_engine_process_survives_a_stopped_job(tmp_path, tex_catalogue):
    typesetter = Typesetter(tex_catalogue, tmp_path / "work", limits=Limits(seconds=1))
    attempt(typesetter, r"\def\a{\a}\a")
    time.sleep(0.3)
    running = [
        entry
        for entry in os.listdir("/proc")
        if entry.isdigit() and _cmdline(entry).startswith("xelatex") and str(tmp_path) in _cmdline(entry, full=True)
    ]
    assert running == []


def _cmdline(pid: str, *, full: bool = False) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as stream:
            text = stream.read().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return ""
    return text if full else text.split(" ", 1)[0].rsplit("/", 1)[-1]


def test_a_picture_made_from_hostile_text_is_still_only_drawing(typesetter):
    from claudia_typeset import check_svg

    outcome = attempt(typesetter, r"\textbf{<script>alert(1)</script>} \&\% \$ \# \_ <svg onload=x>")
    assert hasattr(outcome, "svg")
    check_svg(outcome.svg)
    assert "<script" not in outcome.svg
