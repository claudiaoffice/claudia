"""Mach-O, the format of the Mac's programs and libraries: which files are Mach-O, and whether each carries a code
signature (E8.5; the owner's Q4, 2026-11-26).

Apple Silicon runs no code without a signature, and an ad-hoc one is enough. Node, CPython, Neutralino and the wheels'
libraries were built on a Mac and carry one; the package is built on Linux and changes none of them, so it signs none
and refuses a binary that lacks one (``build.py check-signatures``). What counts is the slice Apple Silicon runs, the
arm64 one: universal wheels (lxml, fontTools, brotli) carry an unsigned Intel slice, which it never runs. Only the
presence of ``LC_CODE_SIGNATURE`` is looked at: whether a signature is valid only macOS can tell, when it runs the code.

The check fails closed: a file that starts as Mach-O but cannot be read as such counts as one that would not run.
"""

from __future__ import annotations

import struct
from pathlib import Path

MH_MAGIC = 0xFEEDFACE  # 32-bit, little-endian on disk: ce fa ed fe
MH_MAGIC_64 = 0xFEEDFACF  # 64-bit, little-endian on disk: cf fa ed fe
FAT_MAGIC = 0xCAFEBABE  # big-endian on disk
FAT_MAGIC_64 = 0xCAFEBABF  # big-endian on disk, with offsets of 64 bits
LC_CODE_SIGNATURE = 0x1D
CPU_ARM64 = 0x0100000C  # arm64 and arm64e (a subtype of it)
_HEADER = {MH_MAGIC: 28, MH_MAGIC_64: 32}  # the size of a thin image's header
_MOST_SLICES = 16  # a Java class file starts with cafebabe too, followed by its version (45 and more)


def _thin_magic(image: bytes) -> int | None:
    if len(image) < 28:
        return None
    (magic,) = struct.unpack_from("<I", image)
    return magic if magic in _HEADER and len(image) >= _HEADER[magic] else None


def _slices(data: bytes) -> list[bytes] | None:
    """The thin Mach-O images in ``data`` (32 or 64 bits), or ``None`` if it cannot be read as Mach-O."""
    if _thin_magic(data) is not None:
        return [data]
    if len(data) < 8 or struct.unpack_from(">I", data)[0] not in (FAT_MAGIC, FAT_MAGIC_64):
        return None
    entry, layout = (32, ">iiQQII") if struct.unpack_from(">I", data)[0] == FAT_MAGIC_64 else (20, ">iiIII")
    (number,) = struct.unpack_from(">I", data, 4)
    if not 0 < number <= _MOST_SLICES or len(data) < 8 + entry * number:
        return None
    found = []
    for index in range(number):
        _cpu, _sub, offset, size, *_ = struct.unpack_from(layout, data, 8 + entry * index)
        piece = data[offset : offset + size]
        if len(piece) != size or _thin_magic(piece) is None:
            return None
        found.append(piece)
    return found


def is_mach_o(data: bytes) -> bool:
    """Whether ``data`` can be read as Mach-O: thin (32 or 64 bits) or universal (32- or 64-bit offsets)."""
    return _slices(data) is not None


def _signed(image: bytes) -> bool:
    header = _HEADER[struct.unpack_from("<I", image)[0]]
    (commands, size) = struct.unpack_from("<II", image, 16)
    offset = header
    for _ in range(commands):
        if offset + 8 > min(len(image), header + size):
            return False
        command, length = struct.unpack_from("<II", image, offset)
        if command == LC_CODE_SIGNATURE:
            return True
        if length < 8:
            return False
        offset += length
    return False


def runs_on_apple_silicon(data: bytes) -> bool:
    """Whether the Mach-O ``data`` has a slice for Apple Silicon, and each such slice a code signature."""
    arm = [image for image in _slices(data) or [] if struct.unpack_from("<i", image, 4)[0] == CPU_ARM64]
    return bool(arm) and all(_signed(image) for image in arm)


def _starts_as_mach_o(data: bytes) -> bool:
    """What the first bytes say: any Mach-O magic, but not a Java class file (its "number of slices" is its version)."""
    if len(data) < 8:
        return False
    if struct.unpack_from("<I", data)[0] in _HEADER:
        return True
    magic, number = struct.unpack_from(">II", data)
    return magic == FAT_MAGIC_64 or (magic == FAT_MAGIC and number <= _MOST_SLICES)


def _mach_o_files(root: Path) -> list[Path]:
    """Every file under ``root`` that starts as Mach-O, links not followed: one that then cannot be read stays in the
    list, so that it is refused rather than let through."""
    found = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as handle:
            if _starts_as_mach_o(handle.read(8)):
                found.append(path)
    return found


def count(root: Path) -> int:
    """How many Mach-O files are under ``root`` (links not followed)."""
    return len(_mach_o_files(root))


def unsigned(root: Path) -> list[Path]:
    """The Mach-O files under ``root`` that Apple Silicon would not run: no signed arm64 slice; relative to it."""
    return [path.relative_to(root) for path in _mach_o_files(root) if not runs_on_apple_silicon(path.read_bytes())]
