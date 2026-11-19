"""The pictures floating on a sheet, as a file format needs them (D1233): where each is pinned, how big it is, how it is
turned, what it is called and says, and the bytes that are embedded for it.

A *picture* is an image object, or a rendered container (its picture is the one last made of its text, D390). Computes
has no text boxes and no shapes (D1232), so these are the floating objects that are not charts. Both converters take
their pictures from here and differ only in how a file holds them (:mod:`.xlsx_pictures`, :mod:`.ods_pictures`).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from claudia_computes import SheetId, VisualObject, WorkbookModel
from claudia_core import ImageAsset, Rasterise, blank_png
from claudia_odf_io import Loss, LossLog

#: The kinds of floating object that show a picture.
PICTURE_KINDS = ("image", "rendered")
MEDIA_TYPES = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "svg": "image/svg+xml",
}


@dataclass(frozen=True)
class WrittenPicture:
    """One picture ready for a file.

    ``layer`` is its place in the stack of its sheet (the last is in front), which a chart on the same sheet shares.
    ``asset`` names what is shown, so that a picture shown twice is one part. ``data`` is what is embedded, in
    ``format``; an SVG that was drawn as a PNG is that PNG, and one that was not has ``svg`` beside a blank PNG (for a
    file that has no way to show an SVG on its own)."""

    sheet: SheetId
    sheet_name: str
    row: int
    col: int
    width: int
    height: int
    rotation: int
    name: str
    description: str
    decorative: bool
    layer: int
    asset: str
    format: str
    data: bytes
    svg: bytes | None = None


def _shown(model: WorkbookModel) -> Iterator[tuple[SheetId, int, VisualObject, ImageAsset | None]]:
    """Every picture of every sheet, bottom first: the object, its place in the stack of its sheet and the image it
    shows (``None``: a rendered container nothing has been drawn for, or an image the model lost)."""
    for sheet_id in model.sheets:
        for layer, object_id in enumerate(model.stack_of(str(sheet_id))):
            obj = model.get_object(object_id)
            if obj.body.kind in PICTURE_KINDS:
                picture = model.picture_of(obj.body)
                yield sheet_id, layer, obj, (model.images.get(picture) if picture else None)


def picture_losses(model: WorkbookModel, *, rasterised: bool) -> tuple[Loss, ...]:
    """What cannot be kept of the pictures of ``model``: ``rendering-pending`` (a rendered container nothing has been
    drawn for: left out), ``image-missing`` and ``svg-fallback`` (an SVG nothing draws as a PNG, ``rasterised``: other
    programs may show it empty or leave out what its style sheet gives)."""
    lost = LossLog()
    for _, _, obj, asset in _shown(model):
        if asset is None:
            lost.add("rendering-pending" if obj.body.kind == "rendered" else "image-missing")
        elif asset.format == "svg" and not rasterised:
            lost.add("svg-fallback")
    return lost.result()


def written_pictures(
    model: WorkbookModel, *, rasterise: Rasterise | None = None, svg_beside_png: bool
) -> tuple[WrittenPicture, ...]:
    """The pictures of ``model`` for a file, sheet by sheet, each bottom first (those :func:`picture_losses` leaves
    out are not there).

    ``rasterise`` draws an SVG as a PNG, which every program then shows the same way. Without it an SVG is embedded as
    it is (``svg_beside_png`` false: a format that shows one, ods) or beside a blank PNG (true: xlsx)."""
    written: list[WrittenPicture] = []
    for sheet_id, layer, obj, asset in _shown(model):
        if asset is None:
            continue
        body = obj.body
        data, fmt, svg = asset.data, asset.format, None
        if asset.format == "svg":
            if rasterise is not None:
                data, fmt = rasterise(asset.data, round(body.w), round(body.h)), "png"
            elif svg_beside_png:
                data, fmt, svg = blank_png(round(body.w), round(body.h)), "png", asset.data
        written.append(
            WrittenPicture(
                sheet_id,
                model.sheets[sheet_id].name,
                obj.anchor.row,
                obj.anchor.col,
                body.w,
                body.h,
                body.rotation,
                body.name,
                "" if body.decorative else body.description,
                body.decorative,
                layer,
                f"{asset.id}-{round(body.w)}x{round(body.h)}"
                if rasterise is not None and asset.format == "svg"
                else asset.id,
                fmt,
                data,
                svg,
            )
        )
    return tuple(written)
