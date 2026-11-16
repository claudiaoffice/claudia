"""The catalogue: the fonts a server has, and what it says about the ones it will not use (E3.3).

One catalogue serves two consumers with the same files: the web fonts for clients (:mod:`claudia_fonts.webfonts`) and
the typesetting engine (:mod:`claudia_fonts.fontconfig`). A font that the catalogue does not use is listed in
:attr:`Catalogue.problems`, and the engine is told to ignore that file as well.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

from claudia_core.stand_ins import GENERIC_FONTS, SAME_WIDTHS

from .collection import Collection, RecordError
from .font import FONT_SUFFIXES, FontFile, FontProblem, read_font

DEFAULT_SUBSTITUTIONS: Mapping[str, str] = SAME_WIDTHS
"""Open fonts that take exactly the room of a common office font, by the office font (Arial → Arimo):
:data:`claudia_core.stand_ins.SAME_WIDTHS` (E3.13). Every one of them is shipped (D500)."""

DEFAULT_GENERICS: Mapping[str, str] = GENERIC_FONTS
"""The font each CSS generic family stands for (``serif``, ``sans-serif``, ``monospace``) and the last resort
(``fallback``): :data:`claudia_core.stand_ins.GENERIC_FONTS`, the suite's own fonts (D905). Clients get them with
``GET /api/fonts``."""

Closeness = Literal["same", "same-widths", "other"]
CLOSENESS: tuple[Closeness, ...] = get_args(Closeness)
"""How close what a document is shown with is to the font it asks for (E3.13), in the words people see: the font
itself, a font with exactly its widths (lines and pages break the same, the letters differ), or another font. The
layout library has the same words (``layout/src/fonts/stand-ins.generated.ts``)."""


@dataclass(frozen=True)
class Problem:
    """A file or folder the catalogue does not use, and why: ``reason`` for a log, ``code`` for a page that says it in
    its own words (a :class:`~claudia_fonts.FontProblem` code, ``record`` for a folder without a usable
    ``collection.json``, ``replaced`` for a font another collection has a newer copy of), ``detail`` what those words
    need (the record's error, the fsType, the collection that replaces it). ``family``, ``style`` and ``collection``
    are known when the file could be read that far."""

    path: Path
    reason: str
    code: str = ""
    detail: str = ""
    family: str | None = None
    style: str | None = None
    collection: str = ""

    @property
    def not_usable(self) -> bool:
        """Whether the font is missing from the catalogue; a replaced font is not, as its newer copy is used."""
        return self.code != "replaced"


@dataclass(frozen=True)
class Resolution:
    """What a document gets when it asks for a family: the family itself, a substitute, or nothing."""

    requested: str
    provided: str | None
    substituted: bool

    @property
    def closeness(self) -> Closeness:
        """``same`` for the family itself, ``same-widths`` for its substitute, ``other`` when the catalogue has
        neither (whoever shows the document then uses another font, such as the generic family's)."""
        if self.provided is None:
            return "other"
        return "same-widths" if self.substituted else "same"


def _font_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in FONT_SUFFIXES)


class Catalogue:
    """The usable fonts of some collections. Build it with :meth:`from_folders` or :meth:`from_collections`."""

    def __init__(
        self,
        fonts: Iterable[FontFile],
        problems: Iterable[Problem],
        substitutions: Mapping[str, str],
        collections: Iterable[Collection] = (),
    ) -> None:
        self._by_style = {(f.family.casefold(), f.style.casefold()): f for f in fonts}
        self._by_family: dict[str, list[FontFile]] = {}
        for font in self._by_style.values():
            self._by_family.setdefault(font.family.casefold(), []).append(font)
        for members in self._by_family.values():
            members.sort(key=lambda f: (f.weight, f.italic, f.style))
        self._by_hash = {f.sha256: f for f in self._by_style.values()}
        self._substitutions = {k.casefold(): v for k, v in substitutions.items()}
        self._substitution_names = dict(substitutions)
        self.problems: tuple[Problem, ...] = tuple(problems)
        """What was not used, in the order it was found."""
        self.collections: tuple[Collection, ...] = tuple(collections)
        """The collections read, in the order read (a later one wins for the same family and style)."""
        self.digest: str = hashlib.sha256("\n".join(sorted(self._by_hash)).encode("ascii")).hexdigest()
        """Identifies the exact set of font files; it changes when a font is added, changed or removed."""

    @classmethod
    def from_collections(
        cls, collections: Iterable[Collection], *, substitutions: Mapping[str, str] | None = None
    ) -> Catalogue:
        """The fonts of ``collections``. A later collection replaces a font of the same family and style."""
        return cls._scan(list(collections), [], substitutions)

    @classmethod
    def from_folders(
        cls, folders: Iterable[str | Path], *, substitutions: Mapping[str, str] | None = None
    ) -> Catalogue:
        """The fonts of the folders, each with its ``collection.json``. A folder without a valid record is a
        :class:`Problem`, not an error: the server starts and says what it skipped."""
        collections, problems = [], []
        for folder in folders:
            try:
                collections.append(Collection.from_folder(folder))
            except RecordError as error:
                problems.append(Problem(Path(folder), str(error), code="record", detail=str(error)))
        return cls._scan(collections, problems, substitutions)

    @classmethod
    def _scan(
        cls, collections: list[Collection], problems: list[Problem], substitutions: Mapping[str, str] | None
    ) -> Catalogue:
        chosen: dict[tuple[str, str], FontFile] = {}
        for collection in collections:
            name = collection.record.name
            if not collection.folder.is_dir():
                problems.append(Problem(collection.folder, "is not a folder", code="record", collection=name))
                continue
            for path in _font_files(collection.folder):
                try:
                    font = read_font(path, collection)
                except FontProblem as error:
                    problems.append(
                        Problem(path, str(error), error.code, error.detail, error.family, error.style, collection=name)
                    )
                    continue
                key = (font.family.casefold(), font.style.casefold())
                old = chosen.get(key)
                if old is not None and old.sha256 != font.sha256:  # the same file twice is nothing to report
                    problems.append(
                        Problem(
                            old.path,
                            f"replaced by {font.path} (same family and style)",
                            code="replaced",
                            detail=name,
                            family=old.family,
                            style=old.style,
                            collection=old.collection,
                        )
                    )
                chosen[key] = font
        table = DEFAULT_SUBSTITUTIONS if substitutions is None else substitutions
        return cls(chosen.values(), problems, table, collections)

    def families(self) -> tuple[str, ...]:
        """The family names, sorted without regard to case."""
        names = (members[0].family for members in self._by_family.values())
        return tuple(sorted(names, key=str.casefold))

    def fonts(self) -> tuple[FontFile, ...]:
        """All fonts, by family, weight and slant."""
        return tuple(font for key in sorted(self._by_family) for font in self._by_family[key])

    def fonts_of(self, family: str) -> tuple[FontFile, ...]:
        """The fonts of a family (case does not matter), lightest first; empty if there is none."""
        return tuple(self._by_family.get(family.casefold(), ()))

    def by_hash(self, sha256: str) -> FontFile | None:
        """The font whose file has this hash, if the catalogue has it."""
        return self._by_hash.get(sha256)

    def stands_in_for(self, family: str) -> tuple[str, ...]:
        """The fonts a document may ask for that ``family`` is shown with instead (the office fonts it has the widths
        of: Arimo for Arial and Helvetica), in the table's order; empty if it stands in for none."""
        wanted = family.casefold()
        return tuple(asked for asked, given in self._substitution_names.items() if given.casefold() == wanted)

    def __contains__(self, family: object) -> bool:
        return isinstance(family, str) and family.casefold() in self._by_family

    def resolve(self, family: str) -> Resolution:
        """What to use for ``family``: the family itself if the catalogue has it, else its metric-compatible
        substitute if the catalogue has that, else nothing."""
        own = self.fonts_of(family)
        if own:
            return Resolution(family, own[0].family, substituted=False)
        target = self._substitutions.get(family.casefold())
        substitute = self.fonts_of(target) if target else ()
        if substitute:
            return Resolution(family, substitute[0].family, substituted=True)
        return Resolution(family, None, substituted=False)
