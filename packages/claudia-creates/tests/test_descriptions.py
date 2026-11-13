"""Describing an object to someone who cannot see it, and marking it as decoration (BITV 1.1.1).

The command and the fields are the kernel's (E10.16), so every app has them; the tests run on a slide because that
is where the objects of this package live."""

import pytest
from conftest import add, image_asset, image_import, image_object, move, put, put_image, reopen, shape_object, text_box

from claudia_core import CommandLog, Document, UndoConflict, encode
from claudia_creates import DescribeObject, RemoveObject, SlideModel


# -- describing, and undoing it ----------------------------------------------------------------------------------
def test_an_object_is_described_and_undo_takes_the_description_away(doc):
    put(doc, shape_object())
    doc.execute(DescribeObject("r1", "a grey box that stands for the server"), author="ana")
    assert doc.model.get("r1").body.description == "a grey box that stands for the server"

    doc.undo("ana")
    assert doc.model.get("r1").body.description == ""


def test_a_picture_starts_with_the_words_it_was_imported_with_and_can_be_described_better(doc):
    put_image(doc)
    assert doc.model.get("i1").body.description == "a sample picture"

    doc.execute(DescribeObject("i1", "two cyclists at a finish line"), author="ana")
    assert doc.model.get("i1").body.description == "two cyclists at a finish line"
    assert doc.model.get("i1").body.imported.alt == "a sample picture", "the import keeps what was said when it came in"


def test_a_picture_whose_description_is_cleared_goes_back_to_what_it_was_imported_with(doc):
    put_image(doc)
    doc.execute(DescribeObject("i1", "two cyclists"), author="ana")
    doc.execute(DescribeObject("i1", ""), author="ana")
    assert doc.model.get("i1").body.description == "a sample picture"


# -- decoration ----------------------------------------------------------------------------------------------------
def test_an_object_is_marked_as_decoration_and_loses_its_description_and_undo_brings_both_back(doc):
    put_image(doc)
    doc.execute(DescribeObject("i1", "", decorative=True), author="ana")
    body = doc.model.get("i1").body
    assert body.decorative is True and body.description == ""

    doc.undo("ana")
    body = doc.model.get("i1").body
    assert body.decorative is False and body.description == "a sample picture"


def test_a_decorative_object_cannot_also_have_a_description(doc):
    put(doc, shape_object())
    with pytest.raises(ValueError, match="decorative object has no description"):
        doc.execute(DescribeObject("r1", "a box", decorative=True), author="ana")
    assert doc.model.get("r1").body.decorative is False, "a refused command changes nothing"


def test_describing_a_decorative_object_makes_it_meaningful_again(doc):
    put(doc, shape_object())
    doc.execute(DescribeObject("r1", "", decorative=True), author="ana")
    doc.execute(DescribeObject("r1", "a divider between two sections"), author="ana")
    body = doc.model.get("r1").body
    assert body.decorative is False and body.description == "a divider between two sections"


def test_a_picture_can_be_added_as_decoration_with_no_alt_text_at_all(doc):
    """What the import dialog's "decorative" tick sends: no words, and the flag."""

    asset = image_asset()
    record = image_import(asset.id)
    quiet = type(record).from_data({**record.to_data(), "alt": ""})
    put_image(doc, asset=asset, imported=quiet, decorative=True)
    body = doc.model.get("i1").body
    assert body.decorative is True and body.description == ""


# -- what is refused -------------------------------------------------------------------------------------------------
def test_an_object_that_is_not_there_cannot_be_described(doc):
    with pytest.raises(ValueError, match="ghost"):
        doc.execute(DescribeObject("ghost", "nothing"), author="ana")


def test_a_description_is_at_most_300_characters(doc):
    put(doc, text_box())
    doc.execute(DescribeObject("t1", "x" * 300), author="ana")
    with pytest.raises(ValueError, match="at most 300"):
        doc.execute(DescribeObject("t1", "x" * 301), author="ana")


def test_a_description_that_is_not_text_is_refused(doc):
    put(doc, text_box())
    with pytest.raises(ValueError, match="description"):
        doc.execute(add(text_box("t2", description=5)), author="ana")
    with pytest.raises(ValueError, match="decorative"):
        doc.execute(add(text_box("t3", decorative="yes")), author="ana")


# -- working with colleagues -----------------------------------------------------------------------------------------
def test_moving_an_object_and_a_colleagues_description_do_not_get_in_each_others_way(doc):
    put(doc, shape_object())
    doc.execute(move("r1", 250, 250), author="ana")
    doc.execute(DescribeObject("r1", "a box"), author="ben")
    doc.undo("ana")
    assert (doc.model.get("r1").anchor.x, doc.model.get("r1").anchor.y) == (200, 200)
    assert doc.model.get("r1").body.description == "a box", "ben's description stays"


def test_undo_of_a_description_is_refused_when_a_colleague_described_it_again(doc):
    put(doc, shape_object())
    doc.execute(DescribeObject("r1", "a box"), author="ana")
    doc.execute(DescribeObject("r1", "a server"), author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")
    assert doc.model.get("r1").body.description == "a server"


def test_a_description_survives_removing_the_object_and_bringing_it_back(doc):
    put(doc, shape_object())
    doc.execute(DescribeObject("r1", "a box"), author="ana")
    doc.execute(RemoveObject("r1"), author="ana")
    doc.undo("ana")
    assert doc.model.get("r1").body.description == "a box"


# -- the history ---------------------------------------------------------------------------------------------------
def test_the_history_reads_like_sentences():
    assert DescribeObject("r1", "a box").label == "Describe object"
    assert DescribeObject("r1", "", decorative=True).label == "Mark as decorative"
    assert DescribeObject("r1", "a box").summary == "Described an object: a box"
    assert DescribeObject("r1", "", decorative=True).summary == "Marked an object as decorative"
    assert DescribeObject("r1", "").summary == "Removed an object's description"


def test_adding_a_picture_says_how_it_is_described():
    assert add(image_object()).summary == "Added an image: a sample picture"
    assert add(image_object(decorative=True, description="")).summary == "Added a decorative image"


# -- documents are forever -----------------------------------------------------------------------------------------
def test_describing_round_trips_and_is_namespaced():
    command = DescribeObject("r1", "a box", False)
    assert command.kind.startswith("core.")
    assert SlideModel.registry.decode(encode(command)) == command


def test_a_description_survives_the_log_and_a_model_survives_its_snapshot(doc):
    put(doc, shape_object())
    doc.execute(DescribeObject("r1", "a box"), author="ana")
    doc.execute(DescribeObject("r1", "", decorative=True), author="ana")
    assert reopen(doc).model.serialize() == doc.model.serialize()
    assert SlideModel.restore(doc.model.serialize()).serialize() == doc.model.serialize()


def test_a_snapshot_written_before_descriptions_existed_still_restores(doc):
    put_image(doc)
    state = doc.model.serialize()
    for body in state["objects"]:
        del body["description"], body["decorative"]
    restored = SlideModel.restore(state)
    assert restored.get("i1").body.description == "a sample picture"
    assert restored.get("i1").body.decorative is False


def envelopes(node, kind):
    """Every stored command of ``kind`` in a log entry, however deep (a batch holds its steps)."""
    if isinstance(node, dict):
        if node.get("k") == kind:
            yield node
        for value in node.values():
            yield from envelopes(value, kind)
    elif isinstance(node, list):
        for value in node:
            yield from envelopes(value, kind)


def test_a_log_written_before_descriptions_existed_still_replays(doc):
    put_image(doc)
    log = doc.log.to_data()
    old = list(envelopes(log, "core.AddObject"))
    assert old, "the log has the picture's AddObject (the test would prove nothing without it)"
    for envelope in old:
        envelope["s"] = 1
        del envelope["d"]["body"]["description"], envelope["d"]["body"]["decorative"]
    replayed = Document.open(SlideModel, CommandLog.from_data(log, SlideModel.registry))
    assert replayed.model.get("i1").body.description == "a sample picture"


def test_the_redacted_description_keeps_the_flag_and_loses_the_words():
    assert DescribeObject("r1", "private words", False).redacted() == DescribeObject("r1", "", False)
    assert DescribeObject("r1", "", True).redacted() == DescribeObject("r1", "", True)
