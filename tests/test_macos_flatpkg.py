"""The flat package's formats, written in Python because the package is built on Linux (E8.5, the owner's Q3 (c),
2026-11-26): the payload (cpio "odc", gzipped) and the xar archive around everything. Each is read back here by
libarchive's ``bsdtar``, a reader that knows nothing of this code; the xar header and the checksum of its table of
contents are checked by hand. The Bom comes from bomutils' ``mkbom`` and is CI's to check.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import shutil
import stat
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the macOS package is built on Linux: POSIX file modes, /bin/sh"
)

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("macos_flatpkg", ROOT / "packaging" / "macos" / "flatpkg.py")
flatpkg = importlib.util.module_from_spec(SPEC)
sys.modules["macos_flatpkg"] = flatpkg
SPEC.loader.exec_module(flatpkg)

needs_bsdtar = pytest.mark.skipif(shutil.which("bsdtar") is None, reason="libarchive's bsdtar is not installed")


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "root"
    app = root / "Applications" / "claudia composes.app" / "Contents" / "MacOS"
    app.mkdir(parents=True)
    (app / "claudia-composes").write_text("#!/bin/sh\n", encoding="utf-8")
    (app / "claudia-composes").chmod(0o755)
    python = root / "Library" / "Application Support" / "Claudia" / "runtime" / "python" / "bin"
    python.mkdir(parents=True)
    (python / "python3.14").write_bytes(b"\xcf\xfa\xed\xfe" + bytes(100))
    (python / "python3.14").chmod(0o755)
    (python / "python3").symlink_to("python3.14")
    (root / "Library" / "Application Support" / "Claudia" / "VERSION").write_text("0.5.0\n", encoding="utf-8")
    empty = root / "Library" / "Logs"
    empty.mkdir(parents=True)
    return root


def unpack(archive: Path, into: Path) -> Path:
    into.mkdir(parents=True, exist_ok=True)
    subprocess.run(["bsdtar", "-xpf", str(archive), "-C", str(into)], check=True)
    return into


def listing(root: Path) -> dict[str, tuple[str, int, bytes | str]]:
    """Each path under ``root``: its kind, mode and contents (a symlink's target)."""
    found = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            found[relative] = ("link", 0, str(path.readlink()))
        elif path.is_dir():
            found[relative] = ("dir", stat.S_IMODE(path.stat().st_mode), b"")
        else:
            found[relative] = ("file", stat.S_IMODE(path.stat().st_mode), path.read_bytes())
    return found


# --------------------------------------------------------------------------------------------------------- payload
@needs_bsdtar
def test_the_payload_holds_every_file_folder_and_link_with_its_mode(tree, tmp_path):
    (tree / "Applications").chmod(0o775)  # as every Mac has it, and so as the payload lists it
    payload = tmp_path / "Payload"
    payload.write_bytes(flatpkg.payload(tree))
    assert listing(unpack(payload, tmp_path / "out")) == listing(tree)


def test_the_payload_is_gzipped_odc_cpio_owned_by_root_with_dot_slash_paths(tree):
    data = gzip.decompress(flatpkg.payload(tree))
    assert data[:6] == b"070707"
    names, uids, gids = [], set(), {}
    offset = 0
    while True:
        header = data[offset : offset + 76]
        uid, gid = int(header[24:30], 8), int(header[30:36], 8)
        name_size, file_size = int(header[59:65], 8), int(header[65:76], 8)
        name = data[offset + 76 : offset + 76 + name_size - 1].decode()
        offset += 76 + name_size + file_size
        if name == "TRAILER!!!":
            break
        names.append(name)
        uids.add(uid)
        gids[name] = gid
    assert names[0] == "."
    assert all(n == "." or n.startswith("./") for n in names)
    assert "./Library/Application Support/Claudia/runtime/python/bin/python3" in names
    assert uids == {0}
    assert {name for name, gid in gids.items() if gid != 0} == {"./Applications"}  # admin, as on every Mac


def test_the_payload_is_the_same_for_the_same_files(tree):
    """No time or order of the building machine in it: two builds of one commit give one package."""
    assert flatpkg.payload(tree) == flatpkg.payload(tree)


def test_the_size_of_a_payload_is_counted_as_macos_installer_shows_it(tree):
    files, kbytes = flatpkg.count(tree)
    assert files == len(list(tree.rglob("*"))) + 1  # and the root folder itself
    assert kbytes >= 1


# ------------------------------------------------------------------------------------------------------------- xar
def members():
    return [
        ("Distribution", b"<installer-gui-script/>"),
        ("Resources", None),
        ("Resources/de.lproj", None),
        ("Resources/de.lproj/welcome.html", "<p>Willkommen ä</p>".encode()),
        ("apps.pkg", None),
        ("apps.pkg/PackageInfo", b"<pkg-info/>"),
        ("apps.pkg/Payload", bytes(range(256)) * 50),
    ]


@needs_bsdtar
def test_the_xar_archive_holds_every_member_as_written(tmp_path):
    archive = tmp_path / "claudia.pkg"
    archive.write_bytes(flatpkg.xar(members()))
    out = unpack(archive, tmp_path / "out")
    for name, data in members():
        if data is None:
            assert (out / name).is_dir(), name
        else:
            assert (out / name).read_bytes() == data, name


def test_the_xar_header_and_the_checksum_of_its_table_of_contents():
    data = flatpkg.xar(members())
    magic, header_size, version, toc_compressed, toc_size, algorithm = struct.unpack(">4sHHQQI", data[:28])
    assert (magic, header_size, version, algorithm) == (b"xar!", 28, 1, 1)  # 1: SHA-1
    compressed = data[28 : 28 + toc_compressed]
    toc = zlib.decompress(compressed)
    assert len(toc) == toc_size
    heap = data[28 + toc_compressed :]
    assert heap[:20] == hashlib.sha1(compressed).digest()  # noqa: S324 (the format's own checksum)
    root = ET.fromstring(toc)
    assert root.find("toc/checksum").get("style") == "sha1"
    assert root.findtext("toc/checksum/offset") == "0" and root.findtext("toc/checksum/size") == "20"


def test_each_member_carries_its_checksums_and_its_place_in_the_heap():
    data = flatpkg.xar(members())
    _, _, _, toc_compressed, _, _ = struct.unpack(">4sHHQQI", data[:28])
    heap = data[28 + toc_compressed :]
    toc = ET.fromstring(zlib.decompress(data[28 : 28 + toc_compressed]))
    payload = next(f for f in toc.iter("file") if f.findtext("name") == "Payload")
    offset, length = int(payload.findtext("data/offset")), int(payload.findtext("data/length"))
    stored = heap[offset : offset + length]
    assert stored == bytes(range(256)) * 50
    assert payload.findtext("data/extracted-checksum") == hashlib.sha1(stored).hexdigest()  # noqa: S324
    assert payload.find("data/encoding").get("style") == "application/octet-stream"


# ----------------------------------------------------------------------------------------------------- PackageInfo
def test_package_info_names_the_part_its_scripts_and_its_size():
    info = ET.fromstring(
        flatpkg.package_info(
            "de.claudia-office.apps", "0.5.0", files=12, kbytes=3400, scripts=("preinstall", "postinstall")
        )
    )
    assert info.get("identifier") == "de.claudia-office.apps" and info.get("version") == "0.5.0"
    assert info.get("install-location") == "/" and info.get("auth") == "root"
    assert info.get("relocatable") == "false", "an app found elsewhere on the Mac must not take the update"
    assert info.find("payload").get("numberOfFiles") == "12" and info.find("payload").get("installKBytes") == "3400"
    assert [s.get("file") for s in info.find("scripts")] == ["./preinstall", "./postinstall"]
    assert [s.tag for s in info.find("scripts")] == ["preinstall", "postinstall"]


def test_a_payload_is_listed_with_paths_and_modes_as_lsbom_lists_a_bom(tree):
    """CI compares the two: what the Bom says macOS installed is what the payload installs."""
    found = {name: mode for name, mode, _owner in flatpkg.listing(flatpkg.payload(tree))}
    assert found["."] == "40755"
    assert found["./Applications/claudia composes.app/Contents/MacOS/claudia-composes"] == "100755"
    assert found["./Library/Application Support/Claudia/VERSION"] == "100644"
    link = (tree / "Library" / "Application Support" / "Claudia" / "runtime" / "python" / "bin" / "python3").lstat()
    assert found["./Library/Application Support/Claudia/runtime/python/bin/python3"] == f"{link.st_mode:o}"
    assert len(found) == len(list(tree.rglob("*"))) + 1


# ------------------------------------------------------------------------------------------------------------- Bom
@pytest.mark.parametrize("data", [b"", b"hi\n", bytes(range(256)) * 300, b"x" * 70000])
def test_the_checksum_is_posix_cksum_as_bomutils_writes_it(data):
    expected = int(subprocess.run(["cksum"], input=data, capture_output=True, check=True).stdout.split()[0])
    assert flatpkg.cksum(data) == expected


def test_the_bom_list_names_every_path_of_the_payload_also_hidden_ones(tree):
    """mkbom reading a folder leaves out names that start with a dot (python-docx's `.rels`, fastapi's `.agents`):
    the Bom is made from this list instead, as lsbom prints a Bom."""
    (tree / "Library" / ".hidden").mkdir()
    (tree / "Library" / ".hidden" / ".rels").write_bytes(b"hi\n")
    lines = flatpkg.bom_listing(tree).splitlines()
    assert lines[0] == ".\t40755\t0/0"
    assert "./Library/.hidden\t40755\t0/0" in lines
    assert f"./Library/.hidden/.rels\t100644\t0/0\t3\t{flatpkg.cksum(b'hi' + bytes([10]))}" in lines
    link = (tree / "Library" / "Application Support" / "Claudia" / "runtime" / "python" / "bin" / "python3").lstat()
    target = b"python3.14"
    assert (
        f"./Library/Application Support/Claudia/runtime/python/bin/python3\t{link.st_mode:o}\t0/0\t{len(target)}"
        f"\t{flatpkg.cksum(target)}\tpython3.14"
    ) in lines
    assert [line.split("\t")[:3] for line in lines] == [list(entry) for entry in flatpkg.listing(flatpkg.payload(tree))]


def test_a_link_whose_target_has_whitespace_is_refused_for_the_bom(tree):
    (tree / "Library" / "odd").symlink_to("a target")
    with pytest.raises(ValueError, match="a target"):
        flatpkg.bom_listing(tree)


# ----------------------------------------------------------------------------------------------- the Mac's folders
def test_the_macs_own_folders_keep_their_owners_and_modes(tree):
    """/Applications is root:admin 0775 on every Mac: a payload that says root:wheel 0755 would take from
    administrators the right to put apps there. The folders the Mac has already are listed as the Mac has them."""
    entries = {name: (mode, owner) for name, mode, owner in flatpkg.listing(flatpkg.payload(tree))}
    assert entries["./Applications"] == ("40775", "0/80")
    assert entries["./Library"] == ("40755", "0/0")
    assert entries["./Library/Application Support"] == ("40755", "0/0")
    assert entries["./Applications/claudia composes.app"] == ("40755", "0/0")
    bom = {line.split("\t")[0]: tuple(line.split("\t")[1:3]) for line in flatpkg.bom_listing(tree).splitlines()}
    assert bom["./Applications"] == ("40775", "0/80")


def test_installing_does_not_change_the_rights_of_what_is_there_already():
    info = ET.fromstring(flatpkg.package_info("de.claudia-office.apps", "0.5.0", files=1, kbytes=1, scripts=()))
    assert info.get("overwrite-permissions") == "false"
