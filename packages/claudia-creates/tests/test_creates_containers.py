"""A container on a slide: the text a person writes, kept as the truth, and its picture (D390).

The object layer is shared (D177), so what is checked here for slides is true in the other two apps too; their tests
(``claudia-computes``, ``claudia-composes``) check that they hold, read back and replay it the same way."""

import pytest
from conftest import SLIDE, add, build, image_asset, reopen, text_box

from claudia_core import (
    AssetsChanged,
    Batch,
    ContainerDefinition,
    DefineAsset,
    ForgetAsset,
    RemoveObject,
    UpdateAsset,
)
from claudia_creates import SlideModel


def container(object_id: str = "c1", definition: str = "r1", **changes):
    fields = {
        "id": object_id,
        "slide": SLIDE,
        "kind": "container",
        "style": "plain-image",
        "x": 100,
        "y": 100,
        "w": 400,
        "h": 240,
        "container": definition,
        "paragraph": None,
    }
    return build(**{**fields, **changes})


def definition(**changes) -> ContainerDefinition:
    fields = {"id": "r1", "type": "mermaid", "source": "flowchart LR\n  A --> B"}
    return ContainerDefinition(**{**fields, **changes})


def put_container(doc, object_id="c1", **changes):
    """What a server does: take the definition into the document and put the object on the slide, in one step."""
    return doc.execute(
        Batch((DefineAsset("container", definition(**changes).to_data()), add(container(object_id)))), author="ana"
    )


def collect(doc):
    seen = []
    doc.subscribe(seen.append)
    return seen


# -- the whole story: write, place, edit, remove, undo -------------------------------------------------------------
def test_a_container_is_added_with_its_definition_and_undo_takes_both_away(doc):
    put_container(doc)
    assert doc.model.get("c1").body.container == "r1"
    assert doc.model.containers["r1"].source.startswith("flowchart")
    doc.undo("ana")
    assert doc.model.objects == {} and doc.model.containers == {}


def test_redo_brings_the_container_and_its_text_back(doc):
    put_container(doc)
    doc.undo("ana")
    doc.redo("ana")
    assert doc.model.containers["r1"].type == "mermaid" and "c1" in doc.model.objects


def test_an_object_cannot_point_at_a_definition_the_document_does_not_know(doc):
    with pytest.raises(ValueError, match="does not know the container"):
        doc.execute(add(container()), author="ana")


def test_a_container_object_needs_its_definition_and_nothing_else_of_other_kinds(doc):
    doc.execute(DefineAsset("container", definition().to_data()), author="ana")
    with pytest.raises(ValueError, match="needs a container"):
        doc.execute(add(container(container=None)), author="ana")
    with pytest.raises(ValueError, match="no text"):
        from claudia_core import paragraph_for

        doc.execute(add(container(paragraph=paragraph_for("c1", "body-text", "x"))), author="ana")


def test_other_kinds_of_object_do_not_carry_a_container(doc):
    doc.execute(DefineAsset("container", definition().to_data()), author="ana")
    with pytest.raises(ValueError, match="points at no definition"):
        doc.execute(add(text_box("t1", ref="r1")), author="ana")


# -- editing the text -----------------------------------------------------------------------------------------------
def test_the_text_is_changed_in_place_and_undo_brings_the_old_text_back(doc):
    put_container(doc)
    doc.execute(UpdateAsset("container", "r1", definition(source="flowchart TD\n  X --> Y").to_data()), author="ana")
    assert doc.model.containers["r1"].source.startswith("flowchart TD")
    doc.undo("ana")
    assert doc.model.containers["r1"].source.startswith("flowchart LR")


def test_everybody_who_looks_is_told_when_the_text_changes(doc):
    put_container(doc)
    seen = collect(doc)
    doc.execute(UpdateAsset("container", "r1", definition(source="x").to_data()), author="ana")
    changed = [event for event in seen if (isinstance(event, AssetsChanged) and event.kind.name == "container")]
    assert [event.asset_id for event in changed] == ["r1"]
    assert changed[0].asset is not None and changed[0].asset.source == "x"


def test_a_picture_is_attached_to_the_definition_by_an_update(doc):
    put_container(doc)
    asset = image_asset()
    steps = Batch(
        (
            DefineAsset("image", asset.to_data()),
            UpdateAsset("container", "r1", definition(image=asset.id, renderer="mermaid 1").to_data()),
        )
    )
    doc.execute(steps, author="ana")
    assert doc.model.containers["r1"].image == asset.id
    doc.undo("ana")
    assert doc.model.containers["r1"].image is None and doc.model.images == {}


def test_a_definition_cannot_name_a_picture_the_document_does_not_have(doc):
    with pytest.raises(ValueError, match="does not know the image"):
        doc.execute(DefineAsset("container", definition(image="b" * 64).to_data()), author="ana")


def test_a_picture_that_a_definition_holds_cannot_be_forgotten(doc):
    asset = image_asset()
    doc.execute(
        Batch((DefineAsset("image", asset.to_data()), DefineAsset("container", definition(image=asset.id).to_data()))),
        author="ana",
    )
    with pytest.raises(ValueError, match="in use"):
        doc.execute(ForgetAsset("image", asset.id), author="ana")


def test_an_update_cannot_change_the_id_or_the_type(doc):
    put_container(doc)
    with pytest.raises(ValueError, match="cannot change its id"):
        doc.execute(UpdateAsset("container", "r1", definition(id="r2").to_data()), author="ana")
    with pytest.raises(ValueError, match="cannot change its type"):
        doc.execute(UpdateAsset("container", "r1", definition(type="typst").to_data()), author="ana")


def test_an_update_of_an_unknown_definition_is_refused(doc):
    with pytest.raises(ValueError, match="does not know the container"):
        doc.execute(UpdateAsset("container", "r1", definition().to_data()), author="ana")


# -- defining and forgetting ---------------------------------------------------------------------------------------
def test_a_definition_in_use_cannot_be_forgotten_and_one_that_exists_cannot_be_defined_again(doc):
    put_container(doc)
    with pytest.raises(ValueError, match="in use"):
        doc.execute(ForgetAsset("container", "r1"), author="ana")
    with pytest.raises(ValueError, match="already"):
        doc.execute(DefineAsset("container", definition().to_data()), author="ana")
    doc.execute(RemoveObject("c1"), author="ana")
    doc.execute(ForgetAsset("container", "r1"), author="ana")
    assert doc.model.containers == {}


def test_two_objects_may_show_the_same_definition(doc):
    put_container(doc)
    doc.execute(add(container("c2")), author="ana")
    assert set(doc.model.containers.users("r1")) == {"c1", "c2"}


# -- what colleagues do meanwhile ----------------------------------------------------------------------------------
def test_an_edit_is_not_replayed_over_a_colleagues_edit_of_the_same_text():
    mine = UpdateAsset("container", "r1", definition(source="mine").to_data())
    theirs = UpdateAsset("container", "r1", definition(source="theirs").to_data())
    assert mine.shifted_by(theirs) is None
    assert mine.shifted_by(UpdateAsset("container", "r2", definition(id="r2").to_data())) is mine


def test_forgetting_is_not_replayed_when_a_colleague_now_uses_the_definition():
    forget = ForgetAsset("container", "r1")
    assert forget.shifted_by(add(container())) is None
    assert forget.shifted_by(add(container(definition="r2"))) is forget


def test_an_object_is_not_brought_back_when_a_colleague_took_its_definition_away():
    assert add(container()).shifted_by(ForgetAsset("container", "r1")) is None


# -- saved and read back -------------------------------------------------------------------------------------------
def test_the_definitions_survive_a_snapshot_and_a_replay_of_the_log(doc):
    asset = image_asset()
    doc.execute(
        Batch(
            (
                DefineAsset("image", asset.to_data()),
                DefineAsset(
                    "container", definition(params={"theme": "neutral"}, image=asset.id, renderer="m 1").to_data()
                ),
                add(container()),
            )
        ),
        author="ana",
    )
    again = reopen(doc).model
    assert again.containers == doc.model.containers
    restored = SlideModel.restore(doc.model.serialize())
    assert restored.containers == doc.model.containers
    assert restored.get("c1").body.container == "r1"


def test_a_snapshot_from_before_containers_still_restores(doc):
    state = doc.model.serialize()
    del state["containers"]
    assert SlideModel.restore(state).containers == {}


def test_the_wire_form_of_an_object_names_its_definition(doc):
    put_container(doc)
    assert doc.model.get("c1").to_data()["ref"] == "r1"


def test_a_redacted_definition_keeps_its_place_but_not_its_words(doc):
    command = DefineAsset("container", definition(source="a secret formula").to_data())
    assert command.redacted().data["source"] == ""
    update = UpdateAsset("container", "r1", definition(source="a secret formula").to_data())
    assert update.redacted().data["source"] == ""


# -- what draws an object (D394) --------------------------------------------------------------------------------------
def test_a_container_is_drawn_by_the_picture_made_from_its_text_and_by_none_before(doc):
    put_container(doc)
    body = doc.model.get("c1").body
    assert doc.model.picture_of(body) is None
    asset = image_asset()
    doc.execute(
        Batch(
            (
                DefineAsset("image", asset.to_data()),
                UpdateAsset("container", "r1", definition(image=asset.id, renderer="m 1").to_data()),
            )
        ),
        author="ana",
    )
    assert doc.model.picture_of(doc.model.get("c1").body) == asset.id


def test_a_plain_picture_is_drawn_by_its_own_image(doc):
    from claudia_core import ObjectBody

    body = ObjectBody("i1", "image", 100, 50, "plain-image", ref="a" * 64)
    assert doc.model.picture_of(body) == "a" * 64
