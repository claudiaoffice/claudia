"""Cell styles: style ranges per sheet, in layers, for the box and the words of a cell (E6.13, D307, D311, D313)."""

import random

import pytest

from claudia_computes import (
    AddSheet,
    CellStyles,
    DeleteCols,
    DeleteRows,
    InsertCols,
    InsertRows,
    RemoveSheet,
    SetCells,
    SetCellStyle,
    Structure,
    WorkbookModel,
    layer_of,
    parse_input,
)
from claudia_computes import cellstyles as cellstyles_module
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_core import Document, MemoryStore, RemoveStyle

S1 = "s1"
LAST_ROW, LAST_COL = MAX_ROWS - 1, MAX_COLS - 1


@pytest.fixture
def doc():
    d = Document(WorkbookModel(), store=MemoryStore())
    d.execute(AddSheet(S1, "Sheet1"), author="ana")
    return d


def styles(doc) -> CellStyles:
    return doc.model.sheet(S1).cell_styles


def put(doc, area, style, slot="both", author="ana"):
    """What a person does: style an area, the last action winning (D317)."""
    for one in ("box", "words") if slot == "both" else (slot,):
        doc.execute(SetCellStyle.applying(doc.model, S1, one, area, style), author=author)


def at(doc, row, col, slot="words"):
    return styles(doc).style_at(row, col, slot)


def column(c0, c1=None):
    return (0, c0, LAST_ROW, c0 if c1 is None else c1)


def row(r0, r1=None):
    return (r0, 0, r0 if r1 is None else r1, LAST_COL)


# ----------------------------------------------------------------------------- layers
def test_the_layer_of_a_range_follows_from_its_shape():
    assert layer_of((0, 0, LAST_ROW, LAST_COL)) == "sheet"
    assert layer_of(column(2)) == "column"
    assert layer_of(row(4, 6)) == "row"
    assert layer_of((1, 1, 1, 1)) == "range"
    assert layer_of((0, 0, LAST_ROW - 1, 3)) == "range"


def test_a_cell_no_range_covers_is_body_text():
    """D313: Body text is what a cell has when no style range says otherwise."""
    d = Document(WorkbookModel(), store=MemoryStore())
    d.execute(AddSheet(S1, "Sheet1"), author="ana")
    assert at(d, 0, 0) == ("body-text", "default") and at(d, 0, 0, "box") == ("body-text", "default")


def test_the_last_action_wins_whatever_layer_it_is_in(doc):
    """D317: styling a whole column after some of its cells gives every cell of the column the new style."""
    put(doc, (2, 2, 3, 3), "input")  # a range first
    put(doc, column(2), "header")  # then the whole column: the range's cells too
    assert at(doc, 2, 2) == ("header", "column") and at(doc, 9, 2) == ("header", "column")
    put(doc, (2, 2, 2, 2), "input")  # then one cell again
    assert at(doc, 2, 2) == ("input", "range") and at(doc, 3, 2) == ("header", "column")
    put(doc, row(9), "result")  # a whole row, crossing the column
    assert at(doc, 9, 2) == ("result", "row") and at(doc, 9, 7) == ("result", "row")
    put(doc, column(2), "note")  # the column again, crossing the row: the column wins where they cross
    assert at(doc, 9, 2)[0] == "note" and at(doc, 9, 7) == ("result", "row") and at(doc, 2, 2) == ("note", "column")
    put(doc, (0, 0, LAST_ROW, LAST_COL), "body-text")  # the whole sheet: everything
    assert {at(doc, r, c) for r in range(12) for c in range(8)} == {("body-text", "sheet")}


def test_one_action_is_one_undo_step(doc):
    put(doc, (2, 2, 3, 3), "input", slot="words")
    put(doc, row(3), "result", slot="words")
    before = look(doc)
    put(doc, column(2), "header", slot="words")
    doc.undo("ana")
    assert look(doc) == before


def test_clearing_lets_what_lies_beneath_show_through(doc):
    """“Clear cell style” (D317): the cells' own style goes, the column's shows again."""
    put(doc, column(1), "input", slot="words")
    put(doc, (4, 1, 5, 1), "note", slot="words")
    put(doc, (4, 1, 5, 1), None, slot="words")
    assert at(doc, 4, 1) == ("input", "column")
    put(doc, column(1), None, slot="words")
    assert at(doc, 4, 1) == ("body-text", "default")


def test_inside_a_layer_a_new_range_cuts_what_was_there(doc):
    put(doc, (0, 0, 9, 9), "header", slot="words")
    put(doc, (3, 3, 5, 5), "input", slot="words")
    assert at(doc, 4, 4) == ("input", "range") and at(doc, 2, 2) == ("header", "range")
    assert at(doc, 9, 9) == ("header", "range")
    assert len(styles(doc)) == 5  # the hole cut the header range into four pieces around the input


def test_the_two_slots_are_separate(doc):
    """D309: a deviation may change the box only, and then the two slots of a cell name different styles."""
    put(doc, (0, 0, 2, 2), "header")
    put(doc, (0, 0, 2, 2), "result", slot="box")
    assert at(doc, 1, 1, "box") == ("result", "range") and at(doc, 1, 1, "words") == ("header", "range")


# ----------------------------------------------------------------------------- kinds and slots (D304, D316)
def test_a_cells_box_takes_a_box_style_or_a_bundle_and_its_words_only_a_paragraph_style(doc):
    put(doc, (0, 0, 0, 0), "plain-box", slot="box")
    put(doc, (0, 0, 0, 0), "header", slot="box")
    with pytest.raises(ValueError, match="cannot be put into the words of a cell"):
        put(doc, (0, 0, 0, 0), "plain-box", slot="words")
    with pytest.raises(ValueError, match="cannot be put into the box of a cell"):
        put(doc, (0, 0, 0, 0), "plain-shape", slot="box")
    with pytest.raises(ValueError, match="no style"):
        put(doc, (0, 0, 0, 0), "sparkly")


@pytest.mark.parametrize(
    "command",
    [
        SetCellStyle(S1, "border", "range", (0, 0, 0, 0), ()),
        SetCellStyle(S1, "box", "column", (0, 0, 0, 0), (((0, 0, 0, 0), "header"),)),
        SetCellStyle(S1, "box", "sheet-ish", (0, 0, 0, 0), ()),
        SetCellStyle(S1, "box", "range", (0, 0, 2, 2), (((0, 0, 3, 3), "header"),)),
        SetCellStyle(S1, "box", "range", (3, 3, 1, 1), ()),
        SetCellStyle(S1, "box", "range", (0, 0, 2, 2), (((0, 0, 1, 1), "header"), ((1, 1, 2, 2), "note"))),
    ],
)
def test_a_change_that_does_not_hold_together_changes_nothing(doc, command):
    with pytest.raises(ValueError):
        doc.execute(command, author="ana")
    assert len(styles(doc)) == 0


def test_a_style_cells_use_cannot_be_taken_back(doc):
    put(doc, (0, 0, 0, 0), "note", slot="words")
    with pytest.raises(ValueError, match="in use"):
        doc.execute(RemoveStyle("note"), author="ana")


def test_the_change_holds_the_cells_it_styles(doc):
    (region,) = SetCellStyle.put(S1, "box", (1, 2, 3, 4), "header").regions(doc.model)
    assert (region.range.first.row, region.range.first.col, region.range.last.row, region.range.last.col) == (
        1,
        2,
        3,
        4,
    )


# ----------------------------------------------------------------------------- undo, the log, a snapshot
def look(doc, rows=12, cols=12):
    return {(r, c, s): at(doc, r, c, s) for r in range(rows) for c in range(cols) for s in ("box", "words")}


def test_undo_puts_back_exactly_what_the_area_held(doc):
    """Every cell looks as it did; the hole the change cut stays as pieces, which is how the ranges are stored."""
    put(doc, (0, 0, 9, 9), "header", slot="words")
    before = look(doc)
    put(doc, (3, 3, 5, 5), "input", slot="words")
    doc.undo("ana")
    assert look(doc) == before
    doc.redo("ana")
    assert at(doc, 4, 4) == ("input", "range")


def test_undo_refuses_to_restyle_cells_a_colleague_styled_since(doc):
    put(doc, (0, 0, 3, 3), "header", slot="words", author="ana")
    put(doc, (2, 2, 5, 5), "note", slot="words", author="ben")
    with pytest.raises(Exception, match="overwrite their work"):
        doc.undo("ana")


def test_the_ranges_survive_the_log_and_a_snapshot(doc):
    put(doc, (0, 0, 9, 9), "header")
    put(doc, column(3), "input", slot="words")
    rebuilt = WorkbookModel.restore(doc.model.serialize())
    assert rebuilt.sheet(S1).cell_styles.to_data() == styles(doc).to_data()
    command = SetCellStyle.put(S1, "words", (1, 1, 2, 2), "note")
    assert SetCellStyle.from_data(command.to_data(), WorkbookModel.registry) == command
    assert command.summary == "B2:C3 words: note"
    assert SetCellStyle.put(S1, "box", column(3), None).summary == "column D box: no style"


# ----------------------------------------------------------------------------- rows and columns move the ranges
def test_inserting_rows_inside_a_range_grows_it_and_below_it_moves_it(doc):
    put(doc, (2, 0, 4, 0), "header", slot="words")
    put(doc, (8, 0, 8, 0), "note", slot="words")
    doc.execute(Structure(InsertRows(S1, 3, 2)), author="ana")
    assert [at(doc, r, 0)[0] for r in range(1, 8)] == [
        "body-text",
        "header",
        "header",
        "header",
        "header",
        "header",
        "body-text",
    ]
    assert at(doc, 10, 0) == ("note", "range")


def test_a_column_style_stays_whole_when_rows_come_and_go(doc):
    put(doc, column(1), "input", slot="words")
    doc.execute(Structure(DeleteRows(S1, 0, 5)), author="ana")
    doc.execute(Structure(InsertRows(S1, 0, 3)), author="ana")
    assert styles(doc).to_data() == [["words", "column", 0, 1, LAST_ROW, 1, "input"]]


def test_deleting_rows_and_undoing_it_brings_every_style_back(doc):
    put(doc, (2, 0, 9, 3), "header", slot="words")
    put(doc, (4, 1, 4, 1), "input", slot="words")
    put(doc, row(5), "note", slot="box")
    look = {(r, c, s): at(doc, r, c, s)[0] for r in range(12) for c in range(5) for s in ("box", "words")}
    doc.execute(Structure(DeleteRows(S1, 3, 3)), author="ana")
    assert at(doc, 3, 0) == ("header", "range") and at(doc, 4, 1) == ("header", "range")
    doc.undo("ana")
    assert {(r, c, s): at(doc, r, c, s)[0] for r in range(12) for c in range(5) for s in ("box", "words")} == look


def test_deleting_columns_moves_ranges_left(doc):
    put(doc, (0, 5, 2, 6), "result", slot="words")
    doc.execute(Structure(DeleteCols(S1, 1, 2)), author="ana")
    assert at(doc, 0, 3) == ("result", "range") and at(doc, 0, 5) == ("body-text", "default")
    doc.execute(Structure(InsertCols(S1, 0, 1)), author="ana")
    assert at(doc, 0, 4) == ("result", "range")


def test_removing_a_sheet_and_undoing_it_brings_its_styles_back(doc):
    doc.execute(AddSheet("s2", "Sheet2"), author="ana")
    put(doc, (0, 0, 2, 2), "header")
    put(doc, column(4), "input", slot="words")
    before = styles(doc).to_data()
    doc.execute(RemoveSheet(S1), author="ana")
    doc.undo("ana")
    assert styles(doc).to_data() == before


def test_typing_into_a_cell_leaves_its_style_alone(doc):
    put(doc, (0, 0, 0, 0), "input")
    doc.execute(SetCells(S1, ((0, 0, parse_input("42")),)), author="ana")
    assert at(doc, 0, 0) == ("input", "range")


# ----------------------------------------------------------------------------- limits
def test_a_sheet_holds_a_bounded_number_of_ranges(doc, monkeypatch):
    monkeypatch.setattr(cellstyles_module, "MAX_STYLE_RANGES", 3)
    for i in range(3):
        put(doc, (i * 2, 0, i * 2, 0), "note", slot="words")
    with pytest.raises(ValueError, match="at most 3 style ranges"):
        put(doc, (10, 0, 10, 0), "note", slot="words")


# ----------------------------------------------------------------------------- the same as styling cell by cell
WINDOW_ROWS, WINDOW_COLS = 30, 14
PICK = ("header", "input", "result", "note", None)


def _random_area(rng):
    shape = rng.random()
    if shape < 0.1:
        return (0, 0, LAST_ROW, LAST_COL)
    if shape < 0.25:
        c = rng.randrange(8)
        return column(c, c + rng.randrange(2))
    if shape < 0.4:
        r = rng.randrange(10)
        return row(r, r + rng.randrange(3))
    r0, c0 = rng.randrange(12), rng.randrange(8)
    return (r0, c0, r0 + rng.randrange(5), c0 + rng.randrange(4))


class Brute:
    """The same thing, cell by cell, in a window that covers everything a random step can reach."""

    def __init__(self):
        self.sheet = {"box": None, "words": None}
        self.columns = {"box": {}, "words": {}}
        self.rows = {"box": {}, "words": {}}
        self.cells = {"box": {}, "words": {}}

    def put(self, slot, area, style):
        """The last action wins (D317), the layers kept: the action's layer takes the style, and what is more
        specific inside the area goes — except a whole row crossing a styled column, which the cell overrides."""
        r0, c0, r1, c1 = area
        layer = layer_of(area)
        cells = self.cells[slot]
        inside = [(r, c) for (r, c) in cells if r0 <= r <= r1 and c0 <= c <= c1]
        if layer == "sheet":
            self.sheet[slot] = style
            self.rows[slot], self.columns[slot], self.cells[slot] = {}, {}, {}
            return
        if layer == "range":
            self._assign(cells, [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)], style)
            return
        for key in inside:
            del cells[key]
        if layer == "row":
            self._assign(self.rows[slot], range(r0, r1 + 1), style)
            return
        self._assign(self.columns[slot], range(c0, c1 + 1), style)
        if style is not None:
            self._assign(cells, [(r, c) for r in self.rows[slot] for c in range(c0, c1 + 1)], style)

    @staticmethod
    def _assign(target, keys, style):
        for key in keys:
            if style is None:
                target.pop(key, None)
            else:
                target[key] = style

    def delete(self, axis, at, count):
        def shift(index):
            return None if at <= index < at + count else (index - count if index >= at + count else index)

        for slot in ("box", "words"):
            if axis == "row":
                self.rows[slot] = {n: s for i, s in self.rows[slot].items() if (n := shift(i)) is not None}
                self.cells[slot] = {(n, c): s for (r, c), s in self.cells[slot].items() if (n := shift(r)) is not None}
            else:
                self.columns[slot] = {n: s for i, s in self.columns[slot].items() if (n := shift(i)) is not None}
                self.cells[slot] = {(r, n): s for (r, c), s in self.cells[slot].items() if (n := shift(c)) is not None}

    def at(self, r, c, slot):
        for found in (
            self.cells[slot].get((r, c)),
            self.rows[slot].get(r),
            self.columns[slot].get(c),
            self.sheet[slot],
        ):
            if found is not None:
                return found
        return "body-text"


@pytest.mark.parametrize("seed", range(12))
def test_ranges_behave_exactly_like_styling_every_cell_and_undo_takes_it_all_back(seed):
    """The brute-force check the plan asks for (step 1.6): a random sequence of styling, clearing and deleting
    rows and columns gives the same style for every cell as doing it cell by cell; undoing everything gives an
    empty sheet again."""
    rng = random.Random(seed)
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet(S1, "Sheet1"), author="ana")
    brute = Brute()
    steps = 0
    for _ in range(40):
        if rng.random() < 0.15:
            axis = rng.choice(("row", "col"))
            at_, count = rng.randrange(10), 1 + rng.randrange(3)
            doc.execute(Structure((DeleteRows if axis == "row" else DeleteCols)(S1, at_, count)), author="ana")
            brute.delete(axis, at_, count)
        else:
            slot, area, style = rng.choice(("box", "words")), _random_area(rng), rng.choice(PICK)
            doc.execute(SetCellStyle.applying(doc.model, S1, slot, area, style), author="ana")
            brute.put(slot, area, style)
            if style is not None:  # D317 itself: every cell of the area now has the style
                r0, c0, r1, c1 = area
                for r in range(r0, min(r1, WINDOW_ROWS - 1) + 1):
                    for c in range(c0, min(c1, WINDOW_COLS - 1) + 1):
                        assert at(doc, r, c, slot)[0] == style, (seed, steps, r, c)
        steps += 1
        for r in range(WINDOW_ROWS):
            for c in range(WINDOW_COLS):
                for slot in ("box", "words"):
                    assert at(doc, r, c, slot)[0] == brute.at(r, c, slot), (seed, steps, r, c, slot)
    for _ in range(steps):
        doc.undo("ana")
    assert {(r, c): at(doc, r, c)[0] for r in range(WINDOW_ROWS) for c in range(WINDOW_COLS)} == {
        (r, c): "body-text" for r in range(WINDOW_ROWS) for c in range(WINDOW_COLS)
    }
