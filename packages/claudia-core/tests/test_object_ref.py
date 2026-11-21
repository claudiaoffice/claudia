"""An object body points at its definition with one field, ``ref``, whose table the kind names (D1201's lesson: a new
kind of object must not need a new field). Bodies written with one field per kind still read."""

import pytest

from claudia_core import AddObject, ObjectBody, paragraph_for
from claudia_core.commands import core_commands
from claudia_core.testing import body_before_ref

POINTERS = ("shape", "image", "diagram", "container", "table")


def body(kind: str, ref: str | None = "x1") -> ObjectBody:
    return ObjectBody("o1", kind, 100, 40, "plain-image", ref=ref)


@pytest.mark.parametrize("kind", POINTERS)
def test_the_kind_says_which_pointer_the_ref_is_and_every_other_pointer_reads_nothing(kind):
    one = body(kind)
    assert getattr(one, kind) == "x1"
    assert [getattr(one, other) for other in POINTERS if other != kind] == [None] * 4


def test_a_text_box_points_at_nothing():
    box = ObjectBody("t1", "text", 100, 40, "body-text", paragraph_for("t1", "body-text", "hi"))
    assert box.ref is None and [getattr(box, name) for name in POINTERS] == [None] * 5


def test_the_plain_data_has_one_pointer_and_none_of_the_old_ones():
    data = body("table").to_data()
    assert data["ref"] == "x1" and not set(POINTERS) & set(data)
    assert ObjectBody.from_data(data) == body("table")


def legacy(kind: str, **more) -> dict:
    return {**body_before_ref(body(kind).to_data()), **more}


@pytest.mark.parametrize("kind", POINTERS)
def test_a_body_written_with_a_field_for_each_kind_reads_with_its_pointer_as_ref(kind):
    assert ObjectBody.from_data(legacy(kind)) == body(kind)


def test_a_body_of_the_last_generation_before_tables_reads_too():
    old = legacy("diagram")
    del old["table"]
    assert ObjectBody.from_data(old) == body("diagram")


def test_a_legacy_body_with_a_pointer_of_another_kind_is_refused():
    with pytest.raises(ValueError, match="a shape object has no image"):
        ObjectBody.from_data(legacy("shape", image="x2"))


def test_a_body_with_a_field_nobody_knows_is_refused_whichever_form_it_has():
    with pytest.raises(ValueError, match="exactly these fields"):
        ObjectBody.from_data({**body("table").to_data(), "colour": "red"})
    with pytest.raises(ValueError, match="exactly these fields"):
        ObjectBody.from_data({**legacy("table"), "colour": "red"})


def test_an_add_object_of_schema_5_is_brought_up_to_date():
    assert AddObject.schema == 6
    stored = {"body": legacy("table"), "anchor": {"holder": "s1"}, "at": None}
    command = core_commands.decode({"k": "core.AddObject", "s": 5, "d": stored})
    assert command.body == body("table")
