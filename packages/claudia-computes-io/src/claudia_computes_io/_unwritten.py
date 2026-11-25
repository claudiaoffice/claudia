"""What changed in a workbook that a converter does not write: the "unwritten changes" of an edit-and-reexport
(D299, D405).

The facets a converter writes are listed per format (``ODS_WRITTEN``, ``XLSX_WRITTEN``); every slice that teaches a
converter another facet takes it off the list. A facet that is not written and differs between the baseline and the
model is a loss (:func:`claudia_odf_io.unwritten_changes`), under the code the fresh export already uses for it where
there is one (``KINDS``)."""

from __future__ import annotations

from collections.abc import Collection
from typing import cast

from claudia_computes import WorkbookModel
from claudia_odf_io import Loss, is_written, unwritten_changes

from ._named import unheld
from ._pictures import PICTURE_KINDS

#: The facets a converter writes, by the name :func:`facets` gives them: the cells with their looks, and the look
#: definitions they name.
ODS_WRITTEN: frozenset[str] = frozenset(
    {"sheets", "styles", "palette", "number_formats", "names", "layout", "charts", "pictures"}
)
XLSX_WRITTEN: frozenset[str] = frozenset(
    {"sheets", "styles", "palette", "number_formats", "names", "layout", "charts", "pictures"}
)
#: What only a fresh export writes in full: a pivot table (a kept file is given only the ones defined since the import)
#: and a slide's text boxes and shapes (a workbook with a slide is always written anew).
FRESH_ONLY: frozenset[str] = frozenset({"pivots", "boxes"})

#: The code a facet is reported under, where an export reported it before the facets existed.
KINDS: dict[str, str] = {
    "layout": "layout",
    "charts": "chart",
    "objects": "object",
    "pictures": "object",
    "boxes": "object",
    "names": "name",
    "pivots": "pivot-table",
}


def facets(model: WorkbookModel) -> dict[str, object]:
    """A workbook as the facets a converter writes or leaves out, in the order losses are reported. The sheets count
    by their name, cells and looks; the widths and heights of rows and columns are a facet of their own (only a sheet
    that has any), the charts shown (each with its definition) are one facet
    and the pictures (an image or a container, with the assets they show) another, the text boxes and shapes of the
    slides (with the outlines they use) another (D1479), and the other floating objects (a sheet has no text boxes and
    shapes, D1232, but a model may hold them), with what they use, a last."""
    data = model.serialize()
    sheets = data["sheets"]
    boxes = {obj.id for obj in model.objects.values() if obj.anchor.holder in model.slides and is_written(obj)}
    outlines = {model.get_object(each).body.shape for each in boxes}
    return {
        "sheets": {s["id"]: (s["name"], s["cells"], s["cell_styles"]) for s in sheets},
        "styles": data["styles"],
        "palette": data["palette"],
        "number_formats": data["number_formats"],
        "layout": {s["id"]: (s["row_heights"], s["col_widths"]) for s in sheets if s["row_heights"] or s["col_widths"]},
        "names": data["names"],
        "charts": _charts(data),
        "pivots": _pivots(model),
        "pictures": [
            *(each for each in data["objects"] if each["kind"] in PICTURE_KINDS),
            *(("image", each) for each in data["images"]),
            *(("container", each) for each in data["containers"]),
        ],
        "boxes": [
            *(each for each in data["objects"] if each["id"] in boxes),
            *(("shape", each) for each in data["shapes"] if each["id"] in outlines),
        ],
        "objects": [
            *(
                each
                for each in data["objects"]
                if each["kind"] != "chart" and each["kind"] not in PICTURE_KINDS and each["id"] not in boxes
            ),
            *(("shape", each) for each in data["shapes"] if each["id"] not in outlines),
        ],
    }


def _pivots(model: WorkbookModel) -> dict[str, object]:
    """The pivot tables a workbook has, each as its definition: the cells they fill are cells of the sheets, written
    with those (a file that keeps its own pivot is stale when a definition differs from the file's, D628)."""
    return {entry.name: entry.to_data() for entry in model.pivots.sorted()}


def _charts(data: dict) -> dict[str, object]:
    """The charts a workbook shows, each with the definition it draws: a chart on a sheet or a slide."""
    definitions = {each["id"]: each for each in data["charts"]}
    return {
        f"object {each['id']}": (each, definitions.get(each["ref"]))
        for each in data["objects"]
        if each["kind"] == "chart"
    }


def workbook_unwritten_changes(
    model: WorkbookModel, baseline: WorkbookModel | None, *, written: Collection[str]
) -> tuple[Loss, ...]:
    """What differs between ``baseline`` (``None``: an empty workbook, the start of a fresh export) and ``model`` in a
    facet outside ``written``. A kept file is given the pivots defined since the import (CODE-70): of its pivots, only
    one of the file that was changed or removed is reported."""
    start, end = facets(baseline if baseline is not None else WorkbookModel()), facets(model)
    if baseline is not None:
        known = cast("dict[str, object]", start["pivots"])
        end["pivots"] = {name: each for name, each in cast("dict[str, object]", end["pivots"]).items() if name in known}
    found = unwritten_changes(start, end, written=written, kinds=KINDS)
    if "names" not in written:
        return found
    return in_order((*found, *unheld(model, baseline).result()))


def in_order(losses: tuple[Loss, ...]) -> tuple[Loss, ...]:
    """Losses by the facet they come from: the names a file cannot hold come where the facet of the names did."""
    order = ("layout", "name", "chart", "object", "pivot-table")
    return tuple(sorted(losses, key=lambda loss: order.index(loss.kind) if loss.kind in order else len(order)))
