"""The macOS package (E8.5, D1625-D1629): what ``packaging/macos/build.py`` lays out, on any system.

The package is built on Linux in CI (the owner, 2026-11-26): nothing here needs a Mac. What only a Mac can tell --
that macOS Installer takes the package, that the apps open -- is ``packaging/macos/test-install.sh``, on the owner's
Mac.
The scripts of the app bundles and of the server are run here for real, with stand-ins for node and Python.
"""

from __future__ import annotations

import importlib.util
import json
import plistlib
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MACOS = ROOT / "packaging" / "macos"
SPEC = importlib.util.spec_from_file_location("macos_build", MACOS / "build.py")
build = importlib.util.module_from_spec(SPEC)
sys.modules["macos_build"] = build
SPEC.loader.exec_module(build)

RUNTIME = "Library/Application Support/Claudia/runtime"


def png(side: int) -> bytes:
    from io import BytesIO

    out = BytesIO()
    Image.new("RGBA", (side, side), (40, 90, 160, 255)).save(out, "PNG")
    return out.getvalue()


def executable(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def fake_repository(root: Path, *, built: bool = True) -> None:
    """What the earlier steps leave behind (npm, `neu update`), as small as can be."""
    (root / "LICENSE").parent.mkdir(parents=True, exist_ok=True)
    (root / "LICENSE").write_text("GPL", encoding="utf-8")
    client = root / "clients" / "neutralino"
    client.mkdir(parents=True)
    (client / "package.json").write_text('{"type": "module"}', encoding="utf-8")
    (client / build.SUITE_ICON).write_bytes(png(256))
    for app in build.APPS:
        folder = client / "apps" / app
        for sub in ("shell", "ext", "js", "bin"):
            (folder / sub).mkdir(parents=True)
        (folder / "bin" / build.NEUTRALINO_BINARY).write_bytes(b"neutralino for macOS")
        (folder / "bin" / "neutralino-win_x64.exe").write_bytes(b"MZ")
        (folder / "shell" / "shell.js").write_text("s", encoding="utf-8")
        (folder / "ext" / "core.mjs").write_text("c", encoding="utf-8")
        (folder / "js" / "neutralino.js").write_text("n", encoding="utf-8")
        (folder / "index.html").write_text("<html>", encoding="utf-8")
        (folder / "neutralino.config.json").write_text("{}", encoding="utf-8")
        (folder / "icon.png").write_bytes(png(256))
        (folder / "icon@4x.png").write_bytes(png(1024))
    if built:
        (client / "dist").mkdir()
        (client / "dist" / "launch.js").write_text("// launcher", encoding="utf-8")
        (root / "web" / ".output" / "public").mkdir(parents=True)
        (root / "web" / ".output" / "public" / "index.html").write_text("<html>", encoding="utf-8")


def fake_python(folder: Path) -> Path:
    """A relocatable CPython as python-build-standalone unpacks (``python/``), the server installed into it."""
    executable(folder / "bin" / "python3", '#!/bin/sh\nprintf "python:%s\\n" "$@"\n')
    site = folder / "lib" / "python3.14" / "site-packages" / "claudia_server"
    site.mkdir(parents=True)
    (site / "__init__.py").write_text("", encoding="utf-8")
    return folder


def fake_node(folder: Path) -> Path:
    executable(folder / "bin" / "node", "#!/bin/sh\n")
    (folder / "LICENSE").write_text("MIT", encoding="utf-8")
    (folder / "lib" / "node_modules" / "npm").mkdir(parents=True)
    return folder


VERSION = build.parse_version("v0.5.0")


@pytest.fixture
def staged(tmp_path):
    repo = tmp_path / "repo"
    fake_repository(repo)
    return build.stage(
        repo,
        tmp_path / "stage",
        python=fake_python(tmp_path / "python"),
        node=fake_node(tmp_path / "node"),
        version=VERSION,
    )


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


# ------------------------------------------------------------------------------------------------------- the apps
@pytest.mark.parametrize("app", ["composes", "computes", "creates"])
def test_each_app_is_a_bundle_in_applications_named_and_marked_for_apple_silicon_and_macos_14(staged, app):
    contents = staged / "apps" / "root" / "Applications" / f"claudia {app}.app" / "Contents"
    info = plistlib.loads((contents / "Info.plist").read_bytes())
    assert info["CFBundleIdentifier"] == f"de.claudia-office.{app}"
    assert info["CFBundleName"] == info["CFBundleDisplayName"] == f"claudia {app}"
    assert info["CFBundleExecutable"] == f"claudia-{app}"
    assert info["CFBundlePackageType"] == "APPL"
    assert info["CFBundleShortVersionString"] == "0.5.0"
    assert info["LSMinimumSystemVersion"] == "14.0"
    assert info["LSArchitecturePriority"] == ["arm64"]
    assert info["NSHighResolutionCapable"] is True
    assert mode(contents / "MacOS" / f"claudia-{app}") == 0o755
    neutralino = contents / "MacOS" / "neutralino"
    assert neutralino.read_bytes() == b"neutralino for macOS" and mode(neutralino) == 0o755
    icon = contents / "Resources" / info["CFBundleIconFile"]
    assert Image.open(icon).format == "ICNS"


def test_an_app_prepares_its_window_with_the_bundled_node_and_becomes_the_window(staged, tmp_path):
    """The app's program, run with the runtime where a test can put it: the launcher writes window.sh, the program
    execs it (D1626). Here node is a stand-in that writes a window.sh which prints what it was started with."""
    runtime = tmp_path / "Library Support" / "runtime"
    home = tmp_path / "home"
    program = (
        staged / "apps" / "root" / "Applications" / "claudia composes.app" / "Contents" / "MacOS" / "claudia-composes"
    )
    text = program.read_text(encoding="utf-8")
    assert f'R="/{RUNTIME}"' in text
    tried = executable(program.parent / "claudia-composes-tried", text.replace(f'R="/{RUNTIME}"', f'R="{runtime}"'))
    executable(
        runtime / "node" / "bin" / "node",
        '#!/bin/sh\nprintf "node:%s\\n" "$@" >> "$HOME/node.txt"\n'
        'mkdir -p "$HOME/Library/Caches/Claudia/run/composes"\n'
        "printf '#!/bin/sh\\necho \"window from $CLAUDIA_NEUTRALINO_BIN\"\\n'"
        ' > "$HOME/Library/Caches/Claudia/run/composes/window.sh"\n',
    )
    done = subprocess.run(
        [str(tried)], env={"HOME": str(home), "PATH": "/usr/bin:/bin"}, capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    log = (home / "Library" / "Logs" / "Claudia" / "composes.log").read_text(encoding="utf-8")
    assert f"window from {program.parent / 'neutralino'}" in log
    assert (home / "node.txt").read_text(encoding="utf-8").splitlines() == [
        f"node:{runtime}/client/dist/launch.js",
        "node:composes",
        "node:--prepare",
    ]


def test_an_app_whose_preparing_fails_starts_no_window_and_keeps_the_reason_in_its_log(staged, tmp_path):
    runtime = tmp_path / "runtime"
    home = tmp_path / "home"
    program = (
        staged / "apps" / "root" / "Applications" / "claudia creates.app" / "Contents" / "MacOS" / "claudia-creates"
    )
    tried = executable(
        program.parent / "tried", program.read_text(encoding="utf-8").replace(f'R="/{RUNTIME}"', f'R="{runtime}"')
    )
    executable(runtime / "node" / "bin" / "node", '#!/bin/sh\necho "No Neutralino binary found" >&2\nexit 1\n')
    done = subprocess.run(
        [str(tried)], env={"HOME": str(home), "PATH": "/usr/bin:/bin"}, capture_output=True, text=True, check=False
    )
    assert done.returncode == 1
    assert "No Neutralino binary found" in (home / "Library" / "Logs" / "Claudia" / "creates.log").read_text(
        encoding="utf-8"
    )


def test_the_uninstaller_is_an_app_in_utilities(staged):
    contents = staged / "apps" / "root" / "Applications" / "Utilities" / "uninstall claudia.app" / "Contents"
    info = plistlib.loads((contents / "Info.plist").read_bytes())
    assert info["CFBundleName"] == "uninstall claudia"
    assert info["CFBundleIdentifier"] == "de.claudia-office.uninstall"
    assert mode(contents / "MacOS" / info["CFBundleExecutable"]) == 0o755
    assert Image.open(contents / "Resources" / info["CFBundleIconFile"]).format == "ICNS"


# ---------------------------------------------------------------------------------------------------- the runtime
def test_the_runtime_has_node_python_with_the_server_the_client_and_the_web_frontend(staged):
    runtime = staged / "apps" / "root" / RUNTIME
    assert mode(runtime / "node" / "bin" / "node") == 0o755
    assert (runtime / "node" / "LICENSE").read_text(encoding="utf-8") == "MIT"
    assert not (runtime / "node" / "lib").exists(), "npm is not needed to run anything"
    assert (runtime / "python" / "lib" / "python3.14" / "site-packages" / "claudia_server" / "__init__.py").exists()
    assert (runtime / "web" / "index.html").exists()
    assert (runtime / "client" / "dist" / "launch.js").exists()
    assert json.loads((runtime / "client" / "package.json").read_text(encoding="utf-8")) == {"type": "module"}
    assert (runtime / "VERSION").read_text(encoding="utf-8") == "0.5.0\n"
    assert mode(runtime / "uninstall.sh") == 0o755


@pytest.mark.parametrize("app", ["composes", "computes", "creates"])
def test_the_apps_folders_are_there_without_neutralino_which_is_in_each_app(staged, app):
    folder = staged / "apps" / "root" / RUNTIME / "client" / "apps" / app
    for name in ("index.html", "neutralino.config.json", "shell/shell.js", "ext/core.mjs", "js/neutralino.js"):
        assert (folder / name).exists(), name
    assert not (folder / "bin").exists()


def test_the_client_knows_where_the_frontend_and_the_server_are(staged):
    """src/packaged.ts reads packaged.json beside apps/, relative to the client's folder."""
    client = staged / "apps" / "root" / RUNTIME / "client"
    packaged = json.loads((client / "packaged.json").read_text(encoding="utf-8"))
    assert (client / packaged["web"]).resolve() == (client.parent / "web").resolve()
    assert (client / packaged["server"]).resolve() == (client.parent / "server" / "claudia-server").resolve()


def test_the_server_is_started_by_the_runtimes_python_with_every_argument_as_given(staged, tmp_path):
    """The script finds the Python next to it, also in a folder with spaces (Application Support)."""
    runtime = staged / "apps" / "root" / RUNTIME
    script = runtime / "server" / "claudia-server"
    assert mode(script) == 0o755
    done = subprocess.run(
        [str(script), "--dir", "/a b/documents", "--port", "8765"], capture_output=True, text=True, check=True
    )
    # -I: the runtime's Python ignores what a person set for her own (PYTHONPATH, her site-packages)
    assert done.stdout.splitlines() == [
        "python:-I",
        "python:-m",
        "python:claudia_server",
        "python:--dir",
        "python:/a b/documents",
        "python:--port",
        "python:8765",
    ]


# ---------------------------------------------------------------------------------------------------- the service
def test_the_service_runs_the_server_under_its_own_account_on_this_computer_only(staged):
    plist = staged / "service" / "root" / "Library" / "LaunchDaemons" / f"{build.SERVICE_LABEL}.plist"
    daemon = plistlib.loads(plist.read_bytes())
    assert daemon["Label"] == build.SERVICE_LABEL == "de.claudia-office.server"
    assert daemon["UserName"] == daemon["GroupName"] == "_claudia"
    assert daemon["RunAtLoad"] is True and daemon["KeepAlive"] is True
    arguments = daemon["ProgramArguments"]
    assert arguments[0] == f"/{RUNTIME}/server/claudia-server"
    options = dict(zip(arguments[1::2], arguments[2::2], strict=False))
    assert options["--host"] == "127.0.0.1" and options["--port"] == "8765"
    assert options["--dir"] == "/Library/Application Support/Claudia/shared/documents"
    assert options["--state-dir"] == "/Library/Application Support/Claudia/shared/state"
    assert options["--web"] == f"/{RUNTIME}/web"
    assert "--no-tls" in arguments
    assert daemon["StandardOutPath"] == daemon["StandardErrorPath"] == "/Library/Logs/Claudia/server.log"


def test_the_service_file_names_the_address_and_the_state_folder_the_daemon_is_started_with(staged):
    """What every person's apps read to list "Shared on this computer" (D1622); only root may write it."""
    service = staged / "service" / "root" / "Library" / "Application Support" / "Claudia" / "service.json"
    found = json.loads(service.read_text(encoding="utf-8"))
    daemon = plistlib.loads(
        (staged / "service" / "root" / "Library" / "LaunchDaemons" / f"{build.SERVICE_LABEL}.plist").read_bytes()
    )
    options = dict(zip(daemon["ProgramArguments"][1::2], daemon["ProgramArguments"][2::2], strict=False))
    assert found == {"origin": f"http://127.0.0.1:{options['--port']}", "state": options["--state-dir"]}


def test_each_part_has_its_install_scripts(staged):
    assert sorted(p.name for p in (staged / "apps" / "scripts").iterdir()) == ["postinstall", "preinstall"]
    assert sorted(p.name for p in (staged / "service" / "scripts").iterdir()) == ["postinstall"]
    for script in [*(staged / "apps" / "scripts").iterdir(), *(staged / "service" / "scripts").iterdir()]:
        assert mode(script) == 0o755


# ------------------------------------------------------------------------------------------------ the installer
def distribution(staged) -> ET.Element:
    return ET.fromstring((staged / "Distribution").read_bytes())


@pytest.mark.parametrize("tag", ["v0.5.0", "v1.12.3"])
def test_the_installer_says_which_version_it_installs(tmp_path, tag):
    repo = tmp_path / "repo"
    fake_repository(repo)
    out = build.stage(
        repo,
        tmp_path / "stage",
        python=fake_python(tmp_path / "py"),
        node=fake_node(tmp_path / "node"),
        version=build.parse_version(tag),
    )
    assert distribution(out).findtext("title") == f"claudia {tag[1:]}"
    for ref in distribution(out).iter("pkg-ref"):
        if ref.get("version") is not None:
            assert ref.get("version") == tag[1:]


def test_the_service_is_offered_and_not_chosen_unless_asked_for(staged):
    choices = {c.get("id"): c for c in distribution(staged).iter("choice")}
    assert choices["service"].get("start_selected") == "false"
    assert choices["apps"].get("start_selected") == "true" and choices["apps"].get("enabled") == "false"
    assert [line.get("choice") for line in distribution(staged).find("choices-outline")] == ["apps", "service"]


def test_the_installer_is_for_apple_silicon_and_macos_14_and_installs_for_everyone(staged):
    root = distribution(staged)
    # arm64 keeps Installer from asking for Rosetta; x86_64 lets an Intel Mac run the check, which says why it may not
    assert root.find("options").get("hostArchitectures").split(",") == ["arm64", "x86_64"]
    assert root.find("options").get("customize") == "allow"
    assert root.find("domains").get("enable_localSystem") == "true"
    assert root.find("domains").get("enable_currentUserHome") == "false"
    assert root.find("volume-check/allowed-os-versions/os-version").get("min") == "14.0"
    script = root.findtext("script")
    assert "hw.optional.arm64" in script and "14.0" in script


@pytest.mark.parametrize("language", ["en", "de"])
def test_the_installer_speaks_english_and_german(staged, language):
    resources = staged / "resources" / f"{language}.lproj"
    for page in ("welcome.html", "license.html"):
        assert (resources / page).read_text(encoding="utf-8").strip()
    strings = (resources / "Localizable.strings").read_text(encoding="utf-8")
    keys = {line.split('"')[1] for line in strings.splitlines() if line.startswith('"')}
    used = {c.get("title") for c in distribution(staged).iter("choice")} | {
        c.get("description") for c in distribution(staged).iter("choice") if c.get("description")
    }
    assert used | {"NEEDS_APPLE_SILICON"} <= keys


def test_the_welcome_and_licence_pages_are_named_in_the_installer(staged):
    root = distribution(staged)
    assert root.find("welcome").get("file") == "welcome.html"
    assert root.find("license").get("file") == "license.html"


# ------------------------------------------------------------------------------------------------- refusals, names
def test_stage_says_which_step_is_missing(tmp_path):
    repo = tmp_path / "repo"
    fake_repository(repo, built=False)
    with pytest.raises(build.BuildError, match="npm"):
        build.stage(
            repo,
            tmp_path / "stage",
            python=fake_python(tmp_path / "py"),
            node=fake_node(tmp_path / "node"),
            version=VERSION,
        )


def test_stage_refuses_a_python_without_the_server_in_it(tmp_path):
    repo = tmp_path / "repo"
    fake_repository(repo)
    python = tmp_path / "py"
    executable(python / "bin" / "python3", "#!/bin/sh\n")
    with pytest.raises(build.BuildError, match="build.py server"):
        build.stage(repo, tmp_path / "stage", python=python, node=fake_node(tmp_path / "node"), version=VERSION)


@pytest.mark.parametrize(
    ("tag", "name"),
    [
        ("v0.5.0", "claudia-office-0.5.0-macos-arm64.pkg"),
        ("v1.12.3", "claudia-office-1.12.3-macos-arm64.pkg"),
        ("v2.0.0", "claudia-office-2.0.0-macos-arm64.pkg"),
    ],
)
def test_every_release_has_a_package_named_after_its_version(tag, name):
    assert build.package_name(build.parse_version(tag)) == name


def test_the_server_is_installed_for_macos_on_apple_silicon_from_the_lock_file(tmp_path):
    commands = build.server_install_commands(tmp_path / "python", tmp_path / "requirements.txt")
    export, install = commands
    assert export[:2] == ["uv", "export"] and "--package" in export and "claudia-server" in export
    assert "--no-dev" in export and "--frozen" in export
    assert install[:3] == ["uv", "pip", "install"]
    assert install[install.index("--python-platform") + 1] == "aarch64-apple-darwin"
    assert install[install.index("--python-version") + 1] == "3.14"
    assert install[install.index("--target") + 1] == str(tmp_path / "python" / "lib" / "python3.14" / "site-packages")
    assert "--only-binary" in install
