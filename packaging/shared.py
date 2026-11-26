"""What the installers' builds share (packaging/windows/build.py, packaging/macos/build.py): the version of a build
from a tag or a commit, files pinned by SHA-256, downloads, and the checks that an earlier step has run.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path

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


def download(url: str, target: Path) -> Path:
    """The file at ``url``, written to ``target``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as out:  # noqa: S310 (a pinned https url)
        shutil.copyfileobj(response, out)
    return target


def require(path: Path, step: str) -> Path:
    if not path.exists():
        raise BuildError(f"{path} is missing. It is made by: {step}")
    return path


def copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, dirs_exist_ok=True)
