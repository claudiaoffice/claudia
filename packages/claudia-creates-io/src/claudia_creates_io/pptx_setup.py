"""How a pptx says how it is printed and which language it is in (D461).

The print layout is what ``p:prnPr`` of ``presProps.xml`` says is printed (``prnWhat``: ``slides`` or ``handouts2`` to
``handouts9``); the paper is the size of the notes page (``p:notesSz``), which is the page handouts and notes are
printed on, its long side first when the page lies on its side. The margins and the page numbers of the setup have no
place in a pptx. A file that was not made by claudia often has a notes page of PowerPoint's own size and a layout of
``slides``: that says nothing of how *claudia* should print it, so it reads as the setup a new presentation has.

The language is the ``lang`` attribute of the runs of the words (:func:`speak`); the language of a file is the one most
of its words are in (:func:`spoken`).
"""

from __future__ import annotations

from collections import Counter

from lxml import etree
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

from claudia_core import PAPERS, LanguageError, PageSetup, PageSetupError, normalize_language
from claudia_core.page import DEFAULT_MARGIN
from claudia_creates import PrintSetup

_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_EMU_PER_MPT = 12.7
#: How far a size may be from a preset's and still be that paper (a little over half a millimetre), in mpt.
_TOLERANCE = 1500
#: The notes page of a new python-pptx presentation and of PowerPoint's own default: no statement about the paper.
_POWERPOINT_NOTES = (6858000, 9144000)
#: ``prnWhat`` for each layout, and back (what is printed that has no layout of ours is printed as slides).
_WHAT = {"slides": "slides", **{f"handouts-{n}": f"handouts{n}" for n in (2, 3, 4, 6, 9)}}
_LAYOUT = {what: layout for layout, what in _WHAT.items()}


def _q(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


def _sides(page: PageSetup) -> tuple[int, int]:
    return (page.height, page.width) if page.orientation == "landscape" else (page.width, page.height)


def _props(prs) -> object | None:  # noqa: ANN001 (python-pptx's own presentation class)
    try:
        return prs.part.part_related_by(RT.PRES_PROPS)
    except KeyError:
        return None


def part_names(prs) -> set[str]:  # noqa: ANN001
    """The names of the parts :func:`write_print_setup` changes in ``prs``, as the package knows them."""
    names = {str(prs.part.partname).lstrip("/")}
    if (props := _props(prs)) is not None:
        names.add(str(props.partname).lstrip("/"))  # type: ignore[attr-defined]
    return names


def write_print_setup(prs, setup: PrintSetup) -> bool:  # noqa: ANN001
    """Make ``prs`` print the way ``setup`` says (its layout, paper and orientation); ``False`` when it has no
    ``presProps`` part to say the layout in."""
    props = _props(prs)
    if props is None:
        return False
    width, height = (round(side * _EMU_PER_MPT) for side in _sides(setup.page))
    notes = prs.part._element.find(_q(_P, "notesSz"))
    if notes is None:
        return False
    notes.set("cx", str(width))
    notes.set("cy", str(height))
    root = etree.fromstring(props.blob)  # type: ignore[attr-defined]
    printing = root.find(_q(_P, "prnPr"))
    if printing is None:
        printing = etree.Element(_q(_P, "prnPr"))
        later = next((child for child in root if etree.QName(child).localname in ("showPr", "clrMru", "extLst")), None)
        if later is None:
            root.append(printing)
        else:
            later.addprevious(printing)
    printing.set("prnWhat", _WHAT[setup.layout])
    props._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)  # type: ignore[attr-defined]  # noqa: SLF001
    return True


def read_print_setup(prs) -> PrintSetup:  # noqa: ANN001
    """The setup ``prs`` says (see the module); the setup of a new presentation for what it does not say."""
    fallback = PrintSetup()
    props = _props(prs)
    notes = prs.part._element.find(_q(_P, "notesSz"))
    printing = etree.fromstring(props.blob).find(_q(_P, "prnPr")) if props is not None else None  # type: ignore[attr-defined]
    if printing is None or notes is None:
        return fallback
    layout = _LAYOUT.get(printing.get("prnWhat", "slides"), "slides")
    try:
        sides = (int(notes.get("cx", "")), int(notes.get("cy", "")))
    except ValueError:
        return PrintSetup(layout, fallback.page)
    if sides == _POWERPOINT_NOTES:
        return PrintSetup(layout, fallback.page)
    return PrintSetup(layout, _page_of(sides) or fallback.page)


def _page_of(emu: tuple[int, int]) -> PageSetup | None:
    across, down = (round(side / _EMU_PER_MPT) for side in emu)
    short, long = sorted((across, down))
    lying = across > down
    try:
        for paper, (width, height) in PAPERS.items():
            if abs(width - short) <= _TOLERANCE and abs(height - long) <= _TOLERANCE:
                margin = 0 if paper == "slide" else DEFAULT_MARGIN
                return PageSetup.preset(
                    paper,
                    orientation="landscape" if lying else "portrait",
                    margin_top=margin,
                    margin_right=margin,
                    margin_bottom=margin,
                    margin_left=margin,
                )
        return PageSetup("custom", short, long, "landscape" if lying else "portrait")
    except PageSetupError:
        return None


def speak(runs, language: str | None) -> None:  # noqa: ANN001
    """Say ``language`` on every run of ``runs`` (python-pptx's own run objects)."""
    if language is not None:
        for run in runs:
            run._r.get_or_add_rPr().set("lang", language)  # noqa: SLF001


def spoken(runs) -> str | None:  # noqa: ANN001
    """The language most of ``runs`` say, or ``None`` when none says one."""
    found: Counter[str] = Counter()
    for run in runs:
        tag = run._r.rPr.get("lang") if run._r.rPr is not None else None  # noqa: SLF001
        if tag:
            try:
                found[normalize_language(tag)] += 1
            except LanguageError:
                continue
    return found.most_common(1)[0][0] if found else None
