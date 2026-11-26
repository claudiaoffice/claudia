"""The formats of a flat macOS package, written in Python, so the package is built on Linux (E8.5, D1629; the owner's
Q3 (c), 2026-11-26). What ``pkgbuild`` and ``productbuild`` write on a Mac:

* a part's **Payload** and **Scripts**: a cpio archive of the "odc" kind (the portable one, headers in octal), gzipped,
  every path relative to the install location (``./Applications/...``), everything owned by root;
* a part's **PackageInfo**: its identifier, version, size and scripts (``package_info``);
* the **xar** archive that holds the distribution file, the installer's pages and the parts (``xar``): a header, the
  table of contents as zlib-compressed XML, then the heap with the SHA-1 of that table first and the members' data.

A part's **Bom** (the list of files macOS Installer keeps as the receipt) is made by bomutils' ``mkbom``, built in CI,
from a list written here (``bom_listing``, as ``lsbom`` prints a Bom): from a folder, mkbom leaves out the names that
start with a dot.
Nothing here depends on the time or the order of the machine that builds: one commit gives one package.
"""

from __future__ import annotations

import gzip
import hashlib
import math
import os
import stat
import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

ROOT_UID = 0
ROOT_GID = 0  # wheel
TRAILER = "TRAILER!!!"


def _entries(root: Path) -> list[tuple[str, Path]]:
    """``.`` and every path under ``root`` as ``./relative``; a folder comes before what is in it."""
    paths = sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())
    return [(".", root), *((f"./{p.relative_to(root).as_posix()}", p) for p in paths)]


def _odc_header(name: bytes, mode: int, inode: int, size: int, mtime: int) -> bytes:
    nlink = 2 if stat.S_ISDIR(mode) else 1
    fields = (
        "070707",
        f"{0:06o}",  # device
        f"{inode:06o}",
        f"{mode:06o}",
        f"{ROOT_UID:06o}",
        f"{ROOT_GID:06o}",
        f"{nlink:06o}",
        f"{0:06o}",  # rdev
        f"{mtime:011o}",
        f"{len(name) + 1:06o}",
        f"{size:011o}",
    )
    return "".join(fields).encode("ascii")


def cpio(root: Path, mtime: int = 0) -> bytes:
    """Every folder, file and symbolic link under ``root``, with its mode, owned by root, as an odc cpio archive."""
    out = bytearray()
    for inode, (name, path) in enumerate(_entries(root), start=1):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            data = os.readlink(path).encode("utf-8")
            mode = stat.S_IFLNK | stat.S_IMODE(info.st_mode)  # as mkbom records it in the Bom
        elif stat.S_ISDIR(info.st_mode):
            data = b""
            mode = stat.S_IFDIR | stat.S_IMODE(info.st_mode)
        else:
            data = path.read_bytes()
            mode = stat.S_IFREG | stat.S_IMODE(info.st_mode)
        encoded = name.encode("utf-8")
        out += _odc_header(encoded, mode, inode, len(data), mtime) + encoded + b"\0" + data
    out += _odc_header(TRAILER.encode("ascii"), 0, 0, 0, 0) + TRAILER.encode("ascii") + b"\0"
    return bytes(out)


def payload(root: Path, mtime: int = 0) -> bytes:
    """A part's Payload (or Scripts): the cpio archive of ``root``, gzipped without a time of its own."""
    return gzip.compress(cpio(root, mtime), compresslevel=9, mtime=0)


def listing(payload_data: bytes) -> list[tuple[str, str]]:
    """The paths of a payload with their modes in octal, as bomutils' ``lsbom`` prints a Bom (``./a/f  100644``)."""
    data = gzip.decompress(payload_data)
    found, offset = [], 0
    while True:
        header = data[offset : offset + 76]
        mode, name_size, size = int(header[18:24], 8), int(header[59:65], 8), int(header[65:76], 8)
        name = data[offset + 76 : offset + 76 + name_size - 1].decode("utf-8")
        offset += 76 + name_size + size
        if name == TRAILER:
            return found
        found.append((name, f"{mode:o}"))


def _crc_table() -> list[int]:
    table = []
    for byte in range(256):
        crc = byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) if crc & 0x80000000 else (crc << 1)
        table.append(crc & 0xFFFFFFFF)
    return table


_CRC = _crc_table()


def cksum(data: bytes) -> int:
    """POSIX ``cksum``: the CRC-32 that a Bom keeps of each file (and of a link's target), as bomutils computes it."""
    crc = 0
    for byte in data:
        crc = _CRC[byte ^ (crc >> 24)] ^ ((crc << 8) & 0xFFFFFFFF)
    length = len(data)
    while length:
        crc = _CRC[(length & 0xFF) ^ (crc >> 24)] ^ ((crc << 8) & 0xFFFFFFFF)
        length >>= 8
    return crc ^ 0xFFFFFFFF


def bom_listing(root: Path) -> str:
    """Every path that the payload of ``root`` installs, as ``lsbom`` prints a Bom and ``mkbom -i`` reads it: the
    path, the mode in octal, ``uid/gid``, and for a file or link its size and checksum (and a link's target)."""
    lines = []
    for name, path in _entries(root):
        info = path.lstat()
        mode = f"{info.st_mode:o}"
        if stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
            if target != "".join(target.split()):
                raise ValueError(f"{name} links to '{target}': a Bom's list cannot hold a link target with whitespace")
            data = target.encode("utf-8")
            lines.append(f"{name}\t{mode}\t{ROOT_UID}/{ROOT_GID}\t{len(data)}\t{cksum(data)}\t{target}")
        elif stat.S_ISDIR(info.st_mode):
            lines.append(f"{name}\t{mode}\t{ROOT_UID}/{ROOT_GID}")
        else:
            data = path.read_bytes()
            lines.append(f"{name}\t{mode}\t{ROOT_UID}/{ROOT_GID}\t{len(data)}\t{cksum(data)}")
    return "".join(f"{line}\n" for line in lines)


def count(root: Path) -> tuple[int, int]:
    """How many files a payload installs (with its root folder) and how much room they take, in KiB, as the
    installer shows it before installing."""
    entries = _entries(root)
    kbytes = sum(math.ceil(p.lstat().st_size / 1024) for _, p in entries if p.is_file() and not p.is_symlink())
    return len(entries), max(kbytes, 1)


def package_info(identifier: str, version: str, *, files: int, kbytes: int, scripts: tuple[str, ...]) -> bytes:
    """A part's PackageInfo. Not relocatable: an app of the same identifier somewhere else on the Mac must not make
    the installer put the update there (pkgbuild's default for bundles)."""
    info = ET.Element(
        "pkg-info",
        {
            "format-version": "2",
            "identifier": identifier,
            "version": version,
            "install-location": "/",
            "auth": "root",
            "relocatable": "false",
            "overwrite-permissions": "true",
            "postinstall-action": "none",
            "generator-version": "claudia packaging/macos/flatpkg.py",
        },
    )
    ET.SubElement(info, "payload", {"numberOfFiles": str(files), "installKBytes": str(kbytes)})
    found = ET.SubElement(info, "scripts")
    for script in scripts:
        ET.SubElement(found, script, {"file": f"./{script}"})
    return ET.tostring(info, encoding="utf-8", xml_declaration=True)


# ------------------------------------------------------------------------------------------------------------- xar
def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()  # noqa: S324 (the checksum the xar format names)


def _text(parent: ET.Element, tag: str, value: str, attributes: dict[str, str] | None = None) -> ET.Element:
    element = ET.SubElement(parent, tag, attributes or {})
    element.text = value
    return element


def xar(members: list[tuple[str, bytes | None]]) -> bytes:
    """A xar archive of ``members``: (path, data), data ``None`` for a folder; a folder is named before what is in
    it. The data is stored as it is (a payload is gzipped already), with its SHA-1, as productbuild stores it."""
    toc = ET.Element("toc")
    checksum = ET.SubElement(toc, "checksum", {"style": "sha1"})
    _text(checksum, "offset", "0")
    _text(checksum, "size", "20")
    _text(toc, "creation-time", "1970-01-01T00:00:00")
    folders: dict[str, ET.Element] = {"": toc}
    heap = bytearray()
    for number, (path, data) in enumerate(members, start=1):
        parent, _, name = path.rpartition("/")
        if parent not in folders:
            raise ValueError(f"{path}: its folder {parent} has to come first")
        entry = ET.SubElement(folders[parent], "file", {"id": str(number)})
        _text(entry, "name", name)
        _text(entry, "type", "directory" if data is None else "file")
        _text(entry, "mode", "0755" if data is None else "0644")
        for tag, value in (("uid", "0"), ("gid", "0"), ("user", "root"), ("group", "wheel")):
            _text(entry, tag, value)
        if data is None:
            folders[path] = entry
            continue
        stored = ET.SubElement(entry, "data")
        _text(stored, "length", str(len(data)))
        _text(stored, "offset", str(20 + len(heap)))  # after the table's checksum, which opens the heap
        _text(stored, "size", str(len(data)))
        ET.SubElement(stored, "encoding", {"style": "application/octet-stream"})
        _text(stored, "extracted-checksum", _sha1(data), {"style": "sha1"})
        _text(stored, "archived-checksum", _sha1(data), {"style": "sha1"})
        heap += data
    document = ET.Element("xar")
    document.append(toc)
    table = ET.tostring(document, encoding="utf-8", xml_declaration=True)
    compressed = zlib.compress(table, 9)
    header = struct.pack(">4sHHQQI", b"xar!", 28, 1, len(compressed), len(table), 1)
    return header + compressed + hashlib.sha1(compressed).digest() + bytes(heap)  # noqa: S324
