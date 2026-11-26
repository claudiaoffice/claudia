"""Mach-O, the format of the Mac's programs and libraries: which files are Mach-O, and whether each carries a code
signature (E8.5; the owner's Q4, 2026-11-26).

Apple Silicon runs no code without a signature, and an ad-hoc one is enough. Node, CPython, Neutralino and the wheels'
libraries were built on a Mac and carry one; the package is built on Linux and changes none of them, so it signs none
and refuses a binary that lacks one (``build.py check-signatures``). What counts is the slice Apple Silicon runs, the
arm64 one: universal wheels (lxml, fontTools, brotli) carry an unsigned Intel slice, which it never runs. Only the
presence of ``LC_CODE_SIGNATURE`` is looked at: whether a signature is valid only macOS can tell, when it runs the code.
"""

from __future__ import annotations

import struct
from pathlib import Path

MH_MAGIC_64 = 0xFEEDFACF  # little-endian on disk: cf fa ed fe
FAT_MAGIC = 0xCAFEBABE  # big-endian on disk
LC_CODE_SIGNATURE = 0x1D
CPU_ARM64 = 0x0100000C  # arm64 and arm64e (a subtype of it)
_HEADER_64 = 32
_MOST_SLICES = 16  # a Java class file starts with cafebabe too, followed by its version (45 and more)


def _slices(data: bytes) -> list[bytes] | None:
    """The thin Mach-O images in ``data``, or ``None`` if it is not Mach-O."""
    if len(data) >= _HEADER_64 and struct.unpack_from("<I", data)[0] == MH_MAGIC_64:
        return [data]
    if len(data) < 8 or struct.unpack_from(">I", data)[0] != FAT_MAGIC:
        return None
    (number,) = struct.unpack_from(">I", data, 4)
    if not 0 < number <= _MOST_SLICES or len(data) < 8 + 20 * number:
        return None
    found = []
    for index in range(number):
        _cpu, _sub, offset, size, _align = struct.unpack_from(">iiIII", data, 8 + 20 * index)
        piece = data[offset : offset + size]
        if len(piece) != size or len(piece) < _HEADER_64 or struct.unpack_from("<I", piece)[0] != MH_MAGIC_64:
            return None
        found.append(piece)
    return found


def is_mach_o(data: bytes) -> bool:
    return _slices(data) is not None


def _signed(image: bytes) -> bool:
    (commands, size) = struct.unpack_from("<II", image, 16)
    offset = _HEADER_64
    for _ in range(commands):
        if offset + 8 > min(len(image), _HEADER_64 + size):
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


def _mach_o_files(root: Path) -> list[Path]:
    found = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as handle:
            if struct.unpack_from(">I", handle.read(4).ljust(4, b"\0"))[0] not in (FAT_MAGIC, 0xCFFAEDFE):
                continue
        if is_mach_o(path.read_bytes()):
            found.append(path)
    return found


def count(root: Path) -> int:
    """How many Mach-O files are under ``root`` (links not followed)."""
    return len(_mach_o_files(root))


def unsigned(root: Path) -> list[Path]:
    """The Mach-O files under ``root`` that Apple Silicon would not run: no signed arm64 slice; relative to it."""
    return [path.relative_to(root) for path in _mach_o_files(root) if not runs_on_apple_silicon(path.read_bytes())]
