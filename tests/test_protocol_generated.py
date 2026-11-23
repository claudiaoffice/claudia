"""The protocol files of the web tests are what the server describes today (E11.7).

The web tests talk to one fake server (``web/tests/support/fake-server.ts``) that refuses a method, a parameter or an
event the server's own description does not have. It reads the files this checks, so a test of the web page fails
when the page and the server do not agree, and this one fails when the files are not what the server says.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("generate_protocol", ROOT / "scripts" / "generate_protocol.py")
assert SPEC and SPEC.loader
generate_protocol = importlib.util.module_from_spec(SPEC)
sys.modules["generate_protocol"] = generate_protocol
SPEC.loader.exec_module(generate_protocol)


def test_the_checked_in_files_are_what_the_server_describes():
    stale = [
        path.name
        for path, text in generate_protocol.files().items()
        if not path.exists() or path.read_text(encoding="utf-8") != text
    ]
    assert stale == [], "run `uv run python scripts/generate_protocol.py`"
    assert generate_protocol.main(["--check"]) == 0


def test_every_app_has_its_file_and_each_file_is_json():
    for app in generate_protocol.APPS:
        data = json.loads((generate_protocol.OUT / f"{app}.json").read_text(encoding="utf-8"))
        assert data["app"] == app and data["methods"] and data["events"] and data["errors"]


def test_the_files_say_which_methods_take_a_revision():
    """`base` is the revision a change is made against; a method that does not name it must not be sent one (the
    server answers `bad_request` to a parameter it does not know), so the files say which methods take it."""
    data = json.loads((generate_protocol.OUT / "computes.json").read_text(encoding="utf-8"))
    takes = {name for name, m in data["methods"].items() if any(p["name"] == "base" for p in m["params"])}
    assert {"set_cells", "add_sheet"} <= takes and not {"undo", "redo", "lock", "chat"} & takes
