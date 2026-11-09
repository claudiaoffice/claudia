"""Shapes: outlines described as plain JSON, the same in all three apps (D67, E10.7, E10.16).

A shape file holds one JSON object. Everything is geometry in a box of 100 by 100 units; the app stretches the box
to the size of the object. There is deliberately no colour, no line width and no script in a shape: how it looks comes
from the style of the object that uses it (D73), so a shape can never load or leak anything.

Only the format lives here — reading and validating one outline, with no I/O, so that every app can hold a shape
in its documents. Collecting shapes from folders on disk is a server's job and lives in
:mod:`claudia_creates.shapes` (``ShapeLibrary``).

.. code-block:: json

    {
      "format": 1,
      "id": "circle",
      "name": "Circle",
      "aspect": 1,
      "path": "M50 0 A50 50 0 1 1 50 100 A50 50 0 1 1 50 0 Z",
      "text_area": {"x": 14.6, "y": 14.6, "w": 70.8, "h": 70.8}
    }

* ``format``: the version of this file layout; only 1 exists.
* ``id``: lower-case letters, digits, ``-`` and ``_``; the file is called ``<id>.json``.
* ``name``: what people see in the menu.
* ``path``: the outline: absolute ``M`` (move), ``L`` (line), ``C`` (cubic curve), ``A`` (arc) and ``Z`` (close)
  with their numbers, as in SVG paths. The first command is ``M``. Coordinates run from 0 to 100.
* ``aspect``: optional: width divided by height if the shape must keep it (a circle: 1); ``null`` when it is free.
* ``text_area``: optional: where text goes inside the box; the whole box by default.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

FORMAT = 1
BOX = 100  # the shape's own coordinate box is BOX by BOX units
MAX_PATH_CHARS = 4_000
MAX_NAME_CHARS = 60
MIN_ASPECT, MAX_ASPECT = 0.1, 10

_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}")
_TOKEN = re.compile(r"[ \t\r\n,]*(?:([A-Za-z])|(\d+(?:\.\d+)?))")
_NUMBERS_OF = {"M": 2, "L": 2, "C": 6, "A": 7, "Z": 0}
_KEYS = {"format", "id", "name", "path", "aspect", "text_area"}
_REQUIRED = ("format", "id", "name", "path")


class ShapeError(ValueError):
    """A shape file that is not right; the message names the part and says what is wrong."""


def _refuse_constant(name: str) -> Any:
    raise ShapeError(f"{name} is not a number JSON allows")


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


# -- the outline ---------------------------------------------------------------------------------------------------
def _tokens(path: str) -> Iterator[tuple[str, str]]:
    """Commands and numbers of a path as ``("command", "M")`` and ``("number", "12.5")``."""
    position = 0
    while position < len(path):
        found = _TOKEN.match(path, position)
        if found is None:
            rest = path[position:].lstrip(" \t\r\n,")
            if not rest:
                return
            raise ShapeError(f"path: unexpected {rest[0]!r}; only M, L, C, A, Z and numbers")
        position = found.end()
        yield ("command", found[1]) if found[1] else ("number", found[2])


def _check_number(command: str, index: int, text: str) -> None:
    value = float(text)
    if command == "A" and index in (3, 4):
        if text not in ("0", "1"):
            raise ShapeError("path: the two flags of an arc are 0 or 1")
    elif command == "A" and index == 2:
        if value > 360:
            raise ShapeError("path: the rotation of an arc is 0 to 360")
    elif value > BOX:
        raise ShapeError(f"path: coordinates run from 0 to {BOX}, not {text}")


def _check_path(path: object) -> str:
    if not isinstance(path, str) or not path.strip():
        raise ShapeError("path: must be text such as 'M0 0 L100 0 L100 100 Z'")
    if len(path) > MAX_PATH_CHARS:
        raise ShapeError(f"path: at most {MAX_PATH_CHARS} characters")
    tokens = list(_tokens(path))
    if tokens[0] != ("command", "M"):
        raise ShapeError("path: must start with M (move to the first point)")
    position = 0
    while position < len(tokens):
        kind, command = tokens[position]
        if kind != "command":
            raise ShapeError(f"path: a number {command} has no command in front of it")
        if command not in _NUMBERS_OF:
            raise ShapeError(f"path: {command!r} is not allowed; use M, L, C, A and Z with absolute coordinates")
        wanted = _NUMBERS_OF[command]
        numbers = tokens[position + 1 : position + 1 + wanted]
        following = tokens[position + 1 + wanted : position + 2 + wanted]
        if len(numbers) < wanted or any(k != "number" for k, _ in numbers) or any(k == "number" for k, _ in following):
            raise ShapeError(f"path: {command} takes exactly {wanted} numbers")
        for index, (_, text) in enumerate(numbers):
            _check_number(command, index, text)
        position += 1 + wanted
    return path


# -- the other parts -----------------------------------------------------------------------------------------------
def _check_id(value: object) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ShapeError("id: lower-case letters, digits, '-' and '_', starting with a letter, at most 40 characters")
    return value


def _check_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or not value.isprintable():
        raise ShapeError("name: must be a line of text")
    if len(value.strip()) > MAX_NAME_CHARS:
        raise ShapeError(f"name: at most {MAX_NAME_CHARS} characters")
    return value.strip()


def _check_aspect(value: object) -> float | None:
    if value is None:
        return None
    if not _is_number(value) or not MIN_ASPECT <= value <= MAX_ASPECT:  # type: ignore[operator]
        raise ShapeError(f"aspect: null, or width divided by height from {MIN_ASPECT} to {MAX_ASPECT}")
    return value  # type: ignore[return-value]


def _check_text_area(value: object) -> tuple[float, float, float, float]:
    if not isinstance(value, dict):
        raise ShapeError("text_area: must be an object with x, y, w and h")
    if set(value) != {"x", "y", "w", "h"} or not all(_is_number(v) for v in value.values()):
        raise ShapeError("text_area: needs the numbers x, y, w and h, and nothing else")
    x, y, w, h = value["x"], value["y"], value["w"], value["h"]
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > BOX or y + h > BOX:
        raise ShapeError(f"text_area: must be a part of the box (0 to {BOX}), wider and taller than 0")
    return (x, y, w, h)


@dataclass(frozen=True)
class ShapeDefinition:
    """One shape: an outline in a 100 by 100 box, its name, whether it keeps its proportions, and its text area.

    Build one from a file with :func:`parse_shape`, or from stored data with :meth:`from_data`; both refuse anything
    the format does not allow."""

    id: str
    name: str
    path: str
    aspect: float | None = None
    text_area: tuple[float, float, float, float] = (0, 0, BOX, BOX)

    def to_data(self) -> dict:
        """The plain-data form: what a shape file holds, and what a document stores of a shape it uses."""
        x, y, w, h = self.text_area
        return {
            "format": FORMAT,
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "aspect": self.aspect,
            "text_area": {"x": x, "y": y, "w": w, "h": h},
        }

    @classmethod
    def from_data(cls, data: object) -> ShapeDefinition:
        """Read the plain-data form; raises :class:`~claudia_core.shapes.ShapeError` naming the first thing that is
        wrong."""
        if not isinstance(data, dict):
            raise ShapeError("a shape is one JSON object")
        unknown = sorted(str(key) for key in set(data) - _KEYS)
        if unknown:
            raise ShapeError(f"unknown key {unknown[0]!r}: a shape has {', '.join(sorted(_KEYS))}")
        for key in _REQUIRED:
            if key not in data:
                raise ShapeError(f"missing {key!r}")
        if data["format"] != FORMAT or isinstance(data["format"], bool):
            raise ShapeError(f"format: this version reads format {FORMAT}, the file says {data['format']!r}")
        return cls(
            id=_check_id(data["id"]),
            name=_check_name(data["name"]),
            path=_check_path(data["path"]),
            aspect=_check_aspect(data.get("aspect")),
            text_area=_check_text_area(data["text_area"]) if "text_area" in data else (0, 0, BOX, BOX),
        )


def parse_shape(text: str) -> ShapeDefinition:
    """Read a shape from the text of a JSON file; raises :class:`~claudia_core.shapes.ShapeError` if it is not a valid
    shape."""
    try:
        data = json.loads(text, parse_constant=_refuse_constant)
    except ShapeError:
        raise
    except (ValueError, RecursionError) as error:
        raise ShapeError(f"not valid JSON: {error}") from None
    return ShapeDefinition.from_data(data)
