"""Charts (E6.6): a diagram definition shared through ``claudia_core`` (E10.16), shown as a tab, a floating
object, or both at once from the very same definition — mirroring how two image objects may share one asset."""

import pytest
from conftest import S1, add, chart_spec, diagram_object, image_asset, image_object, put_chart_spec, reopen

from claudia_computes import (
    AddChart,
    AddSheet,
    CellRef,
    ChartError,
    ChartSpec,
    DefineDiagram,
    DefineImage,
    DeleteRows,
    ForgetDiagram,
    InsertRows,
    RangeRef,
    RemoveChart,
    RemoveObject,
    RemoveSheet,
    SheetId,
    Structure,
    UpdateDiagram,
    WorkbookModel,
)
from claudia_computes.events import ChartsChanged, DiagramsChanged, ObjectsChanged
from claudia_core import Batch, Document, MemoryStore, encode


def collect(doc):
    seen = []
    doc.subscribe(seen.append)
    return seen


# -- ChartSpec itself: a self-contained format, same spirit as ShapeDefinition ---------------------------------
def test_a_chart_definition_round_trips_through_plain_data():
    spec = chart_spec(title="Revenue", legend=False)
    assert ChartSpec.from_data(spec.to_data()) == spec


def test_a_chart_definition_defaults_to_a_header_row_but_may_say_it_has_none():
    assert chart_spec().header_row is True  # the old, implied behaviour stays the default
    turned_off = chart_spec(header_row=False)
    assert turned_off.header_row is False
    assert ChartSpec.from_data(turned_off.to_data()) == turned_off
    assert ChartSpec.from_data({**chart_spec().to_data(), "header_row": False}) == turned_off
    with pytest.raises(ChartError, match="header_row"):
        ChartSpec.from_data({**chart_spec().to_data(), "header_row": "no"})


def test_a_chart_definition_needs_a_known_kind():
    with pytest.raises(ChartError, match="kind"):
        ChartSpec.from_data({**chart_spec().to_data(), "kind": "pie"})  # not yet a kind this version offers


def test_a_chart_definitions_range_must_name_its_sheet():
    """Unlike a formula, a definition has no "current sheet" to default to: it may be shown from elsewhere
    entirely, or from no sheet at all (a tab), so its range always says which sheet it reads."""
    homeless = RangeRef(CellRef(0, 0, None), CellRef(2, 1, None))
    with pytest.raises(ChartError, match="name its sheet"):
        ChartSpec.from_data({**chart_spec().to_data(), "range": homeless.to_dict()})


def test_a_chart_definition_rejects_unknown_keys_and_a_wrong_format():
    with pytest.raises(ChartError, match="unknown key"):
        ChartSpec.from_data({**chart_spec().to_data(), "surprise": True})
    with pytest.raises(ChartError, match="format"):
        ChartSpec.from_data({**chart_spec().to_data(), "format": 2})


# -- the model is the one door a definition's own geometry enters through ---------------------------------------
def test_a_chart_definition_needs_a_sheet_this_document_actually_has(doc):
    spec = chart_spec(sheet="nope")
    with pytest.raises(ValueError, match="does not know the sheet"):
        doc.execute(DefineDiagram(spec.to_data()), author="ana")


def test_a_chart_definitions_range_must_fit_inside_the_sheet(doc):
    from claudia_computes.model import MAX_COLS, MAX_ROWS

    spec = chart_spec(first=(0, 0), last=(MAX_ROWS, 0))  # one row past the edge
    with pytest.raises(ValueError, match="inside the sheet"):
        doc.execute(DefineDiagram(spec.to_data()), author="ana")
    spec = chart_spec(first=(0, 0), last=(0, MAX_COLS))
    with pytest.raises(ValueError, match="inside the sheet"):
        doc.execute(DefineDiagram(spec.to_data()), author="ana")


# -- the whole story: define, place as a floating object, move, remove, undo ------------------------------------
def test_a_diagram_is_added_with_its_definition_and_undo_takes_both_away(doc):
    spec = put_chart_spec(doc)
    doc.execute(add(diagram_object(spec_id=spec.id)), author="ana")
    assert doc.model.get_object("d1").body.diagram == spec.id
    doc.undo("ana")  # the object
    doc.undo("ana")  # the definition
    assert doc.model.objects == {} and doc.model.diagrams == {}


def test_a_definition_may_be_shown_by_a_tab_and_a_floating_object_at_once(doc):
    spec = put_chart_spec(doc)
    doc.execute(add(diagram_object("d1", spec_id=spec.id)), author="ana")
    doc.execute(AddChart("t1", "Revenue", spec.id), author="ana")
    assert set(doc.model.users_of_diagram(spec.id)) == {"d1", "t1"}
    assert len(doc.model.diagrams) == 1, "the definition is only kept once"


def test_a_diagram_object_needs_no_shape_or_image_and_keeps_no_fixed_aspect(doc):
    put_chart_spec(doc)
    doc.execute(add(diagram_object(w=400, h=100)), author="ana")  # any size above the minimum is fine
    doc.execute(add(diagram_object("d2", w=50, h=900)), author="ana")


def test_a_diagram_object_needs_a_known_definition(doc):
    with pytest.raises(ValueError, match="does not know the diagram"):
        doc.execute(add(diagram_object(spec_id="ghost")), author="ana")


def test_a_diagram_object_rejects_a_shape_or_image_alongside_the_diagram(doc):
    spec = put_chart_spec(doc)
    with pytest.raises(ValueError, match="no shape or image"):
        doc.execute(add(diagram_object(spec_id=spec.id, shape="circle")), author="ana")


def test_a_shape_or_image_object_rejects_a_diagram(doc):
    put_chart_spec(doc)
    asset = image_asset()
    doc.execute(DefineImage(asset), author="ana")
    bad = image_object(asset=asset, diagram="c1")
    with pytest.raises(ValueError, match="no shape or diagram"):
        doc.execute(add(bad), author="ana")


# -- what forget_diagram and define_diagram refuse ---------------------------------------------------------------
def test_a_diagram_in_use_cannot_be_forgotten_and_one_that_exists_cannot_be_defined_again(doc):
    spec = put_chart_spec(doc)
    doc.execute(add(diagram_object(spec_id=spec.id)), author="ana")
    with pytest.raises(ValueError, match="in use"):
        doc.execute(ForgetDiagram(spec.id), author="ana")
    with pytest.raises(ValueError, match="already"):
        doc.execute(DefineDiagram(spec.to_data()), author="ana")
    doc.execute(RemoveObject("d1"), author="ana")
    doc.execute(ForgetDiagram(spec.id), author="ana")
    assert doc.model.diagrams == {}


def test_a_diagram_shown_only_by_a_tab_cannot_be_forgotten_either(doc):
    """A tab is as much a user of a definition as a floating object is (``WorkbookModel.users_of_diagram``)."""
    spec = put_chart_spec(doc)
    doc.execute(AddChart("t1", "Revenue", spec.id), author="ana")
    with pytest.raises(ValueError, match="in use"):
        doc.execute(ForgetDiagram(spec.id), author="ana")
    doc.execute(RemoveChart("t1"), author="ana")
    doc.execute(ForgetDiagram(spec.id), author="ana")  # no user left


# -- editing a diagram in place: the one way its content ever changes --------------------------------------------
def test_updating_a_diagram_changes_it_in_place_for_every_user_and_undo_restores_it(doc):
    spec = put_chart_spec(doc, title="Before")
    doc.execute(add(diagram_object(spec_id=spec.id)), author="ana")
    doc.execute(AddChart("t1", "Revenue", spec.id), author="ana")
    changed = spec.to_data() | {"title": "After"}
    doc.execute(UpdateDiagram(spec.id, changed), author="ana")
    assert doc.model.diagrams[spec.id].title == "After"
    doc.undo("ana")
    assert doc.model.diagrams[spec.id].title == "Before"


def test_updating_a_diagram_cannot_change_its_id(doc):
    spec = put_chart_spec(doc)
    with pytest.raises(ValueError, match="cannot change its id"):
        doc.execute(UpdateDiagram(spec.id, chart_spec("other").to_data()), author="ana")


# -- chart tabs: add, remove, undo, and what they refuse ---------------------------------------------------------
def test_a_chart_tab_is_added_and_undo_removes_it(doc):
    spec = put_chart_spec(doc)
    doc.execute(AddChart("t1", "Revenue", spec.id), author="ana")
    assert list(doc.model.charts) == ["t1"]
    doc.undo("ana")
    assert doc.model.charts == {}


def test_a_chart_tab_needs_a_defined_diagram(doc):
    with pytest.raises(ValueError, match="does not know the diagram"):
        doc.execute(AddChart("t1", "Revenue", "ghost"), author="ana")


def test_chart_tab_ids_and_names_must_be_unique(doc):
    spec = put_chart_spec(doc)
    doc.execute(AddChart("t1", "Revenue", spec.id), author="ana")
    with pytest.raises(ValueError, match="exists"):
        doc.execute(AddChart("t1", "Another", spec.id), author="ana")
    with pytest.raises(ValueError, match="exists"):
        doc.execute(AddChart("t2", "Revenue", spec.id), author="ana")


def test_removing_a_chart_tab_does_not_forget_its_definition(doc):
    """The definition survives the tab's removal (and an object's) so that undo can bring the tab back."""
    spec = put_chart_spec(doc)
    doc.execute(AddChart("t1", "Revenue", spec.id), author="ana")
    doc.execute(RemoveChart("t1"), author="ana")
    assert spec.id in doc.model.diagrams


def test_chart_tabs_keep_their_order(doc):
    a, b = put_chart_spec(doc, "ca"), put_chart_spec(doc, "cb")
    doc.execute(AddChart("t1", "A", a.id), author="ana")
    doc.execute(AddChart("t2", "B", b.id), author="ana")
    doc.execute(AddChart("t0", "Zero", a.id, index=0), author="ana")
    assert list(doc.model.charts) == ["t0", "t1", "t2"]


# -- a sheet a chart still reads from cannot be removed -----------------------------------------------------------
def test_a_sheet_a_charts_range_still_reads_from_cannot_be_removed(doc):
    doc.execute(AddSheet("s2", "Sheet2"), author="ana")
    put_chart_spec(doc, sheet="s2")
    with pytest.raises(ValueError, match="still has chart"):
        doc.execute(RemoveSheet("s2"), author="ana")
    doc.execute(RemoveSheet(S1), author="ana")  # a different sheet: nothing stops this


def test_removing_a_sheet_removes_its_diagram_objects_but_not_their_definitions(doc):
    spec = put_chart_spec(doc)  # the definition's range is on S1, same as the object
    doc.execute(AddSheet("s2", "Sheet2"), author="ana")
    doc.execute(add(diagram_object(sheet="s2", spec_id=spec.id)), author="ana")
    with pytest.raises(ValueError, match="still has chart"):
        doc.execute(RemoveSheet(S1), author="ana")  # the definition's own range is still here
    doc.execute(RemoveSheet("s2"), author="ana")  # only the floating object sat here
    assert doc.model.objects == {}
    assert spec.id in doc.model.diagrams


# -- views are told ------------------------------------------------------------------------------------------------
def test_views_hear_about_diagrams(doc):
    seen = collect(doc)
    spec = chart_spec()
    doc.execute(DefineDiagram(spec.to_data()), author="ana")
    changed = [e for e in seen if isinstance(e, DiagramsChanged)]
    assert changed[0].to_data() == {"type": "diagram", "id": spec.id, "definition": spec.to_data()}
    doc.execute(ForgetDiagram(spec.id), author="ana")
    assert [e for e in seen if isinstance(e, DiagramsChanged)][-1].to_data() == {
        "type": "diagram",
        "id": spec.id,
        "definition": None,
    }


def test_views_hear_about_chart_tabs(doc):
    seen = collect(doc)
    spec = put_chart_spec(doc)
    doc.execute(AddChart("t1", "Revenue", spec.id), author="ana")
    assert any(isinstance(e, ChartsChanged) for e in seen)


def test_adding_a_diagram_object_emits_objects_changed(doc):
    seen = collect(doc)
    spec = put_chart_spec(doc)
    doc.execute(add(diagram_object(spec_id=spec.id)), author="ana")
    told = next(e for e in seen if isinstance(e, ObjectsChanged) and e.changed)
    assert told.changed[0].body.kind == "diagram"


# -- the history reads like sentences -------------------------------------------------------------------------
def test_the_history_has_a_sentence_for_a_diagram_object_and_a_chart_tab():
    spec = chart_spec()
    obj = diagram_object(spec_id=spec.id)
    assert add(obj).label == "Add diagram"
    assert add(obj).summary == "Added a diagram"
    assert AddChart("t1", "Revenue", spec.id).label == "Add chart"
    assert "Revenue" in AddChart("t1", "Revenue", spec.id).summary
    assert RemoveChart("t1").summary == "remove a chart"


# -- documents are forever: schema, round trips, snapshots -----------------------------------------------------
def test_command_data_round_trips_for_diagrams_and_charts():
    spec = chart_spec()
    obj = diagram_object(spec_id=spec.id)
    core_commands = (DefineDiagram(spec.to_data()), ForgetDiagram(spec.id), add(obj))
    for command in core_commands:
        # Diagram definitions are shared by all three apps, so their commands are namespaced ``core.`` (E10.16).
        assert command.kind.startswith("core.")
        assert WorkbookModel.registry.decode(encode(command)) == command
    computes_commands = (AddChart("t1", "Revenue", spec.id), RemoveChart("t1"))
    for command in computes_commands:
        assert command.kind.startswith("computes.")
        assert WorkbookModel.registry.decode(encode(command)) == command


def test_every_chart_command_survives_the_log_and_a_model_survives_its_snapshot(doc):
    spec = put_chart_spec(doc)
    doc.execute(add(diagram_object(spec_id=spec.id)), author="ana")
    doc.execute(AddChart("t1", "Revenue", spec.id), author="ana")
    assert reopen(doc).model.serialize() == doc.model.serialize()
    assert WorkbookModel.restore(doc.model.serialize()).serialize() == doc.model.serialize()


def test_equal_states_serialize_equally_with_a_shared_definition_whatever_order(doc):
    spec = put_chart_spec(doc)
    doc.execute(add(diagram_object("d1", spec_id=spec.id)), author="ana")
    doc.execute(AddChart("t1", "Revenue", spec.id), author="ana")
    other = Document(WorkbookModel(), store=MemoryStore())
    other.execute(AddSheet(S1, "Sheet1"), author="x")
    other.execute(Batch((DefineDiagram(spec.to_data()), add(diagram_object("d1", spec_id=spec.id)))), author="x")
    other.execute(AddChart("t1", "Revenue", spec.id), author="x")
    assert other.model.serialize() == doc.model.serialize()


# -- a chart's range is frozen, the same policy an object's anchor already has (an open decision, not a bug) ----
def test_a_charts_range_does_not_follow_a_structural_edit():
    """Documented, not (yet) resolved (see ``charts.py``): unlike a formula, inserting or deleting rows above a
    chart's range leaves the range exactly as it was typed, even though the data it named has since moved."""
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet(S1, "Sheet1"), author="ana")
    spec = put_chart_spec(doc, first=(5, 0), last=(7, 1))
    doc.execute(Structure(InsertRows(S1, 0, 3)), author="ana")
    assert doc.model.diagrams[spec.id].range.to_dict() == spec.range.to_dict()
    doc.execute(Structure(DeleteRows(S1, 0, 3)), author="ana")
    assert doc.model.diagrams[spec.id].range.to_dict() == spec.range.to_dict()


def test_a_charts_range_may_end_up_pointing_at_rows_that_no_longer_exist():
    """A consequence of the policy above, called out explicitly rather than silently tolerated: deleting the
    rows a chart's range named leaves the range as it was, now describing cells that are gone."""
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet(S1, "Sheet1"), author="ana")
    spec = put_chart_spec(doc, first=(0, 0), last=(2, 1))
    doc.execute(Structure(DeleteRows(S1, 0, 5)), author="ana")
    assert doc.model.diagrams[spec.id].range.to_dict() == spec.range.to_dict()
    assert doc.model.sheet(SheetId(S1)).rows_used == 0  # the sheet itself is now empty where the range still points
