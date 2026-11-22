"""A container on a sheet: it hangs from a cell and holds still, like any computes object (D390, D177).

The object layer is shared, so the long story is told in ``claudia-creates``; this is what a workbook must do the
same way: keep the text in its snapshot, bring it back from its log, and refuse what does not make sense."""

import pytest
from conftest import add, build, image_asset, reopen

from claudia_computes import WorkbookModel
from claudia_core import Batch, ContainerDefinition, DefineAsset, UpdateAsset


def container(object_id="c1", **changes):
    fields = {"id": object_id, "kind": "container", "row": 3, "col": 2, "w": 320, "h": 200, "style": "plain-image"}
    return build(**{**fields, "container": "r1", "paragraph": None, **changes})


def definition(**changes) -> ContainerDefinition:
    return ContainerDefinition(**{"id": "r1", "type": "latex", "source": r"\frac{a}{b}", **changes})


def test_a_container_hangs_from_a_cell_with_its_text_in_the_workbook(doc):
    doc.execute(Batch((DefineAsset("container", definition().to_data()), add(container()))), author="ana")
    placed = doc.model.get_object("c1")
    assert (placed.anchor.row, placed.anchor.col) == (3, 2) and placed.body.container == "r1"
    doc.undo("ana")
    assert doc.model.objects == {} and doc.model.containers == {}


def test_a_container_of_a_definition_the_workbook_does_not_know_is_refused(doc):
    with pytest.raises(ValueError, match="does not know the container"):
        doc.execute(add(container()), author="ana")


def test_the_text_survives_a_snapshot_a_replay_and_a_snapshot_from_before(doc):
    asset = image_asset()
    steps = (
        DefineAsset("image", asset.to_data()),
        DefineAsset("container", definition(image=asset.id, renderer="latex 1").to_data()),
        add(container()),
    )
    doc.execute(Batch(steps), author="ana")
    doc.execute(
        UpdateAsset("container", "r1", definition(source="x^2", image=asset.id, renderer="latex 1").to_data()),
        author="ana",
    )
    assert reopen(doc).model.containers == doc.model.containers
    state = doc.model.serialize()
    assert WorkbookModel.restore(state).containers == doc.model.containers
    del state["containers"]
    assert WorkbookModel.restore(state).containers == {}
