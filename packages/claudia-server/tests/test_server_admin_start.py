"""What happens to a server's administrators before it listens: the setup code, a reset, naming one at start (SEC-12,
D1371, D1375, D1376)."""

import json
import os
import stat

import pytest

from claudia_server.admin import AdminDirectory
from claudia_server.admin_start import (
    AdminOptions,
    dismiss_reset_note,
    load_reset_note,
    prepare_administrators,
)
from claudia_server.server_settings import ServerSettings, load_admins, load_settings, save_admins, save_settings
from claudia_server.setup_code import read_code

NOW = "2026-11-20T14:03:12Z"
PASSWORD = "correct horse battery"


def directory(state_dir, *names):
    admins = AdminDirectory(cost=2**4)
    for name in names:
        admins.add(name, PASSWORD, added="2026-11-01T00:00:00Z")
    if names:
        save_admins(state_dir, admins)
    return admins


def password_file(tmp_path, text):
    path = tmp_path / "password"
    path.write_text(text, encoding="utf-8")
    return path


def prepare(state_dir, admins, link=None, **options):
    return prepare_administrators(state_dir, admins, AdminOptions(**options), link_base=link, now=NOW)


# --------------------------------------------------------------------------------------------------- the code
def test_with_nobody_named_a_code_is_made_written_and_said(tmp_path):
    start = prepare(tmp_path, directory(tmp_path), link="https://claudia.example.org/admin")
    assert start.code is not None
    assert read_code(tmp_path) == start.code
    said = "\n".join(start.banner)
    assert "no administrator yet" in said
    assert f"setup code   {start.code}" in said
    assert f"or open      https://claudia.example.org/admin#setup={start.code}" in said
    assert f"also in      {tmp_path / 'admin' / 'setup-code'}" in said
    assert said.count(str(start.code)) == 2  # the code and the link, nothing else


def test_without_the_web_app_there_is_no_link(tmp_path):
    start = prepare(tmp_path, directory(tmp_path))
    assert "or open" not in "\n".join(start.banner)


def test_with_administrators_there_is_no_code_and_an_old_file_goes(tmp_path):
    prepare(tmp_path, directory(tmp_path))
    assert read_code(tmp_path) is not None
    start = prepare(tmp_path, directory(tmp_path, "anna", "ben"))
    assert start.code is None
    assert read_code(tmp_path) is None
    assert start.banner == ("administrators: anna, ben",)


def test_every_start_makes_a_new_code(tmp_path):
    first = prepare(tmp_path, directory(tmp_path)).code
    second = prepare(tmp_path, directory(tmp_path)).code
    assert first != second
    assert read_code(tmp_path) == second


# -------------------------------------------------------------------------------------------------- the reset
def test_a_reset_removes_the_administrators_only_and_keeps_them_aside(tmp_path):
    settings = ServerSettings(max_documents=7, access_secret="a secret of the server")
    save_settings(tmp_path, settings)
    admins = directory(tmp_path, "anna", "ben")
    before = (tmp_path / "admin" / "admins.json").read_bytes()

    start = prepare(tmp_path, admins, reset=True)

    assert len(admins) == 0
    reloaded = AdminDirectory(cost=2**4)
    load_admins(tmp_path, reloaded)
    assert len(reloaded) == 0
    kept = tmp_path / "admin" / "admins-before-reset-2026-11-20T14-03-12Z.json"
    assert kept.read_bytes() == before
    if os.name == "posix":
        assert stat.S_IMODE(kept.stat().st_mode) == 0o600
    assert load_settings(tmp_path, default_max_documents=1).dump() == settings.dump()
    said = "\n".join(start.banner)
    assert f"administrators reset: anna, ben removed (kept aside as {kept.name}); settings unchanged" in said
    assert start.code is not None  # nobody is named, so a code is made
    assert start.reset is not None and start.reset.previous == ("anna", "ben") and start.reset.at == NOW


def test_the_reset_note_is_kept_until_it_is_dismissed(tmp_path):
    prepare(tmp_path, directory(tmp_path, "anna", "ben"), reset=True)
    note = load_reset_note(tmp_path)
    assert note is not None and note.previous == ("anna", "ben")
    # a later start without --reset-administrators still has it, and says nothing about it
    later = prepare(tmp_path, directory(tmp_path, "carla"))
    assert later.reset == note
    assert not any("reset" in line for line in later.banner)
    dismiss_reset_note(tmp_path)
    dismiss_reset_note(tmp_path)
    assert load_reset_note(tmp_path) is None


def test_a_reset_with_nobody_to_remove_leaves_no_note(tmp_path):
    start = prepare(tmp_path, directory(tmp_path), reset=True)
    assert start.reset is None
    assert "administrators reset: there were none" in start.banner


def test_a_damaged_reset_note_is_no_note(tmp_path):
    (tmp_path / "admin").mkdir()
    (tmp_path / "admin" / "reset.json").write_text("{", encoding="utf-8")
    assert load_reset_note(tmp_path) is None


# ------------------------------------------------------------------------------------------------ --admin NAME
def test_admin_names_the_first_administrator_and_no_code_is_made(tmp_path):
    admins = directory(tmp_path)
    start = prepare(tmp_path, admins, name="anna", password_file=password_file(tmp_path, f"{PASSWORD}\n"))
    assert [a.name for a in admins.list_admins()] == ["anna"]
    assert admins.verify("anna", PASSWORD) is not None
    reloaded = AdminDirectory(cost=2**4)
    load_admins(tmp_path, reloaded)
    assert reloaded.verify("anna", PASSWORD) is not None
    assert start.code is None and read_code(tmp_path) is None
    assert start.banner == ("administrators: anna (named at start with --admin)",)


def test_only_the_first_line_of_the_password_file_counts(tmp_path):
    admins = directory(tmp_path)
    prepare(tmp_path, admins, name="anna", password_file=password_file(tmp_path, f"{PASSWORD}\r\nsecond line\n"))
    assert admins.verify("anna", PASSWORD) is not None


def test_admin_changes_nothing_when_there_are_administrators(tmp_path):
    admins = directory(tmp_path, "anna")
    start = prepare(tmp_path, admins, name="anna", password_file=password_file(tmp_path, "a new password\n"))
    assert admins.verify("anna", PASSWORD) is not None
    assert admins.verify("anna", "a new password") is None
    assert start.banner == ("administrators: anna", "--admin anna changed nothing: this server has administrators")


def test_reset_and_admin_together_put_a_new_first_administrator_in_place(tmp_path):
    admins = directory(tmp_path, "anna", "ben")
    start = prepare(tmp_path, admins, reset=True, name="carla", password_file=password_file(tmp_path, PASSWORD))
    assert [a.name for a in admins.list_admins()] == ["carla"]
    assert start.code is None
    assert start.reset is not None and start.reset.previous == ("anna", "ben")


@pytest.mark.parametrize(
    ("text", "said"),
    [("", "is empty"), ("\n", "is empty"), ("short\n", "at least 8 characters")],
)
def test_a_bad_password_file_stops_the_start_before_anything_changes(tmp_path, text, said):
    admins = directory(tmp_path, "anna")
    with pytest.raises(ValueError, match=said):
        prepare(tmp_path, admins, reset=True, name="carla", password_file=password_file(tmp_path, text))
    assert [a.name for a in admins.list_admins()] == ["anna"]  # not reset either
    assert json.loads((tmp_path / "admin" / "admins.json").read_text())["admins"][0]["name"] == "anna"


def test_a_missing_password_file_or_a_bad_name_stops_the_start(tmp_path):
    with pytest.raises(ValueError, match="cannot read"):
        prepare(tmp_path, directory(tmp_path), name="anna", password_file=tmp_path / "missing")
    with pytest.raises(ValueError, match="administrator name"):
        prepare(tmp_path, directory(tmp_path), name="a/b", password_file=password_file(tmp_path, PASSWORD))
