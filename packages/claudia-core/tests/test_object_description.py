"""What an object says about itself to someone who cannot see it: its description and its "decorative" flag (BITV).

The body is the same in every app (E10.16), so the field is too. Documents are forever (docs/versioning.md): a body
written before the fields existed still reads, and a picture's description is then what it was imported with."""

import pytest

from claudia_core import AddObject, ImageImport, ObjectBody, paragraph_for
from claudia_core.commands import core_commands


def picture_import(alt: str = "a red bicycle") -> ImageImport:
    return ImageImport(
        asset="a1",
        alt=alt,
        imported_by="ana",
        imported_at="2026-11-13T10:00:00.000Z",
        source="disk",
        source_name="b.png",
    )


def picture(**changes) -> ObjectBody:
    fields = {
        "id": "i1",
        "kind": "image",
        "w": 40,
        "h": 20,
        "style": "plain-image",
        "image": "a1",
        "imported": picture_import(),
    }
    return ObjectBody(**{**fields, **changes})


def text_box(**changes) -> ObjectBody:
    fields = {
        "id": "t1",
        "kind": "text",
        "w": 100,
        "h": 40,
        "style": "body-text",
        "paragraph": paragraph_for("t1", "body-text", "hi"),
    }
    return ObjectBody(**{**fields, **changes})


# -- the two fields --------------------------------------------------------------------------------------------
def test_an_object_is_described_by_nothing_and_not_decorative_until_somebody_says_otherwise():
    box = text_box()
    assert box.description == "" and box.decorative is False


def test_a_picture_is_described_by_the_words_it_was_imported_with():
    assert picture().description == "a red bicycle"


def test_a_description_given_to_a_picture_wins_over_what_it_was_imported_with():
    assert picture(description="a bicycle against a brick wall").description == "a bicycle against a brick wall"


def test_a_decorative_picture_has_no_description_even_though_it_was_imported_with_one():
    assert picture(decorative=True).description == ""


def test_the_fields_are_part_of_the_data_the_log_stores():
    data = picture(description="a bicycle").to_data()
    assert data["description"] == "a bicycle" and data["decorative"] is False
    assert ObjectBody.from_data(data) == picture(description="a bicycle")


# -- documents are forever -------------------------------------------------------------------------------------
def test_a_body_written_before_the_fields_existed_still_reads():
    old = picture().to_data()
    del old["description"], old["decorative"]
    assert ObjectBody.from_data(old).description == "a red bicycle"
    assert ObjectBody.from_data(old).decorative is False


def test_a_body_with_only_one_of_the_new_fields_is_still_refused():
    data = text_box().to_data()
    del data["decorative"]
    with pytest.raises(ValueError, match="exactly these fields"):
        ObjectBody.from_data(data)


def test_a_body_with_a_field_nobody_knows_is_refused():
    with pytest.raises(ValueError, match="exactly these fields"):
        ObjectBody.from_data({**text_box().to_data(), "colour": "red"})


def test_adding_an_object_is_schema_2_and_schema_1_data_is_brought_up_to_date():
    assert AddObject.schema == 2
    old_body = picture().to_data()
    del old_body["description"], old_body["decorative"]
    envelope = {"k": "core.AddObject", "s": 1, "d": {"body": old_body, "anchor": {"container": "s1"}, "at": None}}
    command = core_commands.decode(envelope)
    assert command.body.description == "a red bicycle" and command.body.decorative is False
