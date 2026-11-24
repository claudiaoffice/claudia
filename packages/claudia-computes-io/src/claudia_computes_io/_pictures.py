"""The pictures floating on a sheet or a slide, as a file format needs them (D1233, D1477): where each is
(:mod:`._placed`), how it is turned, what it is called and says, and the bytes that are embedded for it.

A *picture* is an image object, or a container (its picture is the one last made of its text, D390). Computes
has no text boxes and no shapes (D1232), so these are the floating objects that are not charts. Both converters take
their pictures from here and differ only in how a file holds them (:mod:`.xlsx_pictures`, :mod:`.ods_pictures`).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from claudia_computes import WorkbookModel
from claudia_core import ImageAsset, Rasterise, blank_png
from claudia_odf_io import Loss, LossLog

from ._placed import Placed, placed_objects

#: The kinds of floating object that show a picture.
PICTURE_KINDS = ("image", "container")
MEDIA_TYPES = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "svg": "image/svg+xml",
}


@dataclass(frozen=True)
class WrittenPicture:
    """One picture ready for a file: where it is (``placed``), and what is shown.

    ``asset`` names what is shown, so that a picture shown twice is one part. ``data`` is what is embedded, in
    ``format``; an SVG that was drawn as a PNG is that PNG, and one that was not has ``svg`` beside a blank PNG (for a
    file that has no way to show an SVG on its own)."""

    placed: Placed
    asset: str
    format: str
    data: bytes
    svg: bytes | None = None

    @property
    def name(self) -> str:
        return self.placed.obj.body.name

    @property
    def description(self) -> str:
        """What it says to someone who cannot see it: nothing, for a decorative one."""
        body = self.placed.obj.body
        return "" if body.decorative else body.description

    @property
    def decorative(self) -> bool:
        return self.placed.obj.body.decorative


def _shown(model: WorkbookModel, placed: Iterable[Placed]) -> Iterator[tuple[Placed, ImageAsset | None]]:
    """The pictures among ``placed``, in their order, each with the image it shows (``None``: a container nothing has
    been drawn for, or an image the model lost)."""
    for one in placed:
        if one.obj.body.kind in PICTURE_KINDS:
            picture = model.picture_of(one.obj.body)
            yield one, (model.images.get(picture) if picture else None)


def picture_losses(model: WorkbookModel, *, rasterised: bool) -> tuple[Loss, ...]:
    """What cannot be kept of the pictures of ``model``: ``rendering-pending`` (a container nothing has been
    drawn for: left out), ``image-missing`` and ``svg-fallback`` (an SVG nothing draws as a PNG, ``rasterised``: other
    programs may show it empty or leave out what its style sheet gives)."""
    lost = LossLog()
    for one, asset in _shown(model, placed_objects(model)):
        if asset is None:
            lost.add("rendering-pending" if one.obj.body.kind == "container" else "image-missing")
        elif asset.format == "svg" and not rasterised:
            lost.add("svg-fallback")
    return lost.result()


def written_pictures(
    model: WorkbookModel, placed: Iterable[Placed], *, rasterise: Rasterise | None = None, svg_beside_png: bool
) -> tuple[WrittenPicture, ...]:
    """The pictures among ``placed`` for a file, in their order (those :func:`picture_losses` leaves out are not
    there).

    ``rasterise`` draws an SVG as a PNG, which every program then shows the same way. Without it an SVG is embedded as
    it is (``svg_beside_png`` false: a format that shows one, ods) or beside a blank PNG (true: xlsx)."""
    written: list[WrittenPicture] = []
    for one, asset in _shown(model, placed):
        if asset is None:
            continue
        width, height = round(one.width), round(one.height)
        data, fmt, svg, key = asset.data, asset.format, None, asset.id
        if asset.format == "svg":
            if rasterise is not None:
                data, fmt, key = rasterise(asset.data, width, height), "png", f"{asset.id}-{width}x{height}"
            elif svg_beside_png:
                data, fmt, svg = blank_png(width, height), "png", asset.data
        written.append(WrittenPicture(one, key, fmt, data, svg))
    return tuple(written)
