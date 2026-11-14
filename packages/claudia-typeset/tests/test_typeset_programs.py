"""Finding the programs of the person's own LaTeX installation (D90: installing LaTeX is the user's job)."""

import os
import stat
import sys

import pytest

from claudia_typeset import HELP_TOPIC, SETTINGS, EngineUnavailable, resolve_program

WINDOWS = sys.platform == "win32"


def make_program(folder, name):
    """A file the system will accept as a program."""
    path = folder / (name + (".cmd" if WINDOWS else ""))
    path.write_text("@echo off\n" if WINDOWS else "#!/bin/sh\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_the_settings_are_named():
    assert SETTINGS == ("xelatex", "pdftocairo")


def test_a_full_path_to_the_program_is_taken_as_it_is(tmp_path):
    program = make_program(tmp_path, "xelatex")
    assert resolve_program("xelatex", program, "xelatex") == program


def test_a_path_given_as_text_works_too(tmp_path):
    program = make_program(tmp_path, "xelatex")
    assert resolve_program("xelatex", str(program), "xelatex") == program


def test_the_folder_of_the_installation_is_enough(tmp_path):
    program = make_program(tmp_path, "xelatex")
    assert resolve_program("xelatex", tmp_path, "xelatex") == program


def test_a_program_name_is_looked_up_on_the_path(tmp_path, monkeypatch):
    program = make_program(tmp_path, "xelatex")
    monkeypatch.setenv("PATH", str(tmp_path))
    assert resolve_program("xelatex", "xelatex", "xelatex") == program


def test_nothing_configured_means_the_path_is_searched(tmp_path, monkeypatch):
    program = make_program(tmp_path, "xelatex")
    monkeypatch.setenv("PATH", str(tmp_path))
    assert resolve_program("xelatex", None, "xelatex") == program


def test_a_link_is_not_followed_because_the_program_may_behave_by_its_name(tmp_path):
    """TeX Live's xelatex is a link to xetex and decides what to do by the name it was called with."""
    if WINDOWS:
        pytest.skip("links need privileges on Windows")
    real = make_program(tmp_path, "xetex")
    link = tmp_path / "xelatex"
    os.symlink(real, link)
    assert resolve_program("xelatex", link, "xelatex") == link


def test_nothing_found_says_what_to_do(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(EngineUnavailable) as raised:
        resolve_program("xelatex", None, "xelatex")
    message = str(raised.value)
    assert "xelatex" in message
    assert "PATH" in message
    assert HELP_TOPIC in message


def test_a_wrong_setting_names_the_setting_and_the_value(tmp_path):
    with pytest.raises(EngineUnavailable) as raised:
        resolve_program("pdftocairo", tmp_path / "nowhere" / "pdftocairo", "pdftocairo")
    message = str(raised.value)
    assert "pdftocairo" in message
    assert "nowhere" in message
    assert "does not exist" in message
    assert HELP_TOPIC in message


def test_a_folder_without_the_program_says_so(tmp_path):
    with pytest.raises(EngineUnavailable, match="no xelatex in"):
        resolve_program("xelatex", tmp_path, "xelatex")


@pytest.mark.skipif(WINDOWS, reason="every file can be run on Windows if its name says so")
def test_a_file_that_cannot_be_run_says_so(tmp_path):
    path = tmp_path / "xelatex"
    path.write_text("not a program")
    path.chmod(0o644)
    with pytest.raises(EngineUnavailable, match="cannot be run"):
        resolve_program("xelatex", path, "xelatex")


def test_a_program_is_not_found_by_accident_in_the_working_folder(tmp_path, monkeypatch):
    make_program(tmp_path, "xelatex")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with pytest.raises(EngineUnavailable):
        resolve_program("xelatex", None, "xelatex")


def test_a_caller_may_give_its_own_hint_so_that_another_tool_is_not_told_to_install_latex(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(EngineUnavailable) as error:
        resolve_program("typst", None, "typst", hint=" Install Typst from typst.app.")
    assert "Install Typst from typst.app." in str(error.value) and "LaTeX" not in str(error.value)
