"""The Windows installer's build (D740-D745): the plain file work of ``packaging/windows/build.py``, and that the Inno
Setup script, the service configuration and the client agree with each other.

Inno Setup itself runs only on Windows (the workflow compiles and installs the installer there); what a Linux run can
and does check is every place where two files must say the same thing, because a disagreement shows only when somebody
installs: a file the script names that the stage never makes, a message that has no German, a service name that the
uninstaller and the installer spell differently.
"""

import importlib.util
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WINDOWS = ROOT / "packaging" / "windows"
SPEC = importlib.util.spec_from_file_location("windows_build", WINDOWS / "build.py")
build = importlib.util.module_from_spec(SPEC)
sys.modules["windows_build"] = build
SPEC.loader.exec_module(build)

PNG = b"\x89PNG\r\n\x1a\n" + bytes(8) + struct.pack(">II", 256, 256) + b"data"


# ------------------------------------------------------------------------------------------------------- versions
def test_a_release_tag_is_the_version():
    assert build.parse_version("v1.2.3", 7) == build.Version("1.2.3", "1.2.3.7")
    assert build.parse_version("0.4.0") == build.Version("0.4.0", "0.4.0.0")


def test_a_suffix_stays_in_the_text_and_out_of_the_numbers():
    version = build.parse_version("v1.0.0-rc.1", 3)
    assert version.text == "1.0.0-rc.1"
    assert version.numeric == "1.0.0.3"


@pytest.mark.parametrize("tag", ["", "v1", "v1.2", "latest", "v1.2.x"])
def test_a_tag_that_is_no_version_is_refused(tag):
    with pytest.raises(build.BuildError, match="not a version"):
        build.parse_version(tag)


def test_a_development_build_sorts_before_its_release_and_names_its_commit():
    version = build.development_version("0.3.0", 42, "1a2b3c4d5e6f")
    assert version.text == "0.3.0-dev.42+1a2b3c4"
    assert version.numeric == "0.3.0.42"


# ----------------------------------------------------------------------------------------------------------- icons
def test_an_icon_holds_the_png_whole_and_says_where_it_is():
    icon = build.icon_from_png(PNG)
    reserved, kind, count = struct.unpack("<HHH", icon[:6])
    assert (reserved, kind, count) == (0, 1, 1)
    width, height, _, _, planes, bits, size, offset = struct.unpack("<BBBBHHII", icon[6:22])
    assert (width, height) == (0, 0), "256 is written as 0"
    assert (planes, bits, size) == (1, 32, len(PNG))
    assert icon[offset:] == PNG


def test_the_icons_of_the_apps_are_all_made_from_their_own_png():
    for app in build.APPS:
        icon = build.icon_from_png((ROOT / "clients" / "neutralino" / "apps" / app / "icon.png").read_bytes())
        assert icon[22:30] == b"\x89PNG\r\n\x1a\n"


def test_a_file_that_is_not_a_png_or_too_large_is_refused():
    with pytest.raises(build.BuildError, match="not a PNG"):
        build.icon_from_png(b"GIF89a" + bytes(30))
    with pytest.raises(build.BuildError, match="at most 256"):
        build.icon_from_png(b"\x89PNG\r\n\x1a\n" + bytes(8) + struct.pack(">II", 1024, 1024))


# ------------------------------------------------------------------------------------------------------- pinned
def test_the_pin_of_winsw_is_a_sha256_of_a_versioned_url():
    pin = build.pins()["winsw"]
    assert re.fullmatch(r"[0-9a-f]{64}", pin["sha256"])
    assert f"v{pin['version']}/" in pin["url"] and pin["url"].startswith("https://")


def test_a_file_that_differs_from_its_pin_is_refused(tmp_path):
    file = tmp_path / "tool.exe"
    file.write_bytes(b"one")
    build.verify_sha256(file, build.sha256_of(file))
    with pytest.raises(build.BuildError, match="not the file that was pinned"):
        build.verify_sha256(file, "0" * 64)


# --------------------------------------------------------------------------------------------------------- stage
def fake_repository(root: Path, *, built: bool = True) -> None:
    """The files that the earlier steps leave behind, as small as can be."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "LICENSE").write_text("GPL", encoding="utf-8")
    (root / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")
    client = root / "clients" / "neutralino"
    (client / "bin").mkdir(parents=True)
    for app in build.APPS:
        (client / "bin" / f"{app}.mjs").write_text("// shim", encoding="utf-8")
    (client / "package.json").write_text('{"type": "module"}', encoding="utf-8")
    for app in build.APPS:
        folder = client / "apps" / app
        for sub in ("shell", "ext", "js", "bin"):
            (folder / sub).mkdir(parents=True)
        (folder / "bin" / build.NEUTRALINO_BINARY).write_bytes(b"MZ")
        (folder / "shell" / "shell.js").write_text("s", encoding="utf-8")
        (folder / "ext" / "core.mjs").write_text("c", encoding="utf-8")
        (folder / "js" / "neutralino.js").write_text("n", encoding="utf-8")
        (folder / "index.html").write_text("<html>", encoding="utf-8")
        (folder / "neutralino.config.json").write_text("{}", encoding="utf-8")
        (folder / "icon.png").write_bytes(PNG)
    if built:
        (client / "dist").mkdir()
        (client / "dist" / "launch.js").write_text("// launcher", encoding="utf-8")
        (root / "web" / ".output" / "public").mkdir(parents=True)
        (root / "web" / ".output" / "public" / "index.html").write_text("<html>", encoding="utf-8")
        server = root / "dist" / "claudia-server"
        (server / "_internal").mkdir(parents=True)
        (server / "claudia-server.exe").write_bytes(b"MZ")
        (server / "_internal" / "base_library.zip").write_bytes(b"PK")


@pytest.fixture
def staged(tmp_path):
    repo = tmp_path / "repo"
    fake_repository(repo)
    node = tmp_path / "node"
    node.mkdir()
    (node / "node.exe").write_bytes(b"MZ")
    (node / "LICENSE").write_text("MIT", encoding="utf-8")
    winsw = tmp_path / "WinSW-x64.exe"
    winsw.write_bytes(b"MZ")
    webview2 = tmp_path / "MicrosoftEdgeWebview2Setup.exe"
    webview2.write_bytes(b"MZ")
    launcher = tmp_path / "claudia-start.exe"
    launcher.write_bytes(b"MZ")
    return build.stage(repo, tmp_path / "stage", node, winsw, launcher, webview2)


def test_the_stage_has_every_folder_the_installer_script_takes_from(staged):
    text = iss_text()
    for name, value in re.findall(r'#define (\w+) "([^"]*)"', text):
        text = text.replace("{#" + name + "}", value)
    for source in re.findall(r"Source: \"\{#StageDir\}\\([^\"]+)\"", text):
        folder = staged / source.replace("\\", "/").removesuffix("/*")
        assert folder.exists(), f"claudia.iss takes {source} from the stage, which has none"


def test_the_client_is_whole_and_says_where_the_server_and_the_frontend_are(staged):
    client = staged / "client"
    assert (client / "dist" / "launch.js").exists() and (client / "package.json").exists()
    for app in build.APPS:
        assert (client / "bin" / f"{app}.mjs").exists()
        files = (
            "index.html",
            "neutralino.config.json",
            "icon.png",
            "shell/shell.js",
            "ext/core.mjs",
            "js/neutralino.js",
        )
        for name in files:
            assert (client / "apps" / app / name).exists()
        assert (client / "apps" / app / "bin" / build.NEUTRALINO_BINARY).exists()
    marker = json.loads((client / "packaged.json").read_text(encoding="utf-8"))
    assert (client / marker["web"] / "index.html").resolve() == (staged / "web" / "index.html").resolve()
    assert (client / marker["server"]).resolve() == (staged / "server" / "claudia-server.exe").resolve()


def test_the_launcher_finds_the_apps_where_the_stage_and_the_checkout_have_them(staged):
    """CODE-83, D746: `appFolder` (clients/neutralino/src/paths.ts) is `apps/<app>` beside the launcher's own `dist/`.
    The launcher of the first real install looked for them in a repository the installation does not have."""
    for client in (staged / "client", ROOT / "clients" / "neutralino"):
        for app in build.APPS:
            launcher_folder = client / "dist"
            assert (launcher_folder.parent / "apps" / app / "neutralino.config.json").is_file(), (
                f"{client}: the launcher in {launcher_folder.name}/ would not find the app {app}"
            )


def _install_test_steps() -> dict[str, str]:
    """The steps of the install test job of windows.yml by name, each with its text (no YAML parser: the file is read
    as the text it is, and the steps start at the job's own indentation)."""
    text = (ROOT / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
    job = text[text.index("\n  test:\n") :]
    parts = re.split(r"^      - (?=name: )", job, flags=re.MULTILINE)[1:]
    return {part.splitlines()[0].removeprefix("name: "): part for part in parts}


def test_a_launcher_that_cannot_prepare_its_window_fails_the_install_test():
    """PROC-53: the whole step that starts a window was `continue-on-error` (a runner may have no display), so a
    launcher that stopped on its own error looked like a runner without one, and the first real install was broken
    with a green CI. What needs no display is its own step and must fail the job."""
    steps = _install_test_steps()
    prepares = "The launcher finds the installed app and prepares its window"
    window = "A window opens, and starts the server it needs"
    assert prepares in steps, "no step starts the installed launcher and checks that it prepared the window's folder"
    assert "continue-on-error" not in steps[prepares], "that step may not be allowed to fail"
    assert "HasExited" in steps[prepares], "that step must see a launcher that ended before it prepared the folder"
    assert "ExitCode" in steps[prepares] and "launcher.err" in steps[prepares], "it must say why the launcher ended"
    names = list(steps)
    assert names.index(prepares) < names.index(window), "the check without a display comes before the window check"
    assert "continue-on-error: true" in steps[window], "only the part that needs a display may be advisory"


def test_the_service_runs_the_server_and_serves_the_frontend_where_the_stage_has_them(staged):
    service = ET.parse(staged / "service" / "claudia-service.xml").getroot()
    base = staged / "service"
    executable = service.findtext("executable").replace("%BASE%", str(base)).replace("\\", "/")
    assert (staged / "server" / "claudia-server.exe").resolve() == Path(executable).resolve()
    web = re.search(r'--web "([^"]+)"', service.findtext("arguments")).group(1)
    assert (base / web.replace("%BASE%\\", "").replace("\\", "/")).resolve() == (staged / "web").resolve()


def test_the_icons_are_there_for_the_shortcuts_and_the_setup(staged):
    for app in build.APPS:
        assert (staged / "icons" / f"{app}.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"


def test_winsw_is_named_like_its_configuration(staged):
    for name in ("claudia-service.exe", "claudia-service.xml"):
        assert (staged / "service" / name).exists()


def test_the_licence_of_node_comes_along(staged):
    assert (staged / "node" / "LICENSE-node.txt").read_text(encoding="utf-8") == "MIT"


def test_a_stage_is_made_again_from_nothing(staged, tmp_path):
    (staged / "left-over.txt").write_text("x", encoding="utf-8")
    build.stage(
        tmp_path / "repo", staged, tmp_path / "node", tmp_path / "WinSW-x64.exe", tmp_path / "claudia-start.exe"
    )
    assert not (staged / "left-over.txt").exists()


def test_what_is_not_built_yet_is_named_with_the_step_that_makes_it(tmp_path):
    repo = tmp_path / "repo"
    fake_repository(repo, built=False)
    node = tmp_path / "node"
    node.mkdir()
    (node / "node.exe").write_bytes(b"MZ")
    winsw = tmp_path / "w.exe"
    winsw.write_bytes(b"MZ")
    launcher = tmp_path / "claudia-start.exe"
    launcher.write_bytes(b"MZ")
    with pytest.raises(build.BuildError, match=r"npm ci && npm run build, in web/"):
        build.stage(repo, tmp_path / "out", node, winsw, launcher)


def test_a_missing_launcher_is_named_with_the_step_that_makes_it(tmp_path):
    repo = tmp_path / "repo"
    fake_repository(repo)
    node = tmp_path / "node"
    node.mkdir()
    (node / "node.exe").write_bytes(b"MZ")
    winsw = tmp_path / "w.exe"
    winsw.write_bytes(b"MZ")
    with pytest.raises(build.BuildError, match=r"build.py launcher"):
        build.stage(repo, tmp_path / "out", node, winsw, tmp_path / "claudia-start.exe")


def test_the_installer_is_not_compiled_without_the_webview2_bootstrapper(tmp_path):
    with pytest.raises(build.BuildError, match="fetch-webview2"):
        build.build_installer(tmp_path, build.Version("1.0.0", "1.0.0.0"), tmp_path / "out")


def test_the_compiler_is_given_every_value_the_script_insists_on(tmp_path):
    command = build.installer_command("iscc", tmp_path / "stage", build.Version("1.2.3", "1.2.3.4"), tmp_path / "out")
    assert command[0] == "iscc" and command[-1].endswith("claudia.iss")
    for name in re.findall(r"#ifndef (\w+)\n\s+#error", iss_text()):
        assert any(argument.startswith(f"/D{name}=") for argument in command), f"{name} is required by claudia.iss"


# ----------------------------------------------------------------------------------- the script and what it names
def iss_text() -> str:
    return (WINDOWS / "claudia.iss").read_text(encoding="utf-8-sig")


def test_the_script_is_utf8_with_a_signature_or_inno_reads_the_umlauts_wrong():
    assert (WINDOWS / "claudia.iss").read_bytes().startswith(b"\xef\xbb\xbf")


def test_every_message_the_script_uses_exists_in_every_language():
    text = iss_text()
    used = set(re.findall(r"\{cm:(\w+)\}", text)) | set(re.findall(r"CustomMessage\('(\w+)'\)", text))
    for language in re.findall(r'^Name: "(\w+)"; MessagesFile', text, flags=re.M):
        defined = set(re.findall(rf"^{language}\.(\w+)=", text, flags=re.M))
        assert used <= defined, f"{language} lacks {sorted(used - defined)}"


# The messages of Inno Setup's own Default.isl that the script reads with SetupMessage(msg<Name>). The compiler knows
# only the names Default.isl defines, and an unknown one stops the build with "Unknown identifier" -- which only the
# Windows job sees (it failed on `msgCustomSetupType`, a name that does not exist; the setup type is
# `CustomInstallation`). Add a name here only after finding it in Default.isl of the Inno Setup the workflow installs.
SETUP_MESSAGES_IN_DEFAULT_ISL = {"CustomInstallation"}


def test_the_script_reads_only_setup_messages_that_inno_setup_defines():
    used = set(re.findall(r"SetupMessage\(msg(\w+)\)", iss_text()))
    assert used, "the script reads no setup message any more: drop this test and the list above"
    unknown = sorted(used - SETUP_MESSAGES_IN_DEFAULT_ISL)
    assert not unknown, f"not known to be in Default.isl: {unknown}"


def test_the_languages_are_those_the_suite_has_catalogs_for():
    languages = set(re.findall(r'^Name: "(\w+)"; MessagesFile', iss_text(), flags=re.M))
    assert languages == {path.stem for path in (ROOT / "po").glob("*.po") if path.stem != "xx"} | {"en"}


def _app_starting_lines() -> list[str]:
    """The lines of [Icons] and [Run] that start one of the apps (the others: the service, WebView2's setup)."""
    lines = [line for line in iss_text().splitlines() if line.startswith(("Name:", "Filename:"))]
    return [line for line in lines if re.search(r"Parameters: \"(composes|computes|creates)\"", line)]


def test_the_shortcuts_start_the_hidden_launcher_with_the_name_of_the_app():
    """UX-78, D750: a shortcut that starts node.exe shows node's console for as long as the app runs."""
    lines = _app_starting_lines()
    started = [re.search(r'Parameters: "(\w+)"', line)[1] for line in lines]
    assert set(started) == set(build.APPS), "every app has a shortcut"
    assert len(lines) == 2 * len(build.APPS) + 1, (
        "a Start menu entry and a desktop icon for each app, and the post-install start"
    )
    for line in lines:
        assert 'Filename: "{app}\\client\\claudia-start.exe"' in line, line
        assert "runminimized" not in line, f"{line}: the launcher has no window to minimise"
    assert "node.exe" not in iss_text().replace("{app}\\node\\node.exe", ""), "no entry starts node itself"
    for app in build.APPS:
        assert (ROOT / "clients" / "neutralino" / "bin" / f"{app}.mjs").exists(), "the launcher starts this shim"
        assert f"icons\\{app}.ico" in iss_text()


def test_the_launcher_starts_the_shims_where_the_stage_puts_them(staged):
    """claudia-start.exe finds `node\\node.exe` and `client\\bin\\<app>.mjs` from its own place, <root>\\client."""
    source = (WINDOWS / "launcher" / "claudia-start.c").read_text(encoding="utf-8")
    assert "%ls\\\\node\\\\node.exe" in source and "%ls\\\\bin\\\\%ls.mjs" in source
    assert (staged / "client" / "claudia-start.exe").is_file()
    assert (staged / "node" / "node.exe").is_file()
    for app in build.APPS:
        assert (staged / "client" / "bin" / f"{app}.mjs").is_file()


def test_the_launcher_program_is_compiled_without_a_console_and_with_wide_characters(tmp_path):
    command = build.launcher_command("gcc", tmp_path / "claudia-start.exe")
    assert command[0] == "gcc"
    assert "-mwindows" in command, "the GUI subsystem: no console of its own"
    assert "-municode" in command, "wWinMain: paths with umlauts"
    assert command[command.index("-o") + 1].endswith("claudia-start.exe")
    assert any(argument.endswith("claudia-start.c") for argument in command)
    assert "-lshell32" in command
    source = (WINDOWS / "launcher" / "claudia-start.c").read_text(encoding="utf-8")
    # what the owner asked for, as long as nothing can run it here: node without a window, its output in a log file
    assert "CREATE_NO_WINDOW" in source
    assert "launcher.log" in source and "STARTF_USESTDHANDLES" in source


def _installer_job_steps() -> dict[str, str]:
    text = (ROOT / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
    job = text[text.index("\n  installer:\n") : text.index("\n  # What a person does")]
    parts = re.split(r"^      - (?=name: )", job, flags=re.MULTILINE)[1:]
    return {part.splitlines()[0].removeprefix("name: "): part for part in parts}


def test_the_workflow_builds_the_launcher_program_checks_it_and_stages_it():
    steps = _installer_job_steps()
    built = "The launcher program hides node and keeps a log of what it prints"
    assert built in steps, "no step builds and tries claudia-start.exe"
    assert "build.py launcher" in steps[built] and "continue-on-error" not in steps[built]
    for needed in ("launcher.log", "Wait-Process", "ExitCode"):
        assert needed in steps[built], f"the step does not look at {needed}"
    names = list(steps)
    assert names.index(built) < names.index("Stage the files of the installation")
    assert "--launcher" in steps["Stage the files of the installation"]


def test_the_service_has_one_name_in_the_script_and_in_its_configuration():
    service = ET.parse(WINDOWS / "service" / "claudia-service.xml").getroot()
    assert f'#define ServiceId "{service.findtext("id")}"' in iss_text()


def test_the_service_takes_the_port_that_every_desktop_app_looks_at():
    """The desktop apps use a Claudia server they find on this port (D504): the service must be where they look."""
    service = ET.parse(WINDOWS / "service" / "claudia-service.xml").getroot()
    port = re.search(r"--port (\d+)", service.findtext("arguments")).group(1)
    shell = (ROOT / "clients" / "neutralino" / "src" / "desktop-server.ts").read_text(encoding="utf-8")
    assert f"SERVER_PORT = {port}" in shell


def test_the_service_listens_on_this_computer_only_and_does_not_stop_when_idle():
    arguments = ET.parse(WINDOWS / "service" / "claudia-service.xml").getroot().findtext("arguments")
    assert "--host 127.0.0.1" in arguments
    assert "--exit-when-idle" not in arguments


def test_the_service_component_is_not_chosen_unless_asked_for():
    text = iss_text()
    assert re.search(r'Name: "service"; [^\n]*Types: full\b', text)
    assert re.search(r'Name: "client"; [^\n]*Flags: fixed', text)


def test_the_app_id_never_changes():
    """An update finds the installation it replaces by this GUID. If it changes, every update installs a second copy."""
    assert "AppId={{6C1F2D0A-5B7E-4F0C-9A53-2D8E7B41C9A6}" in iss_text()


def test_the_uninstaller_never_deletes_a_folder_the_person_chose():
    """{app} is where the person pointed the installer: the uninstaller removes what it installed, not the folder."""
    assert not re.search(r'^Type: filesandordirs; Name: "\{app\}', iss_text(), flags=re.M)


# -------------------------------------------------------------------------------------------- the server program
def test_the_server_program_answers_the_workers_of_its_own_pool_first():
    entry = (WINDOWS / "server_entry.py").read_text(encoding="utf-8")
    assert entry.index("freeze_support()") < entry.index("from claudia_server.cli import main")


def test_the_spec_takes_every_package_of_the_workspace_by_name_not_a_list_that_goes_stale():
    spec = (WINDOWS / "claudia-server.spec").read_text(encoding="utf-8")
    assert 'glob("packages/*/src/*")' in spec


def test_the_window_step_ends_the_core_of_its_window_before_the_uninstall():
    """PROC-54: the core of a window is a `node.exe` of the installation. The advisory window step ended the launcher
    and the window but not that node, which held the files, so *Uninstall, standard* failed on both images. The step
    before it looked for that node by its path, which Windows gives in the short form: it never found it."""
    step = _install_test_steps()["A window opens, and starts the server it needs"]
    finally_part = step[step.index("finally") :]
    # found by its command line: Windows names the node of the installation by its short path (C:\PROGRA~1\CLAUDI~1\...)
    assert "Win32_Process" in finally_part and "Claudia\\run" in finally_part and "ExecutablePath" not in finally_part
    assert "claudia-server" in finally_part
