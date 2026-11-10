"""Image objects on a slide: the asset a document keeps, its import record, and who is allowed to see what (E10.8)."""

import pytest
from conftest import (
    SLIDE,
    add,
    image_asset,
    image_import,
    image_object,
    move,
    put_image,
    reopen,
    resize,
    shape_object,
    text_box,
)

from claudia_core import Batch, Document, MemoryStore, UnknownCommand, encode
from claudia_creates import DefineImage, ForgetImage, RemoveObject, SlideModel
from claudia_creates.events import ImagesChanged, ObjectsChanged


def ids(doc, slide=SLIDE):
    return [o.id for o in doc.model.objects_on(slide)]


def collect(doc):
    seen = []
    doc.subscribe(seen.append)
    return seen


# -- the whole story: import, place, resize, remove, undo -----------------------------------------------------
def test_an_image_is_added_with_its_asset_and_undo_takes_both_away(doc):
    put_image(doc)
    assert doc.model.get("i1").body.image in doc.model.images, "the document keeps its own copy of the decoded asset"
    doc.undo("ana")
    assert ids(doc) == [] and doc.model.images == {}


def test_two_objects_can_share_the_same_asset(doc):
    asset = image_asset()
    put_image(doc, "i1", asset=asset)
    put_image(doc, "i2", asset=asset)
    assert set(doc.model.users_of_image(asset.id)) == {"i1", "i2"}
    assert len(doc.model.images) == 1, "the asset is only kept once"


def test_an_image_keeps_its_proportions(doc):
    asset = image_asset(width=200, height=100)  # 2:1
    put_image(doc, "i1", asset=asset, w=200, h=100)
    with pytest.raises(ValueError, match="proportions"):
        doc.execute(resize("i1", 0, 0, 200, 200), author="ana")
    doc.execute(resize("i1", 0, 0, 301, 150), author="ana")  # one unit of rounding is fine
    with pytest.raises(ValueError, match="proportions"):
        put_image(doc, "i2", asset=image_asset(width=200, height=50), w=200, h=100)


def test_an_image_that_is_in_use_cannot_be_forgotten_and_one_that_exists_cannot_be_defined_again(doc):
    asset = image_asset()
    put_image(doc, asset=asset)
    with pytest.raises(ValueError, match="in use"):
        doc.execute(ForgetImage(asset.id), author="ana")
    with pytest.raises(ValueError, match="already"):
        doc.execute(DefineImage(asset), author="ana")
    doc.execute(RemoveObject("i1"), author="ana")
    doc.execute(ForgetImage(asset.id), author="ana")
    assert doc.model.images == {}


# -- what a model refuses ------------------------------------------------------------------------------------
def test_an_image_object_needs_a_known_asset_and_its_import_record(doc):
    asset = image_asset()
    with pytest.raises(ValueError, match="needs an image"):
        doc.execute(add(image_object(asset=asset, imported=None)), author="ana")
    with pytest.raises(ValueError, match="does not know the image"):
        doc.execute(add(image_object(asset=asset)), author="ana")  # asset never defined


def test_an_image_object_has_no_shape_and_a_shape_object_has_no_image(doc):
    asset = image_asset()
    doc.execute(DefineImage(asset), author="ana")
    with pytest.raises(ValueError, match="no shape"):
        doc.execute(add(image_object(asset=asset, shape="rectangle")), author="ana")
    with pytest.raises(ValueError, match="no image"):
        doc.execute(add(shape_object(image=asset.id)), author="ana")


def test_a_text_box_has_no_shape_or_image(doc):
    # The message also names "diagram" now (E6.6): a text box carries none of the three (claudia_core.objects).
    with pytest.raises(ValueError, match="no shape, image or diagram"):
        doc.execute(add(text_box(image="deadbeef" * 8)), author="ana")


def test_the_import_records_asset_must_match_the_objects_image(doc):
    a, b = image_asset(width=10, height=10), image_asset(width=20, height=20)
    doc.execute(DefineImage(a), author="ana")
    doc.execute(DefineImage(b), author="ana")
    mismatched = image_object(asset=a, imported=image_import(b.id))
    with pytest.raises(ValueError, match="does not match"):
        doc.execute(add(mismatched), author="ana")


# -- views are told, and masking --------------------------------------------------------------------------
def test_views_hear_about_images(doc):
    seen = collect(doc)
    asset = image_asset()
    doc.execute(DefineImage(asset), author="ana")
    changed = [e for e in seen if isinstance(e, ImagesChanged)]
    assert changed[0].to_data() == {"type": "image", "id": asset.id, "asset": asset.to_data()}
    doc.execute(ForgetImage(asset.id), author="ana")
    assert [e for e in seen if isinstance(e, ImagesChanged)][-1].to_data() == {
        "type": "image",
        "id": asset.id,
        "asset": None,
    }


def test_an_objects_changed_event_masks_the_source_path_for_everyone_but_the_importer(doc):
    seen = collect(doc)
    put_image(doc)  # imported by "ana" (the default author of put_image)
    expected_path = doc.model.get("i1").body.imported.source_path
    told = next(e for e in seen if isinstance(e, ObjectsChanged) and e.changed)

    for_importer = told.to_data_for("ana")["changed"][0]["imported"]
    assert for_importer["source_path"] == expected_path

    for_colleague = told.to_data_for("ben")["changed"][0]["imported"]
    assert for_colleague["source_path"] is None
    assert for_colleague["source"] == "disk"  # not hidden: only where on disk
    assert for_colleague["imported_by"] == "ana"  # not hidden either

    # to_data() (the log's own view) is never masked
    assert told.to_data()["changed"][0]["imported"]["source_path"] == expected_path


def test_a_slide_objects_to_data_for_masks_only_the_image_it_carries(doc):
    put_image(doc)
    stored = doc.model.get("i1")
    assert stored.to_data_for("ben")["imported"]["source_path"] is None
    assert stored.to_data_for("ana")["imported"]["source_path"] == stored.body.imported.source_path


# -- the history reads like sentences -----------------------------------------------------------------------
def test_the_history_has_a_sentence_for_adding_an_image():
    asset = image_asset()
    obj = image_object(asset=asset)
    assert add(obj).label == "Add image"
    assert "sample picture" in add(obj).summary


# -- documents are forever: schema, round trips, snapshots ---------------------------------------------------
def test_command_data_round_trips_for_images():
    asset = image_asset()
    obj = image_object(asset=asset)
    for command in (DefineImage(asset), ForgetImage(asset.id), add(obj)):
        assert command.kind.startswith("core.")  # images are shared by all three apps (E10.16)
        assert SlideModel.registry.decode(encode(command)) == command


def test_every_image_command_survives_the_log_and_a_model_survives_its_snapshot(doc):
    put_image(doc, "i1")
    doc.execute(move("i1", 5, 6), author="ana")
    assert reopen(doc).model.serialize() == doc.model.serialize()
    assert SlideModel.restore(doc.model.serialize()).serialize() == doc.model.serialize()


def test_an_old_stored_add_object_from_before_the_shared_layer_is_no_longer_read():
    """See the matching test in ``test_grid.py``: E10.16 renamed the object commands' ``kind``, and a registry
    cannot alias one kind to another, so logs written before it do not replay (D177, accepted pre-release)."""
    old = {"k": "creates.AddObject", "s": 1, "d": {"object": {}, "at": None}}
    with pytest.raises(UnknownCommand, match="creates.AddObject"):
        SlideModel.registry.decode(old)


def test_equal_states_serialize_equally_with_shared_images_whatever_order(doc):
    asset = image_asset()
    put_image(doc, "i1", asset=asset)
    put_image(doc, "i2", asset=asset)
    other = Document(SlideModel.empty(), store=MemoryStore())
    other.execute(Batch((DefineImage(asset), add(image_object("i1", asset=asset)))), author="x")
    other.execute(add(image_object("i2", asset=asset)), author="x")
    assert other.model.serialize() == doc.model.serialize()


# -- redaction is deliberately out of scope here (an open decision, not resolved by this change) --------------
def test_redacting_an_image_object_does_not_yet_touch_its_import_record(doc):
    """Documented, not (yet) a design decision: AddObject.redacted() only blanks `text`; an image's `alt` and
    `source_name`/`source_path` survive redaction today. See the implementation notes."""
    added = put_image(doc)
    doc.redact([added.revision])
    assert doc.model.get("i1").body.imported.alt == "a sample picture"
