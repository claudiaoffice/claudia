"""What a name is, for everything in a document that can be pointed at (D550, D551).

One rule for all of it: objects, slides, sheets and chart tabs share one namespace, compared without regard to
capitals or runs of spaces, and a thing that has no name yet is given the first free "<Kind> <n>"."""

import pytest

from claudia_core import MAX_THING_NAME, ObjectBody, clean_name, free_name, name_key, name_problem, paragraph_for


# -- what a name is -------------------------------------------------------------------------------------------
def test_a_name_is_kept_as_typed_but_with_the_spaces_around_and_between_words_tidied():
    assert clean_name("  Figure \t 1  ") == "Figure 1"


def test_two_names_that_differ_only_in_capitals_or_spaces_are_the_same_name():
    assert name_key("Figure  1") == name_key(" figure 1")
    assert name_key("Straße") == name_key("STRASSE")


def test_names_with_spaces_umlauts_or_a_hash_are_fine():
    for fine in ("figure 1", "Größe der Stichprobe", "#1 priority", "Q4 (forecast)"):
        assert name_problem(fine) is None


@pytest.mark.parametrize(
    ("bad", "why"),
    [
        ("", "needs some text"),
        ("   ", "needs some text"),
        ("a\x00b", "control character"),
        ("a\nb", "control character"),
    ],
)
def test_a_name_needs_some_text_and_no_control_characters(bad, why):
    assert why in name_problem(bad)


def test_a_name_is_not_longer_than_the_limit():
    assert name_problem("x" * MAX_THING_NAME) is None
    assert str(MAX_THING_NAME) in name_problem("x" * (MAX_THING_NAME + 1))


# -- the name a new thing gets ---------------------------------------------------------------------------------
def test_a_new_thing_gets_the_first_free_number_of_its_kind():
    assert free_name("Text box", []) == "Text box 1"
    assert free_name("Text box", ["Text box 1", "text box 2"]) == "Text box 3"


def test_a_number_that_became_free_is_used_again():
    assert free_name("Slide", ["Slide 2"]) == "Slide 1"


def test_other_kinds_do_not_use_up_the_numbers():
    assert free_name("Picture", ["Text box 1", "Slide 1"]) == "Picture 1"


# -- on the body of an object -----------------------------------------------------------------------------------
def test_an_object_body_has_no_name_until_it_is_given_one_and_the_name_is_part_of_the_data_the_log_stores():
    fields = {
        "id": "t1",
        "kind": "text",
        "w": 100,
        "h": 40,
        "style": "body-text",
        "paragraph": paragraph_for("t1", "body-text"),
    }
    assert ObjectBody(**fields).name == ""
    named = ObjectBody(**fields, name="Intro")
    assert named.to_data()["name"] == "Intro"
    assert ObjectBody.from_data(named.to_data()) == named


# -- documents are forever ------------------------------------------------------------------------------------
def test_an_object_written_before_names_reads_as_unnamed():
    from claudia_core import AddObject, new_registry

    body = ObjectBody("t1", "text", 400, 100, "plain-box", paragraph_for("t1", "body-text", "hi", "ann")).to_data()
    del body["name"]
    old = {"k": "core.AddObject", "s": 3, "d": {"body": body, "anchor": {"x": 1, "y": 2}, "at": None}}

    command = new_registry().decode(old)

    assert isinstance(command, AddObject)
    assert command.body.name == ""
    assert AddObject.schema == 6


def test_an_object_written_before_ranges_shared_names_replays_under_the_old_rule():
    from claudia_core import AddObject, new_registry

    body = ObjectBody("t1", "text", 400, 100, "plain-box", paragraph_for("t1", "body-text", "hi", "ann")).to_data()
    old = {"k": "core.AddObject", "s": 4, "d": {"body": body, "anchor": {"x": 1, "y": 2}, "at": None}}
    command = new_registry().decode(old)
    assert command.legacy_names
    assert command.to_data()["legacy_names"] is True
    assert "legacy_names" not in AddObject(command.body, command.anchor).to_data()
