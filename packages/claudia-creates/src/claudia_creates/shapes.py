"""The shape library: the outlines a server offers, read from folders on disk (D67, E10.7).

The shape *format* — one outline, its box, its text area — is ``claudia_core.shapes``, so that all three apps
can hold a shape in their documents. What is here is the part that touches the filesystem, which the kernel may
not: the shipped shapes in ``builtin_shapes/`` plus whatever folders a server was given.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from claudia_core.shapes import ShapeDefinition, ShapeError, parse_shape

MAX_FILE_BYTES = 16 * 1024
BUILTIN_DIRECTORY = Path(__file__).parent / "builtin_shapes"


def _read_file(file: Path) -> ShapeDefinition:
    if file.stat().st_size > MAX_FILE_BYTES:
        raise ShapeError(f"too large (at most {MAX_FILE_BYTES // 1024} KB)")
    try:
        shape = parse_shape(file.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        raise ShapeError("not text in UTF-8") from None
    if shape.id != file.stem:
        raise ShapeError(f"the file name {file.stem!r} must be the shape's id, which is {shape.id!r}")
    return shape


def _read_folder(folder: Path) -> tuple[list[ShapeDefinition], list[tuple[str, str]]]:
    if not folder.is_dir():
        return [], [(folder.name or str(folder), "this is not a folder")]
    shapes: list[ShapeDefinition] = []
    problems: list[tuple[str, str]] = []
    for file in sorted(folder.glob("*.json")):
        try:
            shapes.append(_read_file(file))
        except (ShapeError, OSError) as error:
            problems.append((file.name, str(error)))
    return shapes, problems


class ShapeLibrary:
    """The shapes a server offers: the ones that ship with claudia, then those in the folders it was given.

    A shape in a later folder replaces one with the same id from an earlier one (or a shipped one). A file that is not
    right is skipped and listed in ``problems`` as ``(file name, what is wrong)``, so that one typo does not take
    the server down."""

    def __init__(self, shapes: Iterable[ShapeDefinition] = (), problems: Iterable[tuple[str, str]] = ()):
        self._shapes = {shape.id: shape for shape in shapes}
        self.problems: tuple[tuple[str, str], ...] = tuple(problems)

    @classmethod
    def load(cls, directories: Iterable[Path | str] = ()) -> ShapeLibrary:
        """The shipped shapes plus those of ``directories`` (each a folder of ``<id>.json`` files), later ones win."""
        shapes: dict[str, ShapeDefinition] = {}
        problems: list[tuple[str, str]] = []
        for folder in (BUILTIN_DIRECTORY, *map(Path, directories)):
            found, trouble = _read_folder(folder)
            shapes.update((shape.id, shape) for shape in found)
            problems += trouble
        return cls(shapes.values(), problems)

    def get(self, shape_id: str) -> ShapeDefinition | None:
        """The shape with this id, or ``None``."""
        return self._shapes.get(shape_id)

    def __contains__(self, shape_id: object) -> bool:
        return shape_id in self._shapes

    def __iter__(self) -> Iterator[ShapeDefinition]:
        return iter(sorted(self._shapes.values(), key=lambda shape: shape.id))

    def __len__(self) -> int:
        return len(self._shapes)
