"""Write what the web tests know of the server's protocol, from the server's own description (E11.7).

``uv run python scripts/generate_protocol.py``          rewrite ``web/tests/support/protocol/<app>.json``
``uv run python scripts/generate_protocol.py --check``  fail if a checked-in file is not what this would write

The server describes its protocol (``MethodTable.describe``, served at ``/api/<app>/protocol``): the methods with
their parameters, the events, the errors. The web tests talk to one fake server (``web/tests/support/fake-server.ts``)
that refuses a method, a parameter or an event this description does not have, so a method, parameter or event that
is renamed on the server breaks a web test instead of slipping through. The fake reads these files, and
``tests/test_protocol_generated.py`` sees to it that they are what the server describes today.

Only what the fake needs is kept (the names, the types, whether a parameter is required, whether a method changes the
document); the long texts of the description stay on the server.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "tests" / "support" / "protocol"
APPS = ("computes", "composes", "creates")


def described() -> dict[str, dict]:
    """What a server that hosts every app says at ``/api/<app>/protocol``, by app."""
    from claudia_server.cli import make_plan
    from starlette.testclient import TestClient

    with tempfile.TemporaryDirectory() as state:
        plan = make_plan(["--no-tls", "--state-dir", state, "--allow-host", "testserver"])
        with TestClient(plan.app) as client:
            answers = {app: client.get(f"/api/{app}/protocol") for app in APPS}
    for app, answer in answers.items():
        if answer.status_code != 200:
            raise SystemExit(f"/api/{app}/protocol answered {answer.status_code}")
    return {app: answer.json() for app, answer in answers.items()}


def render(app: str, description: dict) -> str:
    """The file of one app: one method to a line, in the order of the names, so a change shows as a changed line."""
    methods = {
        name: {
            "write": method["write"],
            "params": [{"name": p["name"], "type": p["type"], "required": p["required"]} for p in method["params"]],
        }
        for name, method in sorted(description["methods"].items())
    }
    lines = [
        "{",
        f'  "protocol": {description["protocol"]},',
        f'  "app": {json.dumps(app)},',
        f'  "events": {json.dumps(sorted(description["events"]))},',
        f'  "errors": {json.dumps(sorted(description["errors"]))},',
        '  "methods": {',
    ]
    entries = [f"    {json.dumps(name)}: {json.dumps(method)}" for name, method in methods.items()]
    lines.append(",\n".join(entries))
    lines += ["  }", "}", ""]
    return "\n".join(lines)


def files() -> dict[Path, str]:
    """Every file this writes, with its text."""
    return {OUT / f"{app}.json": render(app, description) for app, description in described().items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if a file is out of date")
    args = parser.parse_args(argv)
    wanted = files()
    if args.check:
        stale = [path for path, text in wanted.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
        for path in stale:
            print(f"{path.relative_to(ROOT)} is out of date: run `uv run python scripts/generate_protocol.py`")
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for path, text in wanted.items():
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
