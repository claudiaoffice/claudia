"""`generate_menu.py`: the one place the macOS client reads the shared menu manifest from (E5.11/D159).

The macOS client is TypeScript, not Python, and never imports `claudia_shell_gtk` at run time (that package is the
Linux client's, outside the uv workspace, D116). Instead this script runs at development/build time, imports the
*manifest*, which has no GTK dependency (`manifest.py`'s own docstring: "Nothing here imports GTK"), and writes its
`describe()` as JSON next to the TypeScript that reads it. The checked-in file is a cache, not a second source of
truth, so the important property this module guarantees is: **the checked-in JSON can always be reproduced byte for
byte from the manifest it was generated from** — exactly the drift the project has been bitten by before (D28's
About-dialog links, the GTK/web menu drift D121 fixed). `--check` is the guard a CI job runs for that.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import generate_menu  # noqa: E402  (import after the sys.path tweak above, which is what makes it resolvable)


def test_build_returns_the_manifest_s_own_description() -> None:
    listing = generate_menu.build("creates")
    assert listing["app"] == "creates"
    assert listing["menus"][0]["label"] == "File"


def test_build_carries_the_macos_role_through() -> None:
    """The whole point of this script (D158): a Cocoa role set in the shared Python manifest has to survive the
    trip to JSON unchanged, or the TypeScript side has nothing to map Cmd+C onto."""
    listing = generate_menu.build("creates")
    by_id = {a["id"]: a for menu in listing["menus"] for a in generate_menu.flatten(menu)}
    assert by_id["edit.copy"]["role"] == "copy:"
    assert by_id["file.new"]["role"] is None


def test_build_rejects_an_app_the_linux_client_has_no_manifest_for() -> None:
    with pytest.raises(generate_menu.UnknownApp):
        generate_menu.build("spreadsheets")


def test_the_checked_in_file_matches_a_fresh_generation() -> None:
    """The drift guard itself. If this fails, somebody edited `manifest.py` (or the checked-in JSON) without
    running ``python3 generate_menu.py creates`` — see this module's docstring and the script's own ``--check``."""
    checked_in = json.loads((generate_menu.OUT_DIR / "menu.creates.json").read_text(encoding="utf-8"))
    assert checked_in == generate_menu.build("creates")


def test_write_produces_stable_deterministic_json(tmp_path: Path) -> None:
    """Two generations of the same manifest produce byte-identical output, so a real edit is the only thing that
    ever shows up in a diff (sorted keys would not: dict insertion order in ``describe()`` is already stable, so
    this only has to guard against accidentally switching to an unordered writer later)."""
    out = tmp_path / "menu.creates.json"
    generate_menu.write("creates", out)
    first = out.read_text(encoding="utf-8")
    generate_menu.write("creates", out)
    assert out.read_text(encoding="utf-8") == first
    assert first.endswith("\n")  # plays nicely with text-file conventions / diff tools


def test_main_refuses_a_too_old_python_with_a_clear_message_not_a_dataclass_typeerror(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The actual bug report this guards against: on a Mac whose `python3` is older than manifest.py's floor
    (3.12, `slots=True` on `@dataclass` needs 3.10+ and the project's own floor is higher), this script used to
    fail many frames deep inside manifest.py with `TypeError: dataclass() got an unexpected keyword argument
    'slots'` -- true, but useless to someone who just ran `npm run generate-menu`. This script's own floor check
    has to run and refuse *before* `manifest` is ever imported."""
    monkeypatch.setattr(sys, "version_info", (3, 9, 0, "final", 0))
    assert generate_menu.main(["creates"]) == 1
    message = capsys.readouterr().err
    assert "3.12" in message
    assert "3.9" in message


def test_main_check_succeeds_when_the_checked_in_file_is_current() -> None:
    assert generate_menu.main(["creates", "--check"]) == 0


def test_main_check_fails_when_the_file_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stale_dir = tmp_path
    (stale_dir / "menu.creates.json").write_text('{"app": "creates", "menus": [], "header_toggles": []}\n')
    monkeypatch.setattr(generate_menu, "OUT_DIR", stale_dir)
    assert generate_menu.main(["creates", "--check"]) == 1


def test_main_without_check_writes_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generate_menu, "OUT_DIR", tmp_path)
    assert generate_menu.main(["creates"]) == 0
    assert (tmp_path / "menu.creates.json").exists()


def test_main_all_regenerates_every_app_the_linux_client_knows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generate_menu, "OUT_DIR", tmp_path)
    assert generate_menu.main(["--all"]) == 0
    assert {p.name for p in tmp_path.glob("menu.*.json")} == {
        "menu.composes.json",
        "menu.computes.json",
        "menu.creates.json",
    }
