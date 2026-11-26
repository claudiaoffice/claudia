"""Puts the macOS package together (E8.5, D1625-D1629), on any system: GitHub's macOS runners do not come, so the
package is built on Linux in CI (the owner, 2026-11-26; notes/e8-5-architecture.md, part 3).

    python packaging/macos/build.py version v0.5.0
    python packaging/macos/build.py fetch python build/python.tar.gz        (and node, bomutils)
    python packaging/macos/build.py server --python build/python             the server's wheels for macOS, into it
    python packaging/macos/build.py stage --python build/python --node build/node --version 0.5.0 --out build/macos
    python packaging/macos/build.py check-signatures build/macos              every Mach-O signed (macho.py)
    python packaging/macos/build.py package --stage build/macos --mkbom build/bomutils/mkbom --out dist

What the stage holds (``--out``):

    apps/root/       the payload of the part everyone gets: the three apps, "uninstall claudia", the runtime
    apps/scripts/    its preinstall and postinstall
    service/root/    the payload of the claudia service: its LaunchDaemon and the service file (D1622)
    service/scripts/ its postinstall: the account _claudia, the shared folders, starting it
    resources/       the installer's welcome and licence pages and its words, in en.lproj and de.lproj
    Distribution     what the installer shows and installs (productbuild's distribution file)

``stage`` refuses to go on when something that an earlier step builds is missing, and says which step makes it.
"""

from __future__ import annotations

import argparse
import html
import json
import plistlib
import shutil
import subprocess
import sys
import urllib.request
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import flatpkg  # noqa: E402  (packaging/macos/flatpkg.py)
import macho  # noqa: E402  (packaging/macos/macho.py)
from shared import (  # noqa: E402  (packaging/shared.py)
    BuildError,
    Version,
    copy_tree,
    development_version,
    download,
    parse_version,
    require,
    verify_sha256,
)

APPS = ("composes", "computes", "creates")
SUITE_ICON = "suite-icon.png"
NEUTRALINO_BINARY = "neutralino-mac_arm64"
PYTHON = "3.14"
BUNDLE_PREFIX = "de.claudia-office"
SERVICE_LABEL = f"{BUNDLE_PREFIX}.server"
SERVICE_PORT = 8765
MINIMUM_MACOS = "14.0"
LANGUAGES = ("en", "de")

CLAUDIA = "/Library/Application Support/Claudia"
RUNTIME = f"{CLAUDIA}/runtime"
SHARED = f"{CLAUDIA}/shared"


def package_name(version: Version) -> str:
    """``claudia-office-0.5.0-macos-arm64.pkg``: what the release offers for download."""
    return f"claudia-office-{version.text}-macos-arm64.pkg"


def pins() -> dict:
    return json.loads((HERE / "third-party.json").read_text(encoding="utf-8"))


def check_pin(pin: dict, listing: str) -> None:
    """Refuses a pin whose SHA-256 is not in its publisher's list (``SHA256SUMS``, ``SHASUMS256.txt``) for the
    file's own name, so that a pin taken from CI's first download is the file the publisher made."""
    name = unquote(pin["url"].rsplit("/", 1)[-1])
    lines = {tuple(line.split()) for line in listing.splitlines() if line.strip()}
    if (pin["sha256"], name) not in lines and (pin["sha256"], f"*{name}") not in lines:
        raise BuildError(f"the pin of {name} ({pin['sha256']}) is not in its publisher's list")


def check_pins() -> list[str]:
    """Each pin that names its publisher's list, checked against it; the names of those checked."""
    checked = []
    for name, pin in pins().items():
        if name.startswith("_") or "checksums" not in pin:
            continue
        with urllib.request.urlopen(pin["checksums"], timeout=60) as response:  # noqa: S310 (a pinned https url)
            check_pin(pin, response.read().decode("utf-8"))
        checked.append(name)
    return checked


def fetch(name: str, target: Path) -> Path:
    """A pinned download (third-party.json), refused if it is not the file that was pinned."""
    pin = pins()[name]
    download(pin["url"], target)
    verify_sha256(target, pin["sha256"])
    return target


# ---------------------------------------------------------------------------------------------------------- server
def site_packages(python: Path) -> Path:
    return python / "lib" / f"python{PYTHON}" / "site-packages"


def export_command(requirements: Path) -> list[str]:
    """What the server needs, from the lock file, the suite's own packages as their folders."""
    return [
        "uv", "export", "--frozen", "--package", "claudia-server", "--no-dev", "--no-hashes", "--no-editable",
        "--output-file", str(requirements),
    ]  # fmt: skip


def split_requirements(exported: str) -> tuple[list[str], str]:
    """The suite's own packages (``./packages/...``) and the rest of an exported list, without its comments."""
    lines = [line.strip() for line in exported.splitlines() if line.strip() and not line.strip().startswith("#")]
    return [line for line in lines if line.startswith("./")], "".join(
        f"{line}\n" for line in lines if not line.startswith("./")
    )


def wheel_commands(local: list[str], wheels: Path) -> list[list[str]]:
    """The suite's own packages as wheels (pure Python, so the same on a Mac)."""
    return [["uv", "build", "--wheel", "--out-dir", str(wheels), path] for path in local]


def install_command(python: Path, requirements: Path, wheels: list[Path]) -> list[str]:
    """Everything, from wheels only, for macOS on Apple Silicon, into the runtime's Python: every dependency has a wheel
    for it, so nothing is compiled -- above all nothing for Linux -- and this runs on Linux (D1625)."""
    return [
        "uv", "pip", "install", "--python-platform", "aarch64-apple-darwin", "--python-version", PYTHON,
        "--only-binary", ":all:", "--target", str(site_packages(python)), "--requirement", str(requirements),
        *map(str, wheels),
    ]  # fmt: skip


def install_server(python: Path, work: Path) -> Path:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    subprocess.run(export_command(work / "exported.txt"), cwd=ROOT, check=True)
    local, others = split_requirements((work / "exported.txt").read_text(encoding="utf-8"))
    (work / "others.txt").write_text(others, encoding="utf-8")
    for command in wheel_commands(local, work / "wheels"):
        subprocess.run(command, cwd=ROOT, check=True)
    wheels = sorted((work / "wheels").glob("*.whl"))
    if len(wheels) != len(local):
        raise BuildError(f"{len(local)} of the suite's packages were to become wheels, but {len(wheels)} did")
    subprocess.run(install_command(python, work / "others.txt", wheels), cwd=ROOT, check=True)
    return site_packages(python)


# ------------------------------------------------------------------------------------------------------- the apps
def info_plist(app: str, version: Version) -> dict:
    name = f"claudia {app}"
    release = version.numeric.rsplit(".", 1)[0]  # macOS wants at most three numbers
    return {
        "CFBundleIdentifier": f"{BUNDLE_PREFIX}.{app}",
        "CFBundleName": name,
        "CFBundleDisplayName": name,
        "CFBundleExecutable": f"claudia-{app}",
        "CFBundleIconFile": f"{app}.icns",
        "CFBundlePackageType": "APPL",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleShortVersionString": release,
        "CFBundleVersion": release,
        "LSMinimumSystemVersion": MINIMUM_MACOS,
        "LSArchitecturePriority": ["arm64"],
        "NSHighResolutionCapable": True,
    }


def app_program(app: str) -> str:
    """The program of ``claudia <app>.app`` (D1626): the launcher prepares the window with the bundled node, then this
    process becomes the Neutralino inside the app, so macOS shows one icon with the app's name. What both print is
    kept in ~/Library/Logs/Claudia/<app>.log."""
    return f"""#!/bin/sh
# The program of claudia {app}.app (E8.5, D1626), written by packaging/macos/build.py.
R="{RUNTIME}"
B="$(cd "$(dirname "$0")" && pwd)"
L="$HOME/Library/Logs/Claudia"
mkdir -p "$L"
export CLAUDIA_NEUTRALINO_BIN="$B/neutralino"
"$R/node/bin/node" "$R/client/dist/launch.js" {app} --prepare >>"$L/{app}.log" 2>&1 || exit 1
exec /bin/sh "$HOME/Library/Caches/Claudia/run/{app}/window.sh" >>"$L/{app}.log" 2>&1
"""


SERVER_SCRIPT = """#!/bin/sh
# The server (E8.5, D1625): the runtime's Python, isolated from anything a person set for her own Python.
here="$(cd "$(dirname "$0")" && pwd)"
exec "$here/../python/bin/python3" -I -m claudia_server "$@"
"""


def icns(png: bytes) -> bytes:
    """A macOS icon (.icns) from one large PNG, with the sizes macOS asks for (Pillow; ``iconutil`` needs a Mac)."""
    from PIL import Image  # the build's own dependency (the server's too), not the runtime's

    out = BytesIO()
    Image.open(BytesIO(png)).convert("RGBA").save(out, "ICNS")
    return out.getvalue()


def write(path: Path, data: bytes | str, mode: int = 0o644) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)
    path.chmod(mode)
    return path


def app_bundle(applications: Path, app: str, version: Version, neutralino: Path, icon: bytes) -> None:
    contents = applications / f"claudia {app}.app" / "Contents"
    write(contents / "Info.plist", plistlib.dumps(info_plist(app, version)))
    write(contents / "MacOS" / f"claudia-{app}", app_program(app), 0o755)
    write(contents / "MacOS" / "neutralino", neutralino.read_bytes(), 0o755)
    write(contents / "Resources" / f"{app}.icns", icns(icon))


def uninstaller_bundle(applications: Path, version: Version, icon: bytes) -> None:
    contents = applications / "Utilities" / "uninstall claudia.app" / "Contents"
    info = info_plist("uninstall", version) | {
        "CFBundleName": "uninstall claudia",
        "CFBundleDisplayName": "uninstall claudia",
        "CFBundleExecutable": "uninstall-claudia",
        "CFBundleIconFile": "claudia.icns",
    }
    write(contents / "Info.plist", plistlib.dumps(info))
    write(contents / "MacOS" / "uninstall-claudia", (HERE / "uninstall-app.sh").read_text(encoding="utf-8"), 0o755)
    write(contents / "Resources" / "claudia.icns", icns(icon))


# ---------------------------------------------------------------------------------------------------- the service
def launch_daemon() -> dict:
    """The claudia service (D1627): the server under its own account, on this computer only, before anyone logs in."""
    return {
        "Label": SERVICE_LABEL,
        "ProgramArguments": [
            f"{RUNTIME}/server/claudia-server",
            "--host",
            "127.0.0.1",
            "--port",
            str(SERVICE_PORT),
            "--dir",
            f"{SHARED}/documents",
            "--state-dir",
            f"{SHARED}/state",
            "--web",
            f"{RUNTIME}/web",
            "--no-tls",  # on this computer only (--host): the apps reach it as http://127.0.0.1, as they do theirs
        ],
        "UserName": "_claudia",
        "GroupName": "_claudia",
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": "/Library/Logs/Claudia/server.log",
        "StandardErrorPath": "/Library/Logs/Claudia/server.log",
    }


def service_file() -> dict:
    """What every person's apps read to list "Shared on this computer" (D1622); root's to write."""
    return {"origin": f"http://127.0.0.1:{SERVICE_PORT}", "state": f"{SHARED}/state"}


# -------------------------------------------------------------------------------------------------- the installer
INSTALLATION_CHECK = f"""
function claudiaCanRunHere() {{
  var appleSilicon = system.sysctl('hw.optional.arm64') == 1;
  var recent = system.compareVersions(system.version.ProductVersion, '{MINIMUM_MACOS}') >= 0;
  if (appleSilicon && recent) return true;
  my.result.type = 'Fatal';
  my.result.message = system.localizedString('NEEDS_APPLE_SILICON');
  return false;
}}
"""


def distribution(version: Version, kbytes: dict[str, int] | None = None) -> str:
    """productbuild's distribution file: the title, the pages, the two parts, and the check of the Mac. ``kbytes``:
    the size of each part (``apps``, ``service``), which the installer shows; known once the package is made."""

    def ref(part: str) -> str:
        size = f' installKBytes="{kbytes[part]}"' if kbytes else ""
        version_text = html.escape(version.text)
        return f'<pkg-ref id="{BUNDLE_PREFIX}.{part}" version="{version_text}"{size} auth="root">#{part}.pkg</pkg-ref>'

    script = f"<script><![CDATA[{INSTALLATION_CHECK}]]></script>"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>claudia {html.escape(version.text)}</title>
    <welcome file="welcome.html" mime-type="text/html"/>
    <license file="license.html" mime-type="text/html"/>
    <options customize="allow" require-scripts="false" rootVolumeOnly="true" hostArchitectures="arm64,x86_64"/>
    <domains enable_localSystem="true" enable_anywhere="false" enable_currentUserHome="false"/>
    <volume-check>
        <allowed-os-versions><os-version min="{MINIMUM_MACOS}"/></allowed-os-versions>
    </volume-check>
    <installation-check script="claudiaCanRunHere()"/>
    {script}
    <choices-outline>
        <line choice="apps"/>
        <line choice="service"/>
    </choices-outline>
    <choice id="apps" title="APPS_TITLE" description="APPS_DESCRIPTION" start_selected="true" enabled="false">
        <pkg-ref id="{BUNDLE_PREFIX}.apps"/>
    </choice>
    <choice id="service" title="SERVICE_TITLE" description="SERVICE_DESCRIPTION" start_selected="false">
        <pkg-ref id="{BUNDLE_PREFIX}.service"/>
    </choice>
    {ref("apps")}
    {ref("service")}
</installer-gui-script>
"""


def license_page(text: str, language: str) -> str:
    lead = {
        "en": "claudia is free software. You may use, share and change it under these terms:",
        "de": "claudia ist freie Software. Sie dürfen sie unter diesen Bedingungen nutzen, weitergeben und ändern:",
    }[language]
    return (
        f'<!doctype html><html lang="{language}"><head><meta charset="utf-8"></head>'
        f'<body style="font-family: -apple-system, sans-serif"><p>{html.escape(lead)}</p>'
        f'<pre style="white-space: pre-wrap">{html.escape(text)}</pre></body></html>\n'
    )


# -------------------------------------------------------------------------------------------------------- staging
def stage(root: Path, out: Path, *, python: Path, node: Path, version: Version) -> Path:
    """The files of the package, laid out as the module's docstring says. ``python`` is a relocatable CPython for macOS
    on Apple Silicon with the server installed into it (``build.py server``), ``node`` an unpacked Node.js for it."""
    client = root / "clients" / "neutralino"
    web = require(root / "web" / ".output" / "public", "npm ci && npm run build, in web/")
    require(client / "dist" / "launch.js", "npm ci && npm run build:macos, in clients/neutralino/")
    require(python / "bin" / "python3", "a CPython for macOS on Apple Silicon: build.py fetch python, unpacked")
    require(site_packages(python) / "claudia_server", "build.py server --python <that Python>")
    require(node / "bin" / "node", "a Node.js for macOS on Apple Silicon: build.py fetch node, unpacked")

    if out.exists():
        shutil.rmtree(out)
    apps_root = out / "apps" / "root"
    runtime = apps_root / RUNTIME.lstrip("/")

    copy_tree(web, runtime / "web")
    shutil.copytree(python, runtime / "python", symlinks=True)
    write(runtime / "node" / "bin" / "node", (node / "bin" / "node").read_bytes(), 0o755)
    for licence in ("LICENSE", "LICENSE.txt"):
        if (node / licence).exists():
            write(runtime / "node" / "LICENSE", (node / licence).read_bytes())
            break
    write(runtime / "server" / "claudia-server", SERVER_SCRIPT, 0o755)
    write(runtime / "uninstall.sh", (HERE / "uninstall.sh").read_text(encoding="utf-8"), 0o755)
    write(runtime / "VERSION", f"{version.text}\n")

    target = runtime / "client"
    copy_tree(client / "dist", target / "dist")
    shutil.copy2(client / "package.json", target / "package.json")  # "type": "module": without it dist/*.js is not read
    write(
        target / "packaged.json", json.dumps({"web": "../web", "server": "../server/claudia-server"}, indent=2) + "\n"
    )
    applications = apps_root / "Applications"
    for app in APPS:
        source = client / "apps" / app
        built = f"npm run build:macos, in clients/neutralino/ (and `npx @neutralinojs/neu update` in apps/{app})"
        for name in ("index.html", "neutralino.config.json", "shell", "ext", "js"):
            require(source / name, built)
        neutralino = require(source / "bin" / NEUTRALINO_BINARY, built)
        (target / "apps" / app).mkdir(parents=True)
        for name in ("index.html", "neutralino.config.json", "icon.png"):
            shutil.copy2(source / name, target / "apps" / app / name)
        for name in ("shell", "ext", "js"):
            copy_tree(source / name, target / "apps" / app / name)
        large = source / "icon@4x.png"
        app_bundle(
            applications, app, version, neutralino, (large if large.exists() else source / "icon.png").read_bytes()
        )
    uninstaller_bundle(
        applications, version, require(client / SUITE_ICON, "clients/neutralino/suite-icon.png").read_bytes()
    )

    for component, scripts in (("apps", ("preinstall", "postinstall")), ("service", ("postinstall",))):
        for script in scripts:
            text = (HERE / "scripts" / component / script).read_text(encoding="utf-8")
            write(out / component / "scripts" / script, text, 0o755)

    service_root = out / "service" / "root"
    write(service_root / "Library" / "LaunchDaemons" / f"{SERVICE_LABEL}.plist", plistlib.dumps(launch_daemon()))
    write(service_root / CLAUDIA.lstrip("/") / "service.json", json.dumps(service_file(), indent=2) + "\n")

    licence = (root / "LICENSE").read_text(encoding="utf-8")
    for language in LANGUAGES:
        lproj = out / "resources" / f"{language}.lproj"
        copy_tree(HERE / "resources" / f"{language}.lproj", lproj)
        write(lproj / "license.html", license_page(licence, language))
    write(out / "Distribution", distribution(version))
    return out


# -------------------------------------------------------------------------------------------------------- package
PARTS = {"apps": ("preinstall", "postinstall"), "service": ("postinstall",)}


def check_signatures(stage_dir: Path) -> int:
    """How many Mach-O files the package holds; refused if one has no signature (macho.py, the owner's Q4)."""
    missing = [
        str(part / "root" / path)
        for part in (stage_dir / name for name in PARTS)
        for path in macho.unsigned(part / "root")
    ]
    if missing:
        raise BuildError(
            "these programs or libraries have no signed arm64 slice, which Apple Silicon needs to run them: "
            + ", ".join(missing)
            + ". Sign them ad-hoc (rcodesign sign) or take a build that has one."
        )
    return sum(macho.count(stage_dir / name / "root") for name in PARTS)


def _folder_members(folder: Path, prefix: str) -> list[tuple[str, bytes | None]]:
    found: list[tuple[str, bytes | None]] = [(prefix, None)]
    for path in sorted(folder.rglob("*"), key=lambda p: p.relative_to(folder).as_posix()):
        name = f"{prefix}/{path.relative_to(folder).as_posix()}"
        found.append((name, None) if path.is_dir() else (name, path.read_bytes()))
    return found


def package(stage_dir: Path, mkbom: Path, out: Path, version: Version, mtime: int = 0) -> Path:
    """The package of a stage: each part's payload, scripts, Bom (bomutils' ``mkbom``) and PackageInfo, the
    distribution file with the parts' sizes, and the installer's pages, in one xar archive (flatpkg.py). ``mtime``: the
    time the payload's files get (the commit's), so that one commit gives one package."""
    check_signatures(stage_dir)
    sizes: dict[str, int] = {}
    parts: list[tuple[str, bytes | None]] = []
    work = stage_dir / "work"
    work.mkdir(exist_ok=True)
    for name, scripts in PARTS.items():
        root = stage_dir / name / "root"
        files, sizes[name] = flatpkg.count(root)
        bom, listed = work / f"{name}.bom", work / f"{name}.bom.txt"
        listed.write_text(flatpkg.bom_listing(root), encoding="utf-8")
        subprocess.run([str(mkbom), "-i", str(listed), str(bom)], check=True)
        info = flatpkg.package_info(
            f"{BUNDLE_PREFIX}.{name}", version.text, files=files, kbytes=sizes[name], scripts=scripts
        )
        parts += [
            (f"{name}.pkg", None),
            (f"{name}.pkg/Bom", bom.read_bytes()),
            (f"{name}.pkg/Payload", flatpkg.payload(root, mtime)),
            (f"{name}.pkg/Scripts", flatpkg.payload(stage_dir / name / "scripts", mtime)),
            (f"{name}.pkg/PackageInfo", info),
        ]
    archive = flatpkg.xar(
        [
            ("Distribution", distribution(version, sizes).encode("utf-8")),
            *_folder_members(stage_dir / "resources", "Resources"),
            *parts,
        ]
    )
    out.mkdir(parents=True, exist_ok=True)
    target = out / package_name(version)
    target.write_bytes(archive)
    return target


# ------------------------------------------------------------------------------------------------------------ cli
def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    version = commands.add_parser("version", help="print the package's version for a tag or a development build")
    version.add_argument("tag", help="v1.2.3, or the last release (0.3.0) with --commit for a build that is no release")
    version.add_argument("--build", type=int, default=0)
    version.add_argument("--commit")
    version.add_argument("--field", choices=("text", "numeric", "name"), default="text")

    commands.add_parser("check-pins", help="check the pins against their publishers' lists")

    listed = commands.add_parser("list-payload", help="print a part's payload as lsbom prints its Bom")
    listed.add_argument("payload", type=Path)

    fetched = commands.add_parser("fetch", help="download a pinned file (third-party.json)")
    fetched.add_argument("name", choices=("python", "node", "bomutils"))
    fetched.add_argument("target", type=Path)

    server = commands.add_parser("server", help="install the server for macOS into the runtime's Python")
    server.add_argument("--python", type=Path, required=True)
    server.add_argument("--work", type=Path, default=ROOT / "build" / "macos-server")

    staged = commands.add_parser("stage", help="lay out the files of the package")
    staged.add_argument("--python", type=Path, required=True)
    staged.add_argument("--node", type=Path, required=True)
    staged.add_argument("--version", required=True, help="the text of the version (build.py version prints it)")
    staged.add_argument("--out", type=Path, default=ROOT / "build" / "macos")

    signatures = commands.add_parser("check-signatures", help="refuse a stage with a program that has no signature")
    signatures.add_argument("stage", type=Path)

    packaged = commands.add_parser("package", help="make the .pkg of a stage")
    packaged.add_argument("--stage", type=Path, default=ROOT / "build" / "macos")
    packaged.add_argument("--mkbom", type=Path, required=True, help="bomutils' mkbom (built from the pinned source)")
    packaged.add_argument("--version", required=True)
    packaged.add_argument("--time", type=int, default=0, help="the time of the payload's files (the commit's)")
    packaged.add_argument("--out", type=Path, default=ROOT / "dist")
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
            print(package_name(result) if arguments.field == "name" else getattr(result, arguments.field))
        elif arguments.command == "list-payload":
            for name, mode in flatpkg.listing(arguments.payload.read_bytes()):
                print(f"{name}\t{mode}")
        elif arguments.command == "check-pins":
            print("pins in their publishers' lists: " + ", ".join(check_pins()))
        elif arguments.command == "fetch":
            print(fetch(arguments.name, arguments.target))
        elif arguments.command == "server":
            print(install_server(arguments.python, arguments.work))
        elif arguments.command == "stage":
            version = parse_version(arguments.version)
            print(stage(ROOT, arguments.out, python=arguments.python, node=arguments.node, version=version))
        elif arguments.command == "check-signatures":
            print(f"{check_signatures(arguments.stage)} programs and libraries, each with its signature")
        elif arguments.command == "package":
            version = parse_version(arguments.version)
            print(package(arguments.stage, arguments.mkbom, arguments.out, version, arguments.time))
    except (BuildError, subprocess.CalledProcessError, OSError) as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
