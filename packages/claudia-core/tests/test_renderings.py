"""A rendered text container: its definition, the field an object body points at it with, and old documents (D340).

The definition is the text the person writes (a LaTeX formula, a Mermaid diagram, a Typst page) and the picture last
made from it. It is plain data, the same in all three apps; the kernel never runs a renderer and never reads the source.
Documents are forever (docs/versioning.md): a body written before the field existed still reads."""

import pytest

from claudia_core import AddObject, ObjectBody, RenderedDefinition, paragraph_for
from claudia_core.commands import core_commands


def definition(**changes) -> RenderedDefinition:
    fields = {"id": "r1", "type": "mermaid", "source": "flowchart LR\n  A --> B"}
    return RenderedDefinition(**{**fields, **changes})


def rendered_body(**changes) -> ObjectBody:
    fields = {"id": "o1", "kind": "rendered", "w": 300, "h": 200, "style": "plain-image", "rendered": "r1"}
    return ObjectBody(**{**fields, **changes})


# -- the definition ----------------------------------------------------------------------------------------------
def test_a_definition_is_a_type_and_a_source_and_has_no_picture_until_one_is_made():
    one = definition()
    assert (one.type, one.image, one.renderer) == ("mermaid", None, "")
    assert dict(one.params) == {}


def test_a_definition_round_trips_through_plain_data():
    one = definition(
        params={"theme": "neutral", "scale": 2, "dark": False}, image="a" * 64, renderer="mermaid 1.0 | mmdc 11"
    )
    assert RenderedDefinition.from_data(one.to_data()) == one


def test_the_plain_data_names_its_format_so_that_a_later_one_can_be_told_apart():
    assert definition().to_data()["format"] == 1
    with pytest.raises(ValueError, match="format"):
        RenderedDefinition.from_data({**definition().to_data(), "format": 2})


def test_parameters_cannot_be_changed_after_the_fact():
    one = definition(params={"theme": "neutral"})
    with pytest.raises(TypeError):
        one.params["theme"] = "dark"  # type: ignore[index]


@pytest.mark.parametrize("bad_id", ["", "R1", "1r", "r 1", "r" * 41])
def test_an_id_is_lower_case_letters_digits_dash_and_underscore_starting_with_a_letter(bad_id):
    with pytest.raises(ValueError, match="id"):
        definition(id=bad_id)


@pytest.mark.parametrize("bad_type", ["", "Mermaid", "mer maid", "../x", "m" * 33])
def test_a_type_is_a_plain_lower_case_name(bad_type):
    with pytest.raises(ValueError, match="type"):
        definition(type=bad_type)


def test_a_source_may_be_empty_while_somebody_is_still_writing_it_but_not_without_end():
    assert definition(source="").source == ""
    with pytest.raises(ValueError, match="source"):
        definition(source="x" * 200_001)


def test_a_source_must_be_text():
    with pytest.raises(ValueError, match="source"):
        definition(source=b"x")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "params",
    [
        {"Theme": "x"},  # key: lower case
        {"theme": [1]},  # value: a scalar
        {"theme": None},
        {"theme": "x" * 201},
        {f"k{n}": n for n in range(33)},  # too many
    ],
)
def test_parameters_are_few_plain_named_scalars(params):
    with pytest.raises(ValueError, match="param"):
        definition(params=params)


def test_a_picture_is_named_by_the_id_of_an_image_asset():
    with pytest.raises(ValueError, match="image"):
        definition(image="Not An Id")


# -- the body --------------------------------------------------------------------------------------------------------
def test_a_rendered_object_body_names_its_definition_and_carries_no_text():
    body = rendered_body()
    assert body.rendered == "r1" and body.paragraph is None


def test_the_field_is_part_of_the_plain_data_of_every_body():
    assert rendered_body().to_data()["rendered"] == "r1"
    assert ObjectBody.from_data(rendered_body().to_data()) == rendered_body()
    plain = ObjectBody("t1", "text", 100, 40, "body-text", paragraph=paragraph_for("t1", "body-text", "hi"))
    assert plain.to_data()["rendered"] is None


def test_a_body_written_before_rendered_objects_existed_still_reads():
    old = rendered_body(kind="text", rendered=None, paragraph=paragraph_for("o1", "body-text", "x")).to_data()
    del old["rendered"]
    assert ObjectBody.from_data(old).rendered is None


def test_a_body_with_a_field_nobody_knows_is_still_refused():
    with pytest.raises(ValueError, match="exactly these fields"):
        ObjectBody.from_data({**rendered_body().to_data(), "surprise": 1})


# -- the command of an old log ---------------------------------------------------------------------------------------
def test_an_add_object_logged_before_the_field_is_upcast_with_no_definition():
    now = AddObject(
        rendered_body(kind="text", rendered=None, paragraph=paragraph_for("o1", "body-text", "x")), {"kind": "x"}
    )
    stored = now.to_data()
    del stored["body"]["rendered"]
    del stored["body"]["description"], stored["body"]["decorative"]  # as schema 1 had it
    command = core_commands.decode({"k": "core.AddObject", "s": 1, "d": stored})
    assert command.body.rendered is None


def test_an_add_object_of_schema_two_is_upcast_too():
    now = AddObject(
        rendered_body(kind="text", rendered=None, paragraph=paragraph_for("o1", "body-text", "x")), {"kind": "x"}
    )
    stored = now.to_data()
    del stored["body"]["rendered"]
    assert core_commands.decode({"k": "core.AddObject", "s": 2, "d": stored}).body.rendered is None
