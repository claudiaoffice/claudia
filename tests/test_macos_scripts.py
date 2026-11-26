"""The shell scripts of the macOS package (E8.5, D1625, D1627, D1628), run on Linux under a temporary folder that
stands for the Mac's start volume (macOS Installer passes it as ``$3``; ``uninstall.sh`` takes it as ``$1``).

The Mac's own commands are stand-ins on PATH that write what they were asked into a log: ``launchctl`` (the service is
loaded when ``$LOADED`` is set), ``dscl`` (the accounts in ``$ACCOUNTS`` exist; ``$USED`` are the numbers in use),
``pkill``, ``pkgutil``, ``chown``, and ``chmod`` for ``+a`` (an ACL; a mode is set for real). What only a Mac can
tell -- that launchd starts the server, that the ACL lets an administrator read the setup code -- is test-install.sh's.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MACOS = ROOT / "packaging" / "macos"
CLAUDIA = "Library/Application Support/Claudia"
LABEL = "de.claudia-office.server"

STANDINS = {
    "launchctl": 'echo "launchctl $*" >> "$LOG"\ncase "$1" in print) [ -n "$LOADED" ] ;; *) exit 0 ;; esac\n',
    "dscl": 'echo "dscl $*" >> "$LOG"\n'
    'case "$2" in\n'
    '  -read) for a in $ACCOUNTS; do [ "$3" = "/Users/$a" ] || [ "$3" = "/Groups/$a" ] && exit 0; done; exit 56 ;;\n'
    '  -list) for n in $USED; do echo "someone $n"; done ;;\n'
    "esac\n",
    "pkill": 'echo "pkill $*" >> "$LOG"\nexit 1\n',
    "pkgutil": 'echo "pkgutil $*" >> "$LOG"\n',
    "chown": 'echo "chown $*" >> "$LOG"\n',
    "chmod": 'case "$1" in +a) echo "chmod $*" >> "$LOG" ;; *) exec /bin/chmod "$@" ;; esac\n',
}


@pytest.fixture
def mac(tmp_path):
    volume = tmp_path / "volume"
    volume.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in STANDINS.items():
        stand_in = bin_dir / name
        stand_in.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        stand_in.chmod(0o755)
    log = tmp_path / "log"
    log.touch()

    def run(script: Path, *arguments: str, **environment: str) -> subprocess.CompletedProcess:
        env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "LOG": str(log), "LOADED": "", "ACCOUNTS": "", "USED": ""}
        return subprocess.run(
            ["/bin/sh", str(script), *arguments], env=env | environment, capture_output=True, text=True, check=False
        )

    def asked() -> list[str]:
        return log.read_text(encoding="utf-8").splitlines()

    return volume, run, asked


def make(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def install_args(volume: Path) -> tuple[str, str, str, str]:
    """What macOS Installer passes a script: the package, the install location, the volume, the volume again."""
    return ("/tmp/claudia.pkg", str(volume), f"{volume}/", str(volume))


# ------------------------------------------------------------------------------------------------- the apps' part
def test_before_an_update_the_service_is_stopped_and_the_old_runtime_and_apps_go(mac):
    volume, run, asked = mac
    old = make(volume / CLAUDIA / "runtime" / "python" / "lib" / "gone_in_the_new_version.py")
    make(volume / "Applications" / "claudia composes.app" / "Contents" / "old")
    documents = make(volume / CLAUDIA / "shared" / "documents" / "budget.claudia")
    done = run(MACOS / "scripts" / "apps" / "preinstall", *install_args(volume), LOADED="1")
    assert done.returncode == 0, done.stderr
    assert f"launchctl bootout system/{LABEL}" in asked()
    assert not old.exists() and not (volume / "Applications" / "claudia composes.app").exists()
    assert documents.exists()


def test_a_first_install_stops_nothing(mac):
    volume, run, asked = mac
    assert run(MACOS / "scripts" / "apps" / "preinstall", *install_args(volume)).returncode == 0
    assert not any("bootout" in line for line in asked())


def test_after_an_update_the_service_runs_the_new_version(mac):
    volume, run, asked = mac
    plist = make(volume / "Library" / "LaunchDaemons" / f"{LABEL}.plist")
    assert run(MACOS / "scripts" / "apps" / "postinstall", *install_args(volume)).returncode == 0
    assert f"launchctl bootstrap system {plist}" in asked()


def test_without_the_service_nothing_is_started(mac):
    volume, run, asked = mac
    assert run(MACOS / "scripts" / "apps" / "postinstall", *install_args(volume)).returncode == 0
    assert not any("bootstrap" in line for line in asked())


# ------------------------------------------------------------------------------------------------ the service
def test_the_service_gets_a_hidden_account_with_a_free_number_below_500(mac):
    volume, run, asked = mac
    make(volume / "Library" / "LaunchDaemons" / f"{LABEL}.plist")
    done = run(MACOS / "scripts" / "service" / "postinstall", *install_args(volume), USED="0 501 499 498")
    assert done.returncode == 0, done.stderr
    for line in (
        "dscl . -create /Users/_claudia UniqueID 497",
        "dscl . -create /Groups/_claudia PrimaryGroupID 497",
        "dscl . -create /Users/_claudia UserShell /usr/bin/false",
        "dscl . -create /Users/_claudia IsHidden 1",
    ):
        assert line in asked()


def test_an_account_that_is_there_is_kept(mac):
    volume, run, asked = mac
    make(volume / "Library" / "LaunchDaemons" / f"{LABEL}.plist")
    assert (
        run(MACOS / "scripts" / "service" / "postinstall", *install_args(volume), ACCOUNTS="_claudia").returncode == 0
    )
    assert not any("-create" in line for line in asked())


def test_the_shared_folders_belong_to_the_service_and_its_setup_code_is_for_the_macs_administrators(mac):
    volume, run, asked = mac
    make(volume / "Library" / "LaunchDaemons" / f"{LABEL}.plist")
    assert run(MACOS / "scripts" / "service" / "postinstall", *install_args(volume)).returncode == 0
    shared = volume / CLAUDIA / "shared"
    assert (shared / "documents").is_dir() and (shared / "state" / "admin").is_dir()
    assert f"chown -R _claudia:_claudia {shared} {volume}/Library/Logs/Claudia" in asked()
    acl = [line for line in asked() if line.startswith("chmod +a")]
    admin = next(line for line in acl if line.endswith(f"{shared}/state/admin"))
    assert "group:admin allow" in admin and "read" in admin and "file_inherit" in admin
    assert any(line.endswith(f"{shared} {shared}/state") and "search" in line for line in acl)
    assert oct((shared / "state" / "admin").stat().st_mode & 0o777) == "0o700"


def test_the_service_is_started_now_and_restarted_if_it_ran(mac):
    volume, run, asked = mac
    plist = make(volume / "Library" / "LaunchDaemons" / f"{LABEL}.plist")
    assert run(MACOS / "scripts" / "service" / "postinstall", *install_args(volume), LOADED="1").returncode == 0
    lines = asked()
    assert lines.index(f"launchctl bootout system/{LABEL}") < lines.index(f"launchctl bootstrap system {plist}")


# ------------------------------------------------------------------------------------------------- uninstalling
LAST_WORDS = (
    "claudia is removed. These folders are left: the shared documents in /Library/Application Support/Claudia/shared/"
    "documents, and each person's own documents and settings in ~/Library/Application Support/Claudia. Delete them if "
    "you no longer need them."
)


@pytest.fixture
def installed(mac):
    volume, run, asked = mac
    paths = {
        **{
            app: make(volume / "Applications" / f"claudia {app}.app" / "Contents" / "Info.plist")
            for app in ("composes", "computes", "creates")
        },
        "uninstaller": make(
            volume / "Applications" / "Utilities" / "uninstall claudia.app" / "Contents" / "Info.plist"
        ),
        "runtime": make(volume / CLAUDIA / "runtime" / "VERSION"),
        "daemon": make(volume / "Library" / "LaunchDaemons" / f"{LABEL}.plist"),
        "service file": make(volume / CLAUDIA / "service.json"),
        "service log": make(volume / "Library" / "Logs" / "Claudia" / "server.log"),
        "caches": make(volume / "Users" / "anna" / "Library" / "Caches" / "Claudia" / "run" / "composes" / "window.sh"),
    }
    kept = {
        "shared documents": make(volume / CLAUDIA / "shared" / "documents" / "budget.claudia"),
        "her documents": make(volume / "Users" / "anna" / CLAUDIA / "documents" / "letter.claudia"),
        "her settings": make(volume / "Users" / "anna" / CLAUDIA / "shell.json"),
        "her logs": make(volume / "Users" / "anna" / "Library" / "Logs" / "Claudia" / "composes.log"),
    }
    return volume, run, asked, paths, kept


def test_uninstalling_leaves_only_documents_and_settings_and_says_so(installed):
    volume, run, asked, paths, kept = installed
    done = run(MACOS / "uninstall.sh", str(volume), LOADED="1", ACCOUNTS="_claudia")
    assert done.returncode == 0, done.stderr
    for name, path in paths.items():
        assert not path.exists(), name
    for name, path in kept.items():
        assert path.exists(), name
    assert done.stdout.strip().splitlines()[-1] == LAST_WORDS


def test_uninstalling_stops_the_service_and_removes_its_account_and_the_receipts(installed):
    volume, run, asked, _, _ = installed
    run(MACOS / "uninstall.sh", str(volume), LOADED="1", ACCOUNTS="_claudia")
    lines = asked()
    assert f"launchctl bootout system/{LABEL}" in lines
    assert "dscl . -delete /Users/_claudia" in lines and "dscl . -delete /Groups/_claudia" in lines
    assert f"chown -R root:admin {volume}/{CLAUDIA}/shared" in lines
    assert f"pkgutil --volume {volume} --forget de.claudia-office.apps" in lines
    assert f"pkgutil --volume {volume} --forget de.claudia-office.service" in lines


def test_uninstalling_ends_every_process_of_claudia_and_not_itself(installed):
    """By what they run, of every person of the Mac: the windows, the cores (from her run folder), the servers."""
    volume, run, asked, _, _ = installed
    run(MACOS / "uninstall.sh", str(volume))
    patterns = [line.removeprefix("pkill -f ") for line in asked() if line.startswith("pkill")]
    c = f"{volume}/{CLAUDIA}"
    running = [
        f"{volume}/Applications/claudia computes.app/Contents/MacOS/neutralino --path=/Users/anna/Library/Caches/x",
        "/Users/anna/Library/Caches/Claudia/run/computes/node ext/core.mjs",
        f"{c}/runtime/node/bin/node {c}/runtime/client/dist/launch.js computes --prepare",
        f"{c}/runtime/server/../python/bin/python3 -I -m claudia_server --port 20501",
    ]
    for command in running:
        assert any(re.search(pattern, command) for pattern in patterns), command
    for command in (
        f"/bin/sh {c}/runtime/uninstall.sh",
        f"/bin/sh -c '{c}/runtime/uninstall.sh'",
        f"{volume}/Applications/Utilities/uninstall claudia.app/Contents/MacOS/uninstall-claudia",
    ):
        assert not any(re.search(pattern, command) for pattern in patterns), command


def test_uninstalling_twice_does_no_harm(installed):
    volume, run, _, _, kept = installed
    run(MACOS / "uninstall.sh", str(volume))
    done = run(MACOS / "uninstall.sh", str(volume))
    assert done.returncode == 0, done.stderr
    assert all(path.exists() for path in kept.values())


# ------------------------------------------------------------------------------------------------------- shellcheck
SCRIPTS = [
    MACOS / "scripts" / "apps" / "preinstall",
    MACOS / "scripts" / "apps" / "postinstall",
    MACOS / "scripts" / "service" / "postinstall",
    MACOS / "uninstall.sh",
    MACOS / "uninstall-app.sh",
    MACOS / "test-install.sh",
]


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck is not installed")
@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_each_script_passes_shellcheck_as_posix_sh(script):
    done = subprocess.run(["shellcheck", "--shell=sh", str(script)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout
