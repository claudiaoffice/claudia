"""The setup that lets a typesetting engine use the collection, and nothing else (E3.3, E3.4).

XeTeX and LuaTeX find fonts through *fontconfig*. A configuration file of our own, named by ``FONTCONFIG_FILE``, lists
the folders of the catalogue and nothing of the system, and hides every file the catalogue did not use: a font that
forbids embedding, a broken file, a font that a later collection replaced. So the engine uses exactly the fonts the
browser gets. The fonts are read where they are; nothing is copied.

Fontconfig *aliases* are deliberately not used: XeTeX checks the family name itself and does not follow them, so a
substitute (:meth:`claudia_fonts.Catalogue.resolve`) has to be named in the document that is typeset.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from .catalogue import Catalogue
from .font import FONT_SUFFIXES

CONFIG_NAME = "fonts.conf"
_HEADER = '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'


@dataclass(frozen=True)
class JobFonts:
    """A written configuration and the environment under which an engine must run to use it."""

    config: Path
    environment: dict[str, str]


def write_fontconfig(catalogue: Catalogue, directory: str | Path, cache_directory: str | Path) -> JobFonts:
    """Write ``fonts.conf`` into ``directory`` (a job's own folder) for the engine to use.

    ``cache_directory`` is where fontconfig keeps what it learned about the fonts; share one between jobs so that the
    fonts are not scanned again every time."""
    folders = sorted({font.path.parent for font in catalogue.fonts()}, key=str)
    hidden = [p.path for p in catalogue.problems if p.path.suffix.lower() in FONT_SUFFIXES]
    cache = Path(cache_directory)
    cache.mkdir(parents=True, exist_ok=True)

    root = ElementTree.Element("fontconfig")
    for folder in folders:
        ElementTree.SubElement(root, "dir").text = str(folder)
    ElementTree.SubElement(root, "cachedir").text = str(cache)
    if hidden:
        reject = ElementTree.SubElement(ElementTree.SubElement(root, "selectfont"), "rejectfont")
        for path in hidden:
            ElementTree.SubElement(reject, "glob").text = str(path)

    config = Path(directory) / CONFIG_NAME
    config.write_text(_HEADER + ElementTree.tostring(root, encoding="unicode"), encoding="utf-8")
    return JobFonts(config, {"FONTCONFIG_FILE": str(config)})
