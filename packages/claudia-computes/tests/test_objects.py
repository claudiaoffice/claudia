"""Floating objects anchored to a sheet's cells: images, and the anchor's resistance to structural edits (E6.17)."""

import pytest
from conftest import S1, add, image_asset, image_import, image_object, move, put_image, reopen

from claudia_computes import (
    AddSheet,
    DefineImage,
    DeleteCols,
    DeleteRows,
    ForgetImage,
    InsertCols,
    InsertRows,
    RemoveObject,
    RemoveSheet,
    ResizeLines,
    Structure,
    WorkbookModel,
)
from claudia_computes.events import ImagesChanged, ObjectsChanged
from claudia_core import Batch, Document, MemoryStore, encode


def ids(doc, sheet=S1):
    return [o.id for o in doc.model.objects_on(sheet)]


def collect(doc):
    seen = []
    doc.subscribe(seen.append)
    return seen


# -- the whole story: import, place, move, remove, undo -------------------------------------------------------
def test_an_image_is_added_with_its_asset_and_undo_takes_both_away(doc):
    put_image(doc)
    assert doc.model.get_object("i1").body.image in doc.model.images, (
        "the document keeps its own copy of the decoded asset"
    )
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
    with pytest.raises(ValueError, match="proportions"):
        put_image(doc, "i1", asset=asset, w=200, h=200)
    put_image(doc, "i1", asset=asset, w=301, h=150)  # one unit of rounding is fine
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


def test_moving_an_object_keeps_its_size(doc):
    put_image(doc, w=400, h=200)
    doc.execute(move("i1", 5, 6), author="ana")
    moved = doc.model.get_object("i1")
    assert (moved.anchor.row, moved.anchor.col) == (5, 6)
    assert (moved.body.w, moved.body.h) == (400, 200)
    doc.undo("ana")
    back = doc.model.get_object("i1")
    assert (back.anchor.row, back.anchor.col) == (2, 2)


# -- what a model refuses ------------------------------------------------------------------------------------
def test_an_image_object_needs_a_known_asset_and_its_import_record(doc):
    asset = image_asset()
    with pytest.raises(ValueError, match="needs an image"):
        doc.execute(add(image_object(asset=asset, imported=None)), author="ana")
    with pytest.raises(ValueError, match="does not know the image"):
        doc.execute(add(image_object(asset=asset)), author="ana")  # asset never defined


def test_the_import_records_asset_must_match_the_objects_image(doc):
    a, b = image_asset(width=10, height=10), image_asset(width=20, height=20)
    doc.execute(DefineImage(a), author="ana")
    doc.execute(DefineImage(b), author="ana")
    mismatched = image_object(asset=a, imported=image_import(b.id))
    with pytest.raises(ValueError, match="does not match"):
        doc.execute(add(mismatched), author="ana")


def test_an_object_must_sit_on_a_known_sheet(doc):
    asset = image_asset()
    doc.execute(DefineImage(asset), author="ana")
    with pytest.raises(ValueError, match="unknown container"):  # a sheet is a container (E10.16)
        doc.execute(add(image_object(sheet="nope", asset=asset)), author="ana")


def test_an_object_is_at_least_the_minimum_size(doc):
    asset = image_asset(width=10, height=10)
    doc.execute(DefineImage(asset), author="ana")
    with pytest.raises(ValueError, match="at least"):
        doc.execute(add(image_object(asset=asset, w=5, h=5)), author="ana")


# -- the anchor never moves or resizes on its own: only MoveObject changes it -----------------------------------
def test_inserting_rows_above_an_object_does_not_move_or_resize_it(doc):
    put_image(doc, row=5, col=2, w=400, h=200)
    doc.execute(Structure(InsertRows(S1, 0, 3)), author="ana")
    same = doc.model.get_object("i1")
    assert (same.anchor.row, same.anchor.col, same.body.w, same.body.h) == (5, 2, 400, 200)


def test_deleting_rows_above_an_object_does_not_move_or_resize_it(doc):
    put_image(doc, row=5, col=2, w=400, h=200)
    doc.execute(Structure(DeleteRows(S1, 0, 3)), author="ana")
    same = doc.model.get_object("i1")
    assert (same.anchor.row, same.anchor.col, same.body.w, same.body.h) == (5, 2, 400, 200)


def test_inserting_or_deleting_columns_does_not_move_or_resize_an_object(doc):
    put_image(doc, row=5, col=5, w=400, h=200)
    doc.execute(Structure(InsertCols(S1, 0, 2)), author="ana")
    doc.execute(Structure(DeleteCols(S1, 0, 1)), author="ana")
    same = doc.model.get_object("i1")
    assert (same.anchor.row, same.anchor.col, same.body.w, same.body.h) == (5, 5, 400, 200)


def test_resizing_rows_or_columns_does_not_resize_an_object(doc):
    put_image(doc, row=1, col=1, w=400, h=200)
    doc.execute(ResizeLines(S1, "row", ((1, 500),)), author="ana")
    doc.execute(ResizeLines(S1, "col", ((1, 800),)), author="ana")
    same = doc.model.get_object("i1")
    assert (same.body.w, same.body.h) == (400, 200)


def test_a_structural_edit_even_through_the_rows_an_object_anchors_to_leaves_it_in_place(doc):
    """Deleting the very row an object anchors to does not touch the object (open design point, see the notes):
    only moving it (``MoveObject``) ever changes where it sits."""
    put_image(doc, row=2, col=2, w=400, h=200)
    doc.execute(Structure(DeleteRows(S1, 0, 5)), author="ana")
    same = doc.model.get_object("i1")
    assert (same.anchor.row, same.anchor.col) == (2, 2)


# -- removing a sheet takes its objects with it, and undo brings them all back --------------------------------
def test_removing_a_sheet_removes_its_objects_and_undo_restores_them_in_place(doc):
    asset = image_asset()
    put_image(doc, "i1", asset=asset)
    put_image(doc, "i2", asset=asset)
    assert ids(doc) == ["i1", "i2"]
    doc.execute(RemoveSheet(S1), author="ana")
    assert doc.model.objects == {}
    doc.undo("ana")
    assert ids(doc) == ["i1", "i2"]
    assert doc.model.get_object("i1").body.image in doc.model.images


def test_removing_a_sheet_does_not_forget_its_images_asset(doc):
    """The asset survives a sheet's removal (and the object's) so that undo can bring the object back."""
    asset = image_asset()
    put_image(doc, asset=asset)
    doc.execute(RemoveSheet(S1), author="ana")
    assert asset.id in doc.model.images


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
    expected_path = doc.model.get_object("i1").body.imported.source_path
    told = next(e for e in seen if isinstance(e, ObjectsChanged) and e.changed)

    for_importer = told.to_data_for("ana")["changed"][0]["imported"]
    assert for_importer["source_path"] == expected_path

    for_colleague = told.to_data_for("ben")["changed"][0]["imported"]
    assert for_colleague["source_path"] is None
    assert for_colleague["source"] == "disk"  # not hidden: only where on disk
    assert for_colleague["imported_by"] == "ana"  # not hidden either

    # to_data() (the log's own view) is never masked
    assert told.to_data()["changed"][0]["imported"]["source_path"] == expected_path


def test_a_sheet_objects_to_data_for_masks_only_the_image_it_carries(doc):
    put_image(doc)
    stored = doc.model.get_object("i1")
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
        # Objects are shared by all three apps, so their commands are namespaced ``core.`` (E10.16).
        assert command.kind.startswith("core.")
        assert WorkbookModel.registry.decode(encode(command)) == command


def test_every_image_command_survives_the_log_and_a_model_survives_its_snapshot(doc):
    put_image(doc, "i1")
    doc.execute(move("i1", 5, 6), author="ana")
    assert reopen(doc).model.serialize() == doc.model.serialize()
    assert WorkbookModel.restore(doc.model.serialize()).serialize() == doc.model.serialize()


def test_equal_states_serialize_equally_with_shared_images_whatever_order(doc):
    asset = image_asset()
    put_image(doc, "i1", asset=asset)
    put_image(doc, "i2", asset=asset)
    other = Document(WorkbookModel(), store=MemoryStore())
    other.execute(AddSheet(S1, "Sheet1"), author="x")
    other.execute(Batch((DefineImage(asset), add(image_object("i1", asset=asset)))), author="x")
    other.execute(add(image_object("i2", asset=asset)), author="x")
    assert other.model.serialize() == doc.model.serialize()


# -- redaction is deliberately out of scope here (an open decision, not resolved by this change) --------------
def test_redacting_an_image_object_does_not_yet_touch_its_import_record(doc):
    """Documented, not (yet) a design decision: AddObject.redacted() is a no-op (an image object carries no text
    of its own); an image's alt and source_name/source_path survive redaction today, same as creates' own."""
    added = put_image(doc)
    doc.redact([added.revision])
    assert doc.model.get_object("i1").body.imported.alt == "a sample picture"
