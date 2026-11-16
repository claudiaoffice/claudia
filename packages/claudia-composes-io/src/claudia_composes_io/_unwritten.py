"""What changed in a text that a converter does not write: the "unwritten changes" of an export (D299, D405).

A converter writes some facets of a model into its file and not others. The facets it writes are listed per format
(``ODT_WRITTEN``, ``DOCX_WRITTEN``); every slice that teaches a converter another facet takes it off the list, and
nothing else has to change. A facet that is not written and differs from where the export starts -- the baseline of a
patch, or an empty text for a fresh file -- is a loss (:func:`claudia_odf_io.unwritten_changes`)."""

from __future__ import annotations

from collections.abc import Collection

from claudia_composes import Block, TextModel
from claudia_odf_io import Loss, unwritten_changes

from ._pictures import PICTURE_KINDS

#: The facets a converter writes, by the name :func:`facets` gives them.
_WRITTEN_BY_BOTH = {"blocks", "suggestions", "lists", "schemes", "page", "language", "styles", "palette", "pictures"}
ODT_WRITTEN: frozenset[str] = frozenset(_WRITTEN_BY_BOTH)
DOCX_WRITTEN: frozenset[str] = frozenset(_WRITTEN_BY_BOTH)


def facets(model: TextModel) -> dict[str, object]:
    """A text as the facets a converter writes or leaves out, in the order losses are reported. The blocks count by
    their id, style and words (who wrote which run has its own loss code), the lists by their definitions and the
    list each block is an item of; the rest is the model's own serialization."""
    data = model.serialize()
    return {
        "blocks": [(b.id, b.style, b.text) for b in model.blocks],
        "styles": data["styles"],
        "palette": data["palette"],
        "page": tuple(sorted(data["page"].items())),  # one setting, however many of its numbers differ
        "language": data["language"],
        "lists": _lists(data["lists"], model.blocks),
        "suggestions": data["suggestions"],
        **_objects(model),
    }


def _lists(definitions: object, blocks: list[Block]) -> dict[str, object]:
    found: dict[str, object] = {f"list:{each['id']}": each for each in definitions}  # type: ignore[attr-defined]
    for block in blocks:
        if block.item is not None:
            found[f"item:{block.id}"] = (block.item.list, block.item.level)
    return found


def text_unwritten_changes(
    model: TextModel, baseline: TextModel | None, *, written: Collection[str]
) -> tuple[Loss, ...]:
    """What differs between ``baseline`` (``None``: an empty text, the start of a fresh export) and ``model`` in a
    facet outside ``written``."""
    return unwritten_changes(
        facets(baseline if baseline is not None else TextModel([])), facets(model), written=written
    )


def _objects(model: TextModel) -> dict[str, object]:
    """The objects of a text as the facets a converter writes or leaves out: the pictures (an image, a rendered text
    container, and what draws them), and the other objects with the outlines that shape them."""
    data = model.serialize()
    picture_ids = {obj.id for obj in model.objects.values() if obj.body.kind in PICTURE_KINDS}
    return {
        "pictures": {
            "objects": [each for each in data["objects"] if each["id"] in picture_ids],
            "images": data["images"],
            "renderings": data["renderings"],
        },
        "objects": [each for each in data["objects"] if each["id"] not in picture_ids],
        "shapes": data["shapes"],
    }
