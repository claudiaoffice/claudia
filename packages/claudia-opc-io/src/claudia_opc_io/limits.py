"""How much a package may unpack to before it is refused (SEC-15).

A zip archive lists, in its directory, how large every part is and how large it was before packing. That is enough
to tell a document from a "zip bomb" -- a few kilobytes that unpack to gigabytes -- *before* a single byte is
unpacked, so a file that anybody may upload cannot use up the memory of the machine that reads it.

The defaults are for bombs, not for documents: a deck of full-resolution photographs is tens of MiB, a worksheet
of a million rows a few hundred. What a program may read is the one place these numbers live; nothing reads a
package any other way (:func:`~claudia_opc_io.read_parts` calls :func:`check_package`, and so does the server
before it hands an upload to an office library that opens the zip itself).
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from io import BytesIO

_KIB = 1024
_MIB = 1024 * _KIB


class PackageRefused(ValueError):
    """A package that is too large to read, or unpacks to far too much; the message is a sentence that says which."""


def _size(n: int) -> str:
    """``n`` bytes as a person reads them: ``5 MiB``, ``300 KiB``."""
    return f"{n / _MIB:g} MiB" if n >= _MIB else f"{n // _KIB} KiB"


@dataclass(frozen=True)
class PackageLimits:
    """What a package may hold. All sizes are bytes *after* unpacking, as the archive's directory declares them.

    ``max_ratio`` is how many times larger than its packed size a part may be; it is judged only for a part of at
    least ``ratio_from_bytes``, because a small part of repeating text (an empty worksheet, a theme) compresses
    hundredfold and costs nothing. ``max_ratio=None`` switches the ratio off."""

    max_members: int = 10_000
    max_part_bytes: int = 256 * _MIB
    max_total_bytes: int = 512 * _MIB
    max_ratio: int | None = 250
    ratio_from_bytes: int = 32 * _MIB

    def __post_init__(self) -> None:
        sizes = (self.max_members, self.max_part_bytes, self.max_total_bytes, self.ratio_from_bytes)
        if min(sizes) < 1 or (self.max_ratio is not None and self.max_ratio < 1):
            raise ValueError("every package limit is a positive number")


#: What :func:`check_package` and :func:`~claudia_opc_io.read_parts` use unless told otherwise.
DEFAULT_LIMITS = PackageLimits()


def check_package(zip_bytes: bytes, limits: PackageLimits = DEFAULT_LIMITS) -> None:
    """Return if ``zip_bytes`` is a package within ``limits``; raise :class:`PackageRefused`, with a sentence that
    names the part and the limit, if not. Nothing is unpacked. Bytes that are no zip at all raise
    ``zipfile.BadZipFile``, which is for the reader to word."""
    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        parts = [info for info in archive.infolist() if not info.is_dir()]
    if len(parts) > limits.max_members:
        raise PackageRefused(f"the file has {len(parts)} parts; at most {limits.max_members} are read")
    total = 0
    for info in parts:
        total += info.file_size
        if info.file_size > limits.max_part_bytes:
            raise PackageRefused(
                f"{info.filename} unpacks to {_size(info.file_size)}; "
                f"a part may be at most {_size(limits.max_part_bytes)}"
            )
        if (
            limits.max_ratio is not None
            and info.file_size >= limits.ratio_from_bytes
            and info.file_size > limits.max_ratio * max(info.compress_size, 1)
        ):
            raise PackageRefused(
                f"{info.filename} would unpack to {_size(info.file_size)} from {_size(info.compress_size)}: a document "
                f"does not compress {limits.max_ratio} times over"
            )
    if total > limits.max_total_bytes:
        raise PackageRefused(
            f"the parts of the file together unpack to {_size(total)}; at most {_size(limits.max_total_bytes)} are read"
        )
