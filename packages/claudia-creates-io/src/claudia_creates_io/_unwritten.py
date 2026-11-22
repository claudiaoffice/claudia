"""What changed in a presentation that a converter does not write: the "unwritten changes" of an export (D299, D405),
and the losses odp and pptx share.

The facets a converter writes are listed per format (``ODP_WRITTEN``, ``PPTX_WRITTEN``); every slice that teaches a
converter another facet takes it off the list. A facet that is not written and differs between the baseline (an empty
presentation for a fresh file) and the model is a loss (:func:`claudia_odf_io.unwritten_changes`), under the code the
export already used for it where there is one (``KINDS``)."""

from __future__ import annotations

from collections.abc import Collection

from claudia_core.page import DEFAULT_MARGIN
from claudia_creates import PrintSetup, SlideModel
from claudia_odf_io import Loss, LossLog, unwritten_changes

from ._notes import markdown_to_lines
from ._styling import unwritten_properties

#: The facets a converter writes, by the name :func:`facets` gives them. ``styles`` is written *in part*: a style's
#: font, size, colour, weight, slant and alignment, a shape's fill and outline. What else a style says is reported
#: property by property (:func:`._styling.unwritten_properties`, CODE-58), not as a facet.
PPTX_WRITTEN: frozenset[str] = frozenset(
    {"slides", "notes", "styles", "palette", "shapes", "images", "objects", "containers", "lists", "schemes"}
)
ODP_WRITTEN: frozenset[str] = PPTX_WRITTEN | {"language"}

#: The code a facet is reported under, where an export reported it before the facets existed: a planned time (D343).
KINDS: dict[str, str] = {"times": "planned-time"}


def _beyond_the_layout(setup: PrintSetup) -> dict[str, object]:
    """What of a print setup a format that keeps the layout, the paper and the orientation cannot: margins other than
    the paper's own, and the page numbers."""
    page = setup.page
    own = 0 if page.paper == "slide" else DEFAULT_MARGIN
    margins = [page.margin_top, page.margin_right, page.margin_bottom, page.margin_left]
    return {"margins": None if margins == [own] * 4 else margins, "page_numbers": page.page_numbers}


def facets(model: SlideModel, *, keeps_print_layout: bool = False) -> dict[str, object]:
    """A presentation as the facets a converter writes or leaves out, in the order losses are reported: its own
    serialization (the planned times come one entry per slide that has one). For a format that writes how the slides
    are laid out and on which paper, ``"print_setup"`` is what of it the format cannot write."""
    data = dict(model.serialize())
    if keeps_print_layout:
        data["print_setup"] = _beyond_the_layout(model.print_setup)
    return data


def slides_unwritten_changes(
    model: SlideModel, baseline: SlideModel | None, *, written: Collection[str], keeps_print_layout: bool = False
) -> tuple[Loss, ...]:
    """What differs between ``baseline`` (``None``: an empty presentation, the start of a fresh export) and ``model``
    in a facet outside ``written``."""
    start = facets(baseline if baseline is not None else SlideModel(), keeps_print_layout=keeps_print_layout)
    changed = unwritten_changes(
        start, facets(model, keeps_print_layout=keeps_print_layout), written=written, kinds=KINDS
    )
    return (*changed, *unwritten_properties(model, baseline))


def authored_objects(model: SlideModel) -> int:
    """How many objects have words that somebody wrote: a presentation file does not keep who wrote which words."""
    return sum(
        1
        for obj in model.objects.values()
        if obj.body.paragraph is not None and any(run.author is not None for run in obj.body.paragraph.runs)
    )


def notes_losses(model: SlideModel) -> tuple[Loss, ...]:
    """``"notes-link"``, ``"notes-image"``, ``"notes-code"`` and ``"notes-quote"``, each with how many slides use what
    the file shows only as plain words (the speaker notes are written as paragraphs with bold and italic runs)."""
    losses = LossLog()
    used: dict[str, int] = {}
    for slide_id in model.order:
        for feature in markdown_to_lines(model.notes_of(slide_id))[1] - {"heading"}:  # a heading is a bold line
            used[feature] = used.get(feature, 0) + 1
    for feature in sorted(used):
        losses.add(f"notes-{feature}", count=used[feature])
    return losses.result()
