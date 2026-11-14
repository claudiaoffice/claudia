"""What changed in a presentation that a converter does not write: the "unwritten changes" of an export (D299, D405),
and the losses odp and pptx share.

The facets a converter writes are listed per format (``ODP_WRITTEN``, ``PPTX_WRITTEN``); every slice that teaches a
converter another facet takes it off the list. A facet that is not written and differs between the baseline (an empty
presentation for a fresh file) and the model is a loss (:func:`claudia_odf_io.unwritten_changes`), under the code the
export already used for it where there is one (``KINDS``)."""

from __future__ import annotations

from collections.abc import Collection

from claudia_creates import SlideModel
from claudia_odf_io import Loss, LossLog, unwritten_changes

from ._notes import markdown_to_lines

#: The facets a converter writes, by the name :func:`facets` gives them.
ODP_WRITTEN: frozenset[str] = frozenset(
    {"slides", "notes", "styles", "palette", "shapes", "images", "objects", "renderings"}
)
PPTX_WRITTEN: frozenset[str] = ODP_WRITTEN

#: The code a facet is reported under, where an export reported it before the facets existed: a planned time (D343).
KINDS: dict[str, str] = {"times": "planned-time"}


def facets(model: SlideModel) -> dict[str, object]:
    """A presentation as the facets a converter writes or leaves out, in the order losses are reported: its own
    serialization (the planned times come one entry per slide that has one)."""
    return dict(model.serialize())


def slides_unwritten_changes(
    model: SlideModel, baseline: SlideModel | None, *, written: Collection[str]
) -> tuple[Loss, ...]:
    """What differs between ``baseline`` (``None``: an empty presentation, the start of a fresh export) and ``model``
    in a facet outside ``written``."""
    start = facets(baseline if baseline is not None else SlideModel())
    return unwritten_changes(start, facets(model), written=written, kinds=KINDS)


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
    for slide_id in model.slides:
        for feature in markdown_to_lines(model.notes_of(slide_id))[1] - {"heading"}:  # a heading is a bold line
            used[feature] = used.get(feature, 0) + 1
    for feature in sorted(used):
        losses.add(f"notes-{feature}", count=used[feature])
    return losses.result()
