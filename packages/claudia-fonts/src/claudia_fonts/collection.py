"""A collection: a folder of fonts and the licence record that says what they may be used for (E3.3).

Fonts do not say under which licence they come (the name tables of Latin Modern and TeX Gyre carry no licence text),
so every collection brings a ``collection.json`` next to its fonts. The record is mandatory: no record, no fonts.

.. code-block:: json

    {"format": 1, "name": "Liberation", "licence": "OFL-1.1", "redistributable": true,
     "source": "https://github.com/liberationfonts", "version": "2.1.5"}

``redistributable`` answers who may receive the fonts (D1041, the "may go" of Server settings ▸ Fonts): ``true``,
anyone (an open licence: the files are handed to every client and may go into exports and documents); ``false``, the
people using this server only (a licence for one organisation: the files are handed only to people who passed the
server's access secret, and never go into an export). A font the catalogue cannot use is the third answer, "not
usable", which no record gives: :class:`~claudia_fonts.Problem` says why. ``licence`` is free text for people,
normally an SPDX identifier. ``added_by`` and ``added`` (an ISO date) say who added a collection through the server
settings and when; a collection an operator put on the disk has neither.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

COLLECTION_FILE = "collection.json"
RECORD_FORMAT = 1

MayGo = Literal["anywhere", "this-server"]
MAY_GO: tuple[MayGo, ...] = get_args(MayGo)
"""Who may receive the fonts of a collection (D1041): anyone, or the people using this server."""


class RecordError(ValueError):
    """The record of a collection is missing or wrong; the message says which part."""


def _text(data: Mapping, key: str, *, required: bool) -> str:
    value = data.get(key)
    if value is None:
        if required:
            raise RecordError(f"{COLLECTION_FILE}: {key} is missing")
        return ""
    if not isinstance(value, str):
        raise RecordError(f"{COLLECTION_FILE}: {key} must be text")
    if required and not value.strip():
        raise RecordError(f"{COLLECTION_FILE}: {key} must not be blank")
    return value.strip()


@dataclass(frozen=True)
class CollectionRecord:
    """What a collection's licence allows, as its ``collection.json`` states it."""

    name: str
    licence: str
    redistributable: bool
    source: str = ""
    version: str = ""
    added_by: str = ""
    added: str = ""

    @property
    def may_go(self) -> MayGo:
        """Who may receive the fonts, ``anywhere`` (an open licence) or ``this-server`` (its own people only)."""
        return "anywhere" if self.redistributable else "this-server"

    def to_data(self) -> dict:
        """The record as ``collection.json`` holds it; empty optional fields are left out."""
        data: dict = {
            "format": RECORD_FORMAT,
            "name": self.name,
            "licence": self.licence,
            "redistributable": self.redistributable,
        }
        for key in ("source", "version", "added_by", "added"):
            if getattr(self, key):
                data[key] = getattr(self, key)
        return data

    @classmethod
    def from_data(cls, data: object) -> CollectionRecord:
        """Check the parsed JSON of a record and make it; :class:`RecordError` names the first thing that is wrong."""
        if not isinstance(data, Mapping):
            raise RecordError(f"{COLLECTION_FILE} must hold one JSON object")
        if "format" not in data:
            raise RecordError(f"{COLLECTION_FILE}: format is missing")
        if data["format"] != RECORD_FORMAT:
            raise RecordError(
                f"{COLLECTION_FILE}: format {data['format']!r} is not known (this version reads {RECORD_FORMAT})"
            )
        redistributable = data.get("redistributable")
        if redistributable is None:
            raise RecordError(f"{COLLECTION_FILE}: redistributable is missing")
        if not isinstance(redistributable, bool):
            raise RecordError(f"{COLLECTION_FILE}: redistributable must be true or false")
        return cls(
            name=_text(data, "name", required=True),
            licence=_text(data, "licence", required=True),
            redistributable=redistributable,
            source=_text(data, "source", required=False),
            version=_text(data, "version", required=False),
            added_by=_text(data, "added_by", required=False),
            added=_text(data, "added", required=False),
        )


@dataclass(frozen=True)
class Collection:
    """A folder of fonts (searched with its subfolders) together with its record."""

    folder: Path
    record: CollectionRecord

    @classmethod
    def from_folder(cls, folder: str | Path) -> Collection:
        """Read the record in ``folder``; :class:`RecordError` if there is none or it is wrong."""
        folder = Path(folder)
        try:
            text = (folder / COLLECTION_FILE).read_text(encoding="utf-8")
        except FileNotFoundError:
            raise RecordError(
                f"{folder} has no {COLLECTION_FILE}: every collection says under which licence its fonts come"
            ) from None
        except (OSError, UnicodeDecodeError) as error:
            raise RecordError(f"{COLLECTION_FILE} cannot be read: {error}") from error
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise RecordError(f"{COLLECTION_FILE} is not valid JSON: {error}") from error
        return cls(folder, CollectionRecord.from_data(data))
