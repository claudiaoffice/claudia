"""Deleting a style in a workbook (E1.10, D226): the style ranges that name it keep their look."""

import pytest

from claudia_computes import AddSheet, SetCellStyle, WorkbookModel
from claudia_core import CreateStyle, Document, MemoryStore, StyleDef, plan_delete_style

S1 = "s1"


@pytest.fixture
def doc():
    d = Document(WorkbookModel(), store=MemoryStore())
    d.execute(AddSheet(S1, "Sheet1"), author="ana")
    return d


def test_the_ranges_that_name_a_deleted_style_move_to_its_stand_in_and_undo_puts_them_back(doc):
    doc.execute(
        CreateStyle(StyleDef("tint", "Tint", "a pale cell", None, {"background-color": "#eeeeee"}, kind="box")),
        author="ana",
    )
    doc.execute(SetCellStyle.put(S1, "box", (0, 0, 1, 1), "tint"), author="ana")
    doc.execute(SetCellStyle.put(S1, "box", (5, 5, 5, 5), "tint"), author="ana")
    before = doc.model.sheet(S1).cell_styles.to_data()
    book_before = doc.model.styles.to_data()

    plan = plan_delete_style(doc.model, "tint", how="rebase", target="plain-box")
    doc.execute(plan, author="ana")

    stand_in = doc.model.styles.get("tint-kept")
    assert "tint" not in doc.model.styles and stand_in.to_name and stand_in.kind == "box"
    assert doc.model.sheet(S1).cell_styles.style_at(0, 0, "box")[0] == "tint-kept"
    assert doc.model.sheet(S1).cell_styles.style_at(5, 5, "box")[0] == "tint-kept"
    assert not doc.model.style_in_use("tint")
    doc.undo("ana")
    assert doc.model.sheet(S1).cell_styles.to_data() == before
    assert doc.model.styles.to_data() == book_before


def test_a_built_in_cell_style_can_only_be_hidden(doc):
    ids = [s.id for s in doc.model.styles if s.kind == "box"]
    assert ids
    with pytest.raises(ValueError, match="built-in style and can only be hidden"):
        plan_delete_style(doc.model, ids[0])


def test_assigning_the_plain_box_puts_the_ranges_under_it(doc):
    doc.execute(
        CreateStyle(StyleDef("tint", "Tint", "a pale cell", None, {"background-color": "#eeeeee"}, kind="box")),
        author="ana",
    )
    doc.execute(SetCellStyle.put(S1, "box", (0, 0, 1, 1), "tint"), author="ana")
    doc.execute(plan_delete_style(doc.model, "tint", how="assign", target="plain-box"), author="ana")
    assert doc.model.sheet(S1).cell_styles.style_at(0, 0, "box")[0] == "plain-box"
    doc.undo("ana")
    assert doc.model.sheet(S1).cell_styles.style_at(0, 0, "box")[0] == "tint"
