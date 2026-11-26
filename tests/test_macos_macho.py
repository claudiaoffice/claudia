"""Which files of the macOS package are programs or libraries for the Mac (Mach-O), and whether each is signed.

Apple Silicon runs no code without a signature; an ad-hoc one is enough, and what was built on a Mac carries one. The
build changes no binary, so it signs none: it refuses to make a package with an unsigned one (E8.5, the owner's Q4,
2026-11-26). The files here are made by hand, as small as the format allows.
"""

from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("macos_macho", ROOT / "packaging" / "macos" / "macho.py")
macho = importlib.util.module_from_spec(SPEC)
sys.modules["macos_macho"] = macho
SPEC.loader.exec_module(macho)

LC_SEGMENT_64 = 0x19
LC_CODE_SIGNATURE = 0x1D
CPU_ARM64 = 0x0100000C
CPU_X86_64 = 0x01000007


def thin(*commands: int, cpu: int = CPU_ARM64) -> bytes:
    """A 64-bit Mach-O with these load commands (each the smallest it can be)."""
    body = b"".join(struct.pack("<II", command, 16) + bytes(8) for command in commands)
    header = struct.pack("<IiiIIIII", 0xFEEDFACF, cpu, 0, 2, len(commands), len(body), 0, 0)
    return header + body


def fat(*slices: bytes) -> bytes:
    """A universal binary of these slices, each at a 4096-byte boundary."""
    header = struct.pack(">II", 0xCAFEBABE, len(slices))
    entries, data = b"", b""
    offset = 4096
    for piece in slices:
        entries += struct.pack(">iiIII", CPU_ARM64, 0, offset + len(data), len(piece), 12)
        data += piece + bytes(-len(piece) % 4096)
    return (header + entries).ljust(4096, b"\0") + data


SIGNED = thin(LC_SEGMENT_64, LC_CODE_SIGNATURE)
UNSIGNED = thin(LC_SEGMENT_64)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (SIGNED, True),
        (UNSIGNED, False),
        (fat(SIGNED, thin(LC_CODE_SIGNATURE, cpu=CPU_X86_64)), True),
        (fat(SIGNED, UNSIGNED), False),  # every slice has to be signed
    ],
)
def test_a_mach_o_is_signed_when_every_slice_has_its_code_signature(data, expected):
    assert macho.is_mach_o(data)
    assert macho.is_signed(data) is expected


@pytest.mark.parametrize(
    "data",
    [
        b"#!/bin/sh\necho\n",
        b"",
        b"\xca\xfe\xba\xbe\x00\x00\x00\x34" + bytes(64),  # a Java class file (version 52), which starts the same way
        b"\xcf\xfa\xed\xfe",  # cut off
    ],
)
def test_other_files_are_not_mach_o(data):
    assert not macho.is_mach_o(data)


def test_the_unsigned_mach_o_files_of_a_folder_are_found_and_links_are_not_followed(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "node").write_bytes(SIGNED)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "_speedups.so").write_bytes(UNSIGNED)
    (tmp_path / "lib" / "notes.txt").write_text("not a program", encoding="utf-8")
    (tmp_path / "bin" / "node-link").symlink_to("node")
    (tmp_path / "bin" / "dangling").symlink_to("nowhere")
    assert macho.unsigned(tmp_path) == [Path("lib/_speedups.so")]
    assert macho.count(tmp_path) == 2
