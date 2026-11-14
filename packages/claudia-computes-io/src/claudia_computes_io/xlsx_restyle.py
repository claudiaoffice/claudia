"""Writing a changed look into an edited xlsx file (E6.18, D379, after D371).

An edit of an imported file changes the original's XML only where something changed (D371). A cell that got another
look gets a new entry in ``cellXfs`` -- with its font, fill, border and number format appended to their lists -- and
points at it; nothing the file had is changed or renumbered, so every other cell, every conditional format and every
named style keeps exactly what it pointed at. A look is added once, however many cells take it. Its named style is
the file's style of that name (Normal for Body text); a named style the file does not have yet is added to
``cellStyleXfs`` and ``cellStyles``. A row or a column whose look changed gets it as its format (``s`` and
``customFormat`` on the row, ``style`` on the ``col``).
"""

from __future__ import annotations

from typing import Any

from lxml import etree
from openpyxl.xml.functions import tostring

from claudia_computes import WorkbookModel
from claudia_computes.cellstyles import DEFAULT_CELL_STYLE
from claudia_computes.numformats import BUILTIN

from .cell_looks import GENERAL, CellLook, LookExport, Restyling
from .xlsx_read import NS, parse_xml
from .xlsx_write_looks import MAX_STYLED_ROWS, _Parts

_X = NS["x"]
_STYLES = "xl/styles.xml"
_FIRST_OWN_FORMAT = 164
_EMPTY = (
    f'<styleSheet xmlns="{_X}"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
    '</fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
)
#: Where each list goes in ``styleSheet`` when a file lacks it (the schema's order).
_ORDER = ("numFmts", "fonts", "fills", "borders", "cellStyleXfs", "cellXfs", "cellStyles", "dxfs", "tableStyles",
          "colors", "extLst")  # fmt: skip


def _namespaced(element: Any) -> etree._Element:  # noqa: ANN401 (openpyxl's xml.etree element)
    """openpyxl's element (no namespace) in the spreadsheet namespace, as lxml's."""
    made = etree.fromstring(tostring(element))
    for node in made.iter():
        if isinstance(node.tag, str) and not node.tag.startswith("{"):
            node.tag = f"{{{_X}}}{node.tag}"
    etree.cleanup_namespaces(made)
    return made


class StylesPatch:
    """``xl/styles.xml`` of an edited file, taking new looks."""

    def __init__(self, parts: dict[str, bytes], model: WorkbookModel) -> None:
        self.parts = parts
        self.looks = LookExport(model)
        self.root = parse_xml(parts.get(_STYLES, _EMPTY.encode()))
        self.changed = False
        self._xfs: dict[CellLook, int] = {}
        self._pieces: dict[tuple[str, bytes], int] = {}
        self._named: dict[str, int] = {}
        for element in self.root.iterfind("x:cellStyles/x:cellStyle", NS):
            self._named.setdefault(element.get("name", "").casefold(), int(element.get("xfId", "0")))
            if element.get("builtinId") == "0":
                self._normal = int(element.get("xfId", "0"))

    def _list(self, name: str) -> etree._Element:
        found = self.root.find(f"x:{name}", NS)
        if found is not None:
            return found
        made = etree.Element(f"{{{_X}}}{name}")
        later = next((self.root.find(f"x:{n}", NS) for n in _ORDER[_ORDER.index(name) + 1 :]
                      if self.root.find(f"x:{n}", NS) is not None), None)  # fmt: skip
        if later is None:
            self.root.append(made)
        else:
            later.addprevious(made)
        return made

    def _append(self, name: str, element: etree._Element) -> int:
        """Add ``element`` to the list ``name`` (once: the same piece twice is one) and return its place."""
        key = (name, etree.tostring(element))
        if key not in self._pieces:
            holder = self._list(name)
            holder.append(element)
            holder.set("count", str(len(holder)))
            self._pieces[key] = len(holder) - 1
        return self._pieces[key]

    def _format(self, code: str) -> int:
        if code == GENERAL:
            return 0
        builtin = next((number for number, known in BUILTIN.items() if known == code), None)
        if builtin is not None:
            return builtin
        formats = self._list("numFmts")
        for existing in formats.iterfind("x:numFmt", NS):
            if existing.get("formatCode") == code:
                return int(existing.get("numFmtId", "0"))
        taken = [int(f.get("numFmtId", "0")) for f in formats.iterfind("x:numFmt", NS)]
        number = max([_FIRST_OWN_FORMAT - 1, *taken]) + 1
        etree.SubElement(formats, f"{{{_X}}}numFmt", numFmtId=str(number), formatCode=code)
        formats.set("count", str(len(formats)))
        return number

    def _xf(self, look: CellLook, parent: int | None) -> etree._Element:
        parts = _Parts(look)
        attributes = {
            "numFmtId": str(self._format(look.code)),
            "fontId": str(self._append("fonts", _namespaced(parts.font.to_tree()))),
            "fillId": str(self._append("fills", _namespaced(parts.fill.to_tree()))),
            "borderId": str(self._append("borders", _namespaced(parts.border.to_tree()))),
        }
        if parent is not None:
            attributes |= {"xfId": str(parent), "applyNumberFormat": "1", "applyFont": "1", "applyFill": "1",
                           "applyBorder": "1", "applyAlignment": "1"}  # fmt: skip
        xf = etree.Element(f"{{{_X}}}xf", attributes)
        alignment = parts.alignment.to_tree()
        if alignment is not None:
            xf.append(_namespaced(alignment))
        return xf

    def _named_style(self, style_id: str) -> int:
        """The place in ``cellStyleXfs`` of the file's named style for ``style_id``, added when the file lacks it."""
        if style_id == DEFAULT_CELL_STYLE:
            return getattr(self, "_normal", 0)
        name = self.looks.model.styles.get(style_id).name
        if name.casefold() not in self._named:
            holder = self._list("cellStyleXfs")
            holder.append(self._xf(self.looks.named_look(style_id), None))
            holder.set("count", str(len(holder)))
            index = len(holder) - 1
            styles = self._list("cellStyles")
            etree.SubElement(styles, f"{{{_X}}}cellStyle", name=name, xfId=str(index))
            styles.set("count", str(len(styles)))
            self._named[name.casefold()] = index
        return self._named[name.casefold()]

    def index(self, look: CellLook) -> int:
        """The place in ``cellXfs`` of an entry for ``look``, added the first time."""
        if look not in self._xfs:
            if look == self.looks.named_look(DEFAULT_CELL_STYLE):
                self._xfs[look] = 0
            else:
                xf = self._xf(look, self._named_style(look.parent))
                holder = self._list("cellXfs")
                holder.append(xf)
                holder.set("count", str(len(holder)))
                self._xfs[look] = len(holder) - 1
                self.changed = True
        return self._xfs[look]

    def finish(self) -> None:
        """Put the changed styles into the parts (nothing, when no look was added)."""
        if self.changed:
            self.parts[_STYLES] = etree.tostring(self.root, xml_declaration=True, encoding="UTF-8", standalone=True)


def restyle_sheet(sheet, styles: StylesPatch, changes: Restyling) -> None:  # noqa: ANN001 (a SheetPatch)
    """Point the cells, rows and columns of one sheet whose look changed at their new looks (rows up to
    ``MAX_STYLED_ROWS`` of one run, as for a new file)."""
    for (row, col), look in changes.cells.items():
        sheet.restyle(row, col, styles.index(look))
    for first, last, line in changes.rows:
        for row in range(first, min(last, first + MAX_STYLED_ROWS - 1) + 1):
            sheet.restyle_row(row, None if line is None else styles.index(line))
    for first, last, line in changes.columns:
        sheet.restyle_columns(first, last, None if line is None else styles.index(line))
