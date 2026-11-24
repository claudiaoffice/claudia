"""Puts the Windows installer together (D740-D745): stages the files of an install and compiles ``claudia.iss``.

The steps that need a toolchain (npm, PyInstaller, ``neu update``, Inno Setup) are steps of the workflow
(``.github/workflows/windows.yml``) or are run by hand as ``packaging/windows/README.md`` lists them; this script does
what is plain file work and is tested on any system (``tests/test_windows_packaging.py``):

    python packaging/windows/build.py version v0.4.0 --build 17
    python packaging/windows/build.py launcher --out build\\claudia-start.exe
    python packaging/windows/build.py stage --node C:\\node --winsw WinSW-x64.exe --out build\\stage \\
        --launcher build\\claudia-start.exe
    python packaging/windows/build.py installer --stage build\\stage --version 0.4.0 --out dist

``stage`` refuses to go on when something that an earlier step builds is missing, and says which step makes it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APPS = ("composes", "computes", "creates")
# The icon of the suite as a whole (three dots), in clients/neutralino: what the setup and Programs show (UX-79).
SUITE_ICON = "suite-icon.png"
NEUTRALINO_BINARY = "neutralino-win_x64.exe"
LAUNCHER_PROGRAM = "claudia-start.exe"
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+.]?([0-9A-Za-z.+-]+))?$")


class BuildError(Exception):
    """Something the person building has to do first, or a file that is not what it was pinned to be."""


@dataclass(frozen=True)
class Version:
    """What the installer calls itself: the text a person reads and the four numbers of the file's version resource."""

    text: str
    numeric: str


def parse_version(tag: str, build: int = 0) -> Version:
    """``v1.2.3`` (a release tag) is version 1.2.3; ``1.2.3-rc.1`` keeps its suffix in the text. ``build`` is the
    fourth number (the workflow's run number), which tells builds of one version apart.

    >>> parse_version("v1.2.3", 7)
    Version(text='1.2.3', numeric='1.2.3.7')
    """
    found = VERSION_PATTERN.match(tag.strip())
    if found is None:
        raise BuildError(f"'{tag}' is not a version: expected 1.2.3 or v1.2.3, with an optional suffix such as -rc.1")
    major, minor, patch, suffix = found.groups()
    text = f"{major}.{minor}.{patch}" + (f"-{suffix.lstrip('-+.')}" if suffix else "")
    return Version(text=text, numeric=f"{major}.{minor}.{patch}.{build}")


def development_version(base: str, build: int, commit: str) -> Version:
    """A build that is no release (a pull request, a push to main): sorts before the release it leads to, and says which
    commit it is. ``base`` is the last released version, ``0.3.0``.

    >>> development_version("0.3.0", 42, "1a2b3c4d5e").text
    '0.3.0-dev.42+1a2b3c4'
    """
    release = parse_version(base, build)
    return Version(text=f"{release.text}-dev.{build}+{commit[:7]}", numeric=release.numeric)


def icon_from_png(png: bytes) -> bytes:
    """A Windows icon (.ico) that holds one PNG, which Windows has read since Vista. Side 256 is written as 0, as the
    format wants; other sizes are written as they are.

    >>> icon_from_png(b"\\x89PNG\\r\\n\\x1a\\n" + bytes(8) + struct.pack(">II", 256, 256))[:6]
    b'\\x00\\x00\\x01\\x00\\x01\\x00'
    """
    if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) < 24:
        raise BuildError("the icon is not a PNG file")
    width, height = struct.unpack(">II", png[16:24])
    if not (0 < width <= 256 and 0 < height <= 256):
        raise BuildError(f"the icon is {width}x{height}; an .ico holds at most 256x256")
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", width % 256, height % 256, 0, 0, 1, 32, len(png), len(header) + 16)
    return header + entry + png


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sha256(path: Path, expected: str) -> None:
    found = sha256_of(path)
    if found != expected.lower():
        raise BuildError(f"{path.name} is not the file that was pinned: its SHA-256 is {found}, not {expected}")


def pins() -> dict:
    return json.loads((HERE / "third-party.json").read_text(encoding="utf-8"))


def download(url: str, target: Path) -> Path:
    """The file at ``url``, written to ``target``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as out:  # noqa: S310 (a pinned https url)
        shutil.copyfileobj(response, out)
    return target


def fetch_winsw(target: Path) -> Path:
    """WinSW at the pinned version, refused if it is not the file that was pinned."""
    pin = pins()["winsw"]
    download(pin["url"], target)
    verify_sha256(target, pin["sha256"])
    return target


def require(path: Path, step: str) -> Path:
    if not path.exists():
        raise BuildError(f"{path} is missing. It is made by: {step}")
    return path


def copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, dirs_exist_ok=True)


def stage(root: Path, out: Path, node: Path, winsw: Path, launcher: Path, webview2: Path | None = None) -> Path:
    """The files of an install, laid out as ``claudia.iss`` installs them. ``root`` is the repository, ``node`` the
    folder of a Node.js (``node.exe`` and its ``LICENSE``), ``winsw`` WinSW's executable, ``launcher`` the program
    the shortcuts start (``build.py launcher``).

    What has to be built before: the web frontend (``npm run build`` in web/), the client (``npm run build:windows`` in
    clients/neutralino, and ``npx @neutralinojs/neu update`` in each of its apps) and the server (``pyinstaller``).
    """
    client = root / "clients" / "neutralino"
    web = require(root / "web" / ".output" / "public", "npm ci && npm run build, in web/")
    server = require(root / "dist" / "claudia-server", "pyinstaller packaging/windows/claudia-server.spec")
    require(server / "claudia-server.exe", "pyinstaller packaging/windows/claudia-server.spec (on Windows)")
    require(client / "dist" / "launch.js", "npm ci && npm run build:windows, in clients/neutralino/")
    require(node / "node.exe", "a Node.js for Windows: pass its folder with --node")
    require(winsw, "pass WinSW's executable with --winsw (build.py fetch-winsw gets the pinned one)")
    require(launcher, "build.py launcher, then pass its output with --launcher")

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    copy_tree(web, out / "web")
    copy_tree(server, out / "server")

    (out / "node").mkdir()
    shutil.copy2(node / "node.exe", out / "node" / "node.exe")
    for licence in ("LICENSE", "LICENSE.txt"):
        if (node / licence).exists():
            shutil.copy2(node / licence, out / "node" / "LICENSE-node.txt")
            break

    target = out / "client"
    (target / "apps").mkdir(parents=True)
    copy_tree(client / "bin", target / "bin")
    copy_tree(client / "dist", target / "dist")
    shutil.copy2(launcher, target / LAUNCHER_PROGRAM)  # what the shortcuts start: node without a window (D750)
    shutil.copy2(client / "package.json", target / "package.json")  # "type": "module": without it dist/*.js is not read
    for app in APPS:
        source = client / "apps" / app
        built = f"npm run build:windows, in clients/neutralino/ (and `npx @neutralinojs/neu update` in apps/{app})"
        for name in ("index.html", "neutralino.config.json", "icon.png", "shell", "ext", "js", "bin"):
            require(source / name, built)
        require(source / "bin" / NEUTRALINO_BINARY, built)
        app_target = target / "apps" / app
        app_target.mkdir()
        for name in ("index.html", "neutralino.config.json", "icon.png"):
            shutil.copy2(source / name, app_target / name)
        for name in ("shell", "ext", "js", "bin"):
            copy_tree(source / name, app_target / name)
    # Where the installer put what the client needs besides itself (src/packaged.ts), relative to the client's folder.
    (target / "packaged.json").write_text(
        json.dumps({"web": "../web", "server": "../server/claudia-server.exe"}, indent=2) + "\n", encoding="utf-8"
    )

    (out / "icons").mkdir()
    for app in APPS:
        icon = icon_from_png((client / "apps" / app / "icon.png").read_bytes())
        (out / "icons" / f"{app}.ico").write_bytes(icon)
    suite = icon_from_png(
        require(client / SUITE_ICON, "the suite icon, clients/neutralino/suite-icon.png").read_bytes()
    )
    (out / "icons" / "claudia.ico").write_bytes(suite)

    (out / "service").mkdir()
    shutil.copy2(winsw, out / "service" / "claudia-service.exe")  # WinSW reads the file with the name of its own exe
    shutil.copy2(HERE / "service" / "claudia-service.xml", out / "service" / "claudia-service.xml")

    shutil.copy2(root / "LICENSE", out / "LICENSE.txt")
    shutil.copy2(root / "CHANGELOG.md", out / "CHANGELOG.md")
    (out / "prerequisites").mkdir()
    if webview2 is not None:
        shutil.copy2(webview2, out / "prerequisites" / "MicrosoftEdgeWebview2Setup.exe")
    return out


def launcher_command(compiler: str, out: Path) -> list[str]:
    """The command line that compiles the program the shortcuts start (``launcher/claudia-start.c``, UX-78, D750): of
    the GUI subsystem, so that it has no console window, with wide-character entry for paths with umlauts."""
    return [
        compiler,
        "-O2",
        "-Wall",
        "-municode",
        "-mwindows",
        "-o",
        str(out),
        str(HERE / "launcher" / "claudia-start.c"),
        "-lshell32",
        "-luser32",
    ]


def build_launcher(out: Path, compiler: str = "gcc") -> Path:
    """``claudia-start.exe``, compiled with MinGW's ``gcc`` (on the workflow's runners, or ``--cc`` another one)."""
    if shutil.which(compiler) is None:
        raise BuildError(f"{compiler} is not installed: MinGW-w64 (`choco install mingw`), or pass another with --cc")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(launcher_command(compiler, out), check=True)
    return require(out, f"{compiler} (it said why it did not)")


def find_iscc() -> str:
    found = shutil.which("iscc")
    if found:
        return found
    for candidate in (
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    raise BuildError(
        "Inno Setup 6 is not installed (ISCC.exe): https://jrsoftware.org/isinfo.php, or `choco install innosetup`"
    )


def installer_command(iscc: str, stage_dir: Path, version: Version, out: Path) -> list[str]:
    """The command line that compiles the installer; the options are those ``claudia.iss`` asks for with #error."""
    return [
        iscc,
        f"/DAppVersion={version.text}",
        f"/DNumericVersion={version.numeric}",
        f"/DStageDir={stage_dir.resolve()}",
        f"/DOutputDir={out.resolve()}",
        str(HERE / "claudia.iss"),
    ]


def build_installer(stage_dir: Path, version: Version, out: Path) -> Path:
    bootstrapper = stage_dir / "prerequisites" / "MicrosoftEdgeWebview2Setup.exe"
    require(bootstrapper, "build.py fetch-webview2, then stage --webview2")
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(installer_command(find_iscc(), stage_dir, version, out), check=True)
    built = out / f"claudia-office-{version.text}-windows-x64.exe"
    return require(built, "Inno Setup (it said why it did not)")


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    version = commands.add_parser("version", help="print the installer's version for a tag or a development build")
    version.add_argument("tag", help="v1.2.3, or the last release (0.3.0) with --commit for a build that is no release")
    version.add_argument("--build", type=int, default=0, help="the build number (the workflow's run number)")
    version.add_argument("--commit", help="the commit of a development build")
    version.add_argument("--field", choices=("text", "numeric"), default="text")

    staged = commands.add_parser("stage", help="lay out the files of an install")
    staged.add_argument("--node", type=Path, required=True, help="the folder of a Node.js for Windows")
    staged.add_argument("--winsw", type=Path, required=True)
    staged.add_argument(
        "--launcher", type=Path, required=True, help="claudia-start.exe (the launcher command makes it)"
    )
    staged.add_argument("--webview2", type=Path)
    staged.add_argument("--out", type=Path, default=ROOT / "build" / "windows" / "stage")

    installer = commands.add_parser("installer", help="compile the installer from a stage")
    installer.add_argument("--stage", type=Path, default=ROOT / "build" / "windows" / "stage")
    installer.add_argument("--version", required=True, help="the text of the version (build.py version prints it)")
    installer.add_argument("--numeric", default="0.0.0.0")
    installer.add_argument("--out", type=Path, default=ROOT / "dist")

    launcher = commands.add_parser("launcher", help="compile the program the shortcuts start (needs MinGW's gcc)")
    launcher.add_argument("--out", type=Path, default=ROOT / "build" / "windows" / "claudia-start.exe")
    launcher.add_argument("--cc", default="gcc", help="the C compiler: MinGW-w64's gcc, or a cross-compiler")

    downloads = (("fetch-winsw", "download the pinned WinSW"), ("fetch-webview2", "download Microsoft's bootstrapper"))
    for name, text in downloads:
        fetch = commands.add_parser(name, help=text)
        fetch.add_argument("target", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    arguments = _arguments(argv)
    try:
        if arguments.command == "version":
            result = (
                development_version(arguments.tag, arguments.build, arguments.commit)
                if arguments.commit
                else parse_version(arguments.tag, arguments.build)
            )
            print(getattr(result, arguments.field))
        elif arguments.command == "stage":
            print(stage(ROOT, arguments.out, arguments.node, arguments.winsw, arguments.launcher, arguments.webview2))
        elif arguments.command == "launcher":
            print(build_launcher(arguments.out, arguments.cc))
        elif arguments.command == "installer":
            print(build_installer(arguments.stage, Version(arguments.version, arguments.numeric), arguments.out))
        elif arguments.command == "fetch-winsw":
            print(fetch_winsw(arguments.target))
        elif arguments.command == "fetch-webview2":
            print(download(pins()["webview2"]["url"], arguments.target))
    except (BuildError, subprocess.CalledProcessError, OSError) as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
