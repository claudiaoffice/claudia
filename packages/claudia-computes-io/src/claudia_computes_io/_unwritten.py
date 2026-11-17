"""What changed in a workbook that a converter does not write: the "unwritten changes" of an edit-and-reexport
(D299, D405).

The facets a converter writes are listed per format (``ODS_WRITTEN``, ``XLSX_WRITTEN``); every slice that teaches a
converter another facet takes it off the list. A facet that is not written and differs between the baseline and the
model is a loss (:func:`claudia_odf_io.unwritten_changes`), under the code the fresh export already uses for it where
there is one (``KINDS``)."""

from __future__ import annotations

from collections.abc import Collection

from claudia_computes import WorkbookModel
from claudia_odf_io import Loss, unwritten_changes

from ._named import unheld

#: The facets a converter writes, by the name :func:`facets` gives them: the cells with their looks, and the look
#: definitions they name.
ODS_WRITTEN: frozenset[str] = frozenset({"sheets", "styles", "palette", "number_formats", "names", "layout", "charts"})
XLSX_WRITTEN: frozenset[str] = frozenset({"sheets", "styles", "palette", "number_formats", "names", "layout", "charts"})

#: The code a facet is reported under, where an export reported it before the facets existed.
KINDS: dict[str, str] = {
    "layout": "layout",
    "charts": "chart",
    "objects": "object",
    "names": "name",
    "pivots": "pivot-table",
}


def facets(model: WorkbookModel) -> dict[str, object]:
    """A workbook as the facets a converter writes or leaves out, in the order losses are reported. The sheets count
    by their name, cells and looks; the widths and heights of rows and columns are a facet of their own (only a sheet
    that has any), the charts shown (a tab, or a diagram floating on a sheet, each with its definition) are one facet
    and the other floating objects, with the assets they use, another."""
    data = model.serialize()
    sheets = data["sheets"]
    return {
        "sheets": {s["id"]: (s["name"], s["cells"], s["cell_styles"]) for s in sheets},
        "styles": data["styles"],
        "palette": data["palette"],
        "number_formats": data["number_formats"],
        "layout": {s["id"]: (s["row_heights"], s["col_widths"]) for s in sheets if s["row_heights"] or s["col_widths"]},
        "names": data["names"],
        "charts": _charts(data),
        "pivots": _pivots(model),
        "objects": [
            *(each for each in data["objects"] if each.get("diagram") is None),
            *(("image", each) for each in data["images"]),
            *(("shape", each) for each in data["shapes"]),
            *(("rendering", each) for each in data["renderings"]),
        ],
    }


def _pivots(model: WorkbookModel) -> dict[str, object]:
    """The pivot tables a workbook has, each as its definition: the cells they fill are cells of the sheets, written
    with those (a file that keeps its own pivot is stale when a definition differs from the file's, D628)."""
    return {entry.name: entry.to_data() for entry in model.pivots.sorted()}


def _charts(data: dict) -> dict[str, object]:
    """The charts a workbook shows, each with the definition it draws: a tab, or a diagram floating on a sheet."""
    definitions = {each["id"]: each for each in data["diagrams"]}
    shown: dict[str, object] = {f"tab {tab['id']}": (tab, definitions.get(tab["spec_id"])) for tab in data["charts"]}
    for each in data["objects"]:
        if each.get("diagram") is not None:
            shown[f"object {each['id']}"] = (each, definitions.get(each["diagram"]))
    return shown


def workbook_unwritten_changes(
    model: WorkbookModel, baseline: WorkbookModel | None, *, written: Collection[str]
) -> tuple[Loss, ...]:
    """What differs between ``baseline`` (``None``: an empty workbook, the start of a fresh export) and ``model`` in a
    facet outside ``written``."""
    start = facets(baseline if baseline is not None else WorkbookModel())
    found = unwritten_changes(start, facets(model), written=written, kinds=KINDS)
    if "names" not in written:
        return found
    return in_order((*found, *unheld(model, baseline).result()))


def in_order(losses: tuple[Loss, ...]) -> tuple[Loss, ...]:
    """Losses by the facet they come from: the names a file cannot hold come where the facet of the names did."""
    order = ("layout", "name", "chart", "object", "pivot-table")
    return tuple(sorted(losses, key=lambda loss: order.index(loss.kind) if loss.kind in order else len(order)))
