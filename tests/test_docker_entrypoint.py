"""The container's entry point names the first administrator from a platform's secret variables (D1376).

``docker/entrypoint.sh`` is run with a stand-in ``python`` first on the ``PATH`` that writes down its arguments and
environment instead of starting a server."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ENTRYPOINT = Path(__file__).resolve().parents[1] / "docker" / "entrypoint.sh"

pytestmark = pytest.mark.skipif(shutil.which("sh") is None or os.name != "posix", reason="needs a POSIX shell")


def run(tmp_path, **env):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    seen = tmp_path / "seen"
    fake = bin_dir / "python"
    fake.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {seen}/args\nenv > {seen}/env\n', encoding="utf-8")
    fake.chmod(0o755)
    seen.mkdir(exist_ok=True)
    environment = {"PATH": f"{bin_dir}:/usr/bin:/bin", "TMPDIR": str(tmp_path), **env}
    done = subprocess.run(["sh", str(ENTRYPOINT)], env=environment, capture_output=True, text=True, check=False)
    args = (seen / "args").read_text().splitlines() if (seen / "args").exists() else []
    environ = (seen / "env").read_text() if (seen / "env").exists() else ""
    return done, args, environ


def test_the_secret_variables_become_admin_and_a_private_password_file(tmp_path):
    done, args, environ = run(tmp_path, CLAUDIA_ADMIN="anna", CLAUDIA_ADMIN_PASSWORD="a-long-password")
    assert done.returncode == 0, done.stderr
    at = args.index("--admin")
    assert args[at + 1] == "anna"
    password_file = Path(args[args.index("--admin-password-file") + 1])
    assert password_file.read_text(encoding="utf-8") == "a-long-password\n"
    assert stat.S_IMODE(password_file.stat().st_mode) == 0o600
    assert "CLAUDIA_ADMIN_PASSWORD=" not in environ


def test_without_the_variables_nothing_is_added(tmp_path):
    done, args, _ = run(tmp_path)
    assert done.returncode == 0, done.stderr
    assert "--admin" not in args and "--admin-password-file" not in args


def test_a_password_without_a_name_stops_the_container(tmp_path):
    done, args, _ = run(tmp_path, CLAUDIA_ADMIN_PASSWORD="a-long-password")
    assert done.returncode == 2
    assert "CLAUDIA_ADMIN" in done.stderr
    assert args == []
