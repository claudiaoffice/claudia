"""Which objects of a text are pictures a converter writes (D464): an image, and a container, which is
the picture last made from its text (D394)."""

from __future__ import annotations

from claudia_composes import TextModel
from claudia_core import ImageAsset, VisualObject
from claudia_odf_io import LossLog

#: The kinds of object a converter writes as a picture.
PICTURE_KINDS = frozenset({"image", "container"})


def pictures_of(model: TextModel, paragraph_id: str) -> list[tuple[VisualObject, ImageAsset]]:
    """The pictures hanging from the paragraph ``paragraph_id`` with the asset each shows, the one in front last. A
    container nothing has been drawn for is not among them (``rendering-pending`` says so)."""
    found = []
    for object_id in model.stack_of(paragraph_id):
        obj = model.get_object(object_id)
        picture = model.picture_of(obj.body) if obj.body.kind in PICTURE_KINDS else None
        if picture is not None and picture in model.images:
            found.append((obj, model.images[picture]))
    return found


def all_pictures(model: TextModel) -> dict[str, tuple[VisualObject, ImageAsset]]:
    """Every picture of the text by object id (see :func:`pictures_of`)."""
    return {obj.id: (obj, asset) for paragraph in model.paragraphs for obj, asset in pictures_of(model, paragraph.id)}


def picture_losses(
    model: TextModel, losses: LossLog, *, vector_loss: str | None = None, only_containers: bool = False
) -> None:
    """Say in ``losses`` what the files cannot keep of the pictures of ``model``: ``rendering-pending`` for a rendered
    text container nothing has been drawn for (it is left out) and, when ``vector_loss`` is given, that code for each
    picture that is an SVG (only the containers when ``only_containers``): a program that cannot draw an SVG
    shows an empty picture."""
    for obj in model.objects.values():
        if obj.body.kind not in PICTURE_KINDS:
            continue
        picture = model.picture_of(obj.body)
        if picture is None or picture not in model.images:
            if obj.body.kind == "container":
                losses.add("rendering-pending")
        elif (
            vector_loss
            and model.images[picture].format == "svg"
            and (obj.body.kind == "container" or not only_containers)
        ):
            losses.add(vector_loss)
