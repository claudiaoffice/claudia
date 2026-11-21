"""Named ranges are things (D552): each has an id that survives renaming, and a range and an object, a sheet, a chart
tab or a slide never share a name. Old logs, written before that, still replay."""

import pytest
from conftest import S1, add, image_asset, image_object, put_chart_spec, put_image, reopen
from names_helpers import define, name

from claudia_computes import (
    AddChart,
    AddSheet,
    DefineName,
    NamedRange,
    RemoveName,
    RenameName,
    WorkbookModel,
)
from claudia_core import DefineAsset, Document, MemoryStore, RenameThing


def ids_of(doc) -> dict[str, str]:
    return {named.name: named.id for named in doc.model.names}


# -- the id -----------------------------------------------------------------------------------------------------
def test_a_name_has_an_id_that_tells_nothing_about_its_text():
    named = NamedRange("Revenue", None, name("Revenue", "A1:B2").range)
    assert named.id.startswith("r") and "revenue" not in named.id.lower()


def test_an_id_given_is_kept_and_written():
    named = NamedRange("Revenue", None, name("Revenue", "A1:B2").range, id="rfeed0001")
    assert named.id == "rfeed0001"
    assert NamedRange.from_data(named.to_data()).id == "rfeed0001"


def test_an_old_name_without_an_id_gets_the_same_one_every_time():
    data = name("Revenue", "A1:B2").to_data()
    del data["id"]
    first, second = NamedRange.from_data(data), NamedRange.from_data(data)
    assert first.id == second.id != ""


def test_renaming_a_name_keeps_its_id(doc):
    define(doc, "Revenue", "A1:B2")
    before = ids_of(doc)["Revenue"]
    doc.execute(RenameName(None, "Revenue", "Takings"), author="ana")
    assert ids_of(doc) == {"Takings": before}
    doc.undo("ana")
    assert ids_of(doc) == {"Revenue": before}


def test_defining_a_name_again_keeps_the_id_of_the_one_it_replaces(doc):
    define(doc, "Revenue", "A1:B2")
    before = ids_of(doc)["Revenue"]
    define(doc, "revenue", "C1:D2")
    assert set(ids_of(doc).values()) == {before}


def test_a_name_is_a_thing_with_its_text_as_name(doc):
    define(doc, "Revenue", "A1:B2")
    thing_id = ids_of(doc)["Revenue"]
    assert ("range", thing_id, "Revenue") in doc.model.named_things()
    assert doc.model.thing_name(thing_id) == "Revenue"
    assert doc.model.has_thing(thing_id)


def test_two_names_cannot_share_an_id(doc):
    define(doc, "Revenue", "A1:B2")
    clash = NamedRange("Costs", None, name("Costs", "C1:D2").range, id=ids_of(doc)["Revenue"])
    with pytest.raises(ValueError, match="id"):
        doc.execute(DefineName(clash), author="ana")


def test_a_name_is_removed_and_back_with_its_id(doc):
    define(doc, "Revenue", "A1:B2")
    before = ids_of(doc)
    doc.execute(RemoveName(None, "Revenue"), author="ana")
    assert not doc.model.has_thing(before["Revenue"])
    doc.undo("ana")
    assert ids_of(doc) == before


def test_a_range_is_renamed_only_as_a_name(doc):
    define(doc, "Revenue", "A1:B2")
    with pytest.raises(ValueError, match="list of names"):
        doc.execute(RenameThing(ids_of(doc)["Revenue"], "Takings"), author="ana")


# -- one namespace ----------------------------------------------------------------------------------------------
def test_a_name_cannot_be_called_like_a_sheet(doc):
    with pytest.raises(ValueError, match="There is already a sheet called “Sheet1”"):
        define(doc, "sheet1", "A1:B2")


def test_a_name_cannot_be_called_like_an_object(doc):
    put_image(doc, "i1", name="Logo")
    with pytest.raises(ValueError, match="There is already an image called “Logo”"):
        define(doc, "LOGO", "A1:B2")


def test_a_name_cannot_be_called_like_a_chart_tab(doc):
    put_chart_spec(doc)
    doc.execute(AddChart("t1", "Revenue", "c1"), author="ana")
    with pytest.raises(ValueError, match="There is already a chart called “Revenue”"):
        define(doc, "revenue", "A1:B2")


def test_a_name_cannot_be_renamed_to_that_of_a_thing(doc):
    define(doc, "Revenue", "A1:B2")
    with pytest.raises(ValueError, match="There is already a sheet called “Sheet1”"):
        doc.execute(RenameName(None, "Revenue", "SHEET1"), author="ana")
    assert set(ids_of(doc)) == {"Revenue"}


def test_a_sheet_scoped_name_is_checked_the_same(doc):
    with pytest.raises(ValueError, match="There is already a sheet called “Sheet1”"):
        define(doc, "Sheet1", "A1:B2", scope=S1)


def test_a_sheet_cannot_be_called_like_a_name(doc):
    define(doc, "Revenue", "A1:B2")
    with pytest.raises(ValueError, match="There is already a range called “Revenue”"):
        doc.execute(AddSheet("s2", "revenue"), author="ana")


def test_a_chart_tab_cannot_be_called_like_a_name(doc):
    define(doc, "Revenue", "A1:B2")
    put_chart_spec(doc)
    with pytest.raises(ValueError, match="There is already a range called “Revenue”"):
        doc.execute(AddChart("t1", "REVENUE", "c1"), author="ana")


def test_an_object_cannot_be_called_like_a_name_when_added_or_renamed(doc):
    define(doc, "Revenue", "A1:B2")
    with pytest.raises(ValueError, match="There is already a range called “Revenue”"):
        put_image(doc, "i1", name="revenue")
    put_image(doc, "i2")
    with pytest.raises(ValueError, match="There is already a range called “Revenue”"):
        doc.execute(RenameThing("i2", "Revenue"), author="ana")


def test_names_of_one_text_on_different_sheets_are_still_allowed(doc):
    doc.execute(AddSheet("s2", "Data"), author="ana")
    define(doc, "Total", "A1:A3", scope=S1)
    define(doc, "Total", "A1:A3", scope="s2", sheet="s2")
    assert len({named.id for named in doc.model.names}) == 2


def test_the_namespace_survives_reopening(doc):
    define(doc, "Revenue", "A1:B2")
    again = reopen(doc)
    with pytest.raises(ValueError, match="There is already a range called “Revenue”"):
        again.execute(AddSheet("s2", "Revenue"), author="ana")


# -- old logs -----------------------------------------------------------------------------------------------------
def old_name_data(text: str, area: str) -> dict:
    """A name as a log wrote it before names had ids."""
    data = name(text, area).to_data()
    del data["id"]
    return data


def test_an_old_workbook_with_a_sheet_and_a_name_of_one_text_opens_and_still_works():
    old = [
        {"k": "computes.AddSheet", "s": 2, "d": {"id": "s1", "name": "Sales", "index": None}},
        {"k": "computes.DefineName", "s": 1, "d": {"name": old_name_data("sales", "A1:B2")}},
        {"k": "computes.RenameName", "s": 1, "d": {"scope": None, "old": "sales", "new": "SALES"}},
    ]
    registry = WorkbookModel.registry
    commands = [registry.decode(envelope) for envelope in old]
    doc = Document(WorkbookModel(), store=MemoryStore())
    for command in commands:
        doc.execute(command, author="ana")
    assert [named.name for named in doc.model.names] == ["SALES"]
    assert doc.model.sheet("s1").name == "Sales"
    assert all(command.to_data().get("legacy_names") for command in commands)


def test_an_old_object_added_under_the_text_of_a_name_replays():
    registry = WorkbookModel.registry
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet(S1, "Sheet1"), author="ana")
    doc.execute(
        registry.decode({"k": "computes.DefineName", "s": 1, "d": {"name": old_name_data("Logo", "A1:B2")}}),
        author="ana",
    )
    doc.execute(DefineAsset("image", image_asset().to_data()), author="ana")
    obj = put_image_command(name="logo")
    command = registry.decode({"k": "core.AddObject", "s": 4, "d": obj.to_data()})
    assert command.legacy_names
    doc.execute(command, author="ana")
    assert doc.model.thing_name("i1") == "logo"
    # (and what is there is not judged again when the object is changed for something else)
    doc.execute(RenameThing("i1", "logo"), author="ana")


def put_image_command(**changes):
    return add(image_object("i1", **changes))


def test_a_new_command_does_not_write_the_legacy_marker():
    assert "legacy_names" not in DefineName(name("Revenue", "A1:B2")).to_data()
    assert "legacy_names" not in RenameName(None, "a", "b").to_data()
    assert "legacy_names" not in RenameThing("x", "y").to_data()
    assert "legacy_names" not in put_image_command().to_data()


def test_an_old_rename_of_a_thing_to_the_text_of_a_name_replays():
    old = WorkbookModel.registry.decode({"k": "core.RenameThing", "s": 1, "d": {"id": "i1", "name": "Revenue"}})
    assert old.legacy_names
    assert old.to_data()["legacy_names"] is True


def test_an_old_snapshot_is_rebuilt_from_the_log():
    assert WorkbookModel.state_schema >= 13
