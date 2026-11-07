"""The methods a table view needs: sheets, a window of cells, typing into cells, rows and columns (computes)."""

import pytest

from claudia_computes import AddSheet, WorkbookModel
from claudia_core import Document, MemoryStore
from claudia_server.auth import Account
from claudia_server.computes import computes_methods
from claudia_server.protocol import Context, Limits, RequestError, core_methods

ANN = Account("ann", "owner")
VERA = Account("vera", "viewer")


@pytest.fixture
def book():
    return Document(WorkbookModel(), store=MemoryStore())


def call(doc, name, params=None, account=ANN):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann"], lock_seconds=30.0)
    return computes_methods.dispatch(ctx, name, params)


def typed(doc, sheet, cells):
    return call(
        doc, "set_cells", {"sheet": sheet, "cells": [{"row": r, "col": c, "input": text} for r, c, text in cells]}
    )


def test_a_new_workbook_has_no_sheets_and_one_can_be_added(book):
    assert call(book, "sheets") == []
    added = call(book, "add_sheet", {"name": "Budget"})
    assert added["sheet"] == "s1" and added["revision"] == "main:1"
    assert call(book, "add_sheet", {"name": "Plan"})["sheet"] == "s2"
    assert [s["name"] for s in call(book, "sheets")] == ["Budget", "Plan"]


def test_sheet_names_must_be_new_and_nonempty(book):
    call(book, "add_sheet", {"name": "Budget"})
    for bad in ("budget", "", "   "):
        with pytest.raises(RequestError) as caught:
            call(book, "add_sheet", {"name": bad})
        assert caught.value.code in {"command_error", "bad_request"}


def test_typing_makes_numbers_text_and_booleans(book):
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(0, 0, "42"), (0, 1, "3.5"), (0, 2, "hello"), (0, 3, "true"), (0, 4, "'007"), (0, 5, " -7 ")])
    cells = {
        (r, c): v
        for r, c, v in call(book, "cells", {"sheet": "s1", "row0": 0, "row1": 9, "col0": 0, "col1": 9})["cells"]
    }
    assert cells[(0, 0)] == {"t": "int", "v": 42}
    assert cells[(0, 1)] == {"t": "float", "v": 3.5}
    assert cells[(0, 2)] == {"t": "text", "v": "hello"}
    assert cells[(0, 3)] == {"t": "bool", "v": True}
    assert cells[(0, 4)] == {"t": "text", "v": "007"}, "a leading apostrophe forces text"
    assert cells[(0, 5)] == {"t": "int", "v": -7}


def test_empty_input_clears_a_cell(book):
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(1, 1, "x")])
    typed(book, "s1", [(1, 1, "")])
    assert call(book, "cells", {"sheet": "s1", "row0": 0, "row1": 5, "col0": 0, "col1": 5})["cells"] == []


def test_a_window_returns_only_its_cells_sorted(book):
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(5, 5, "far"), (1, 1, "a"), (2, 0, "b"), (1, 0, "c")])
    window = call(book, "cells", {"sheet": "s1", "row0": 1, "row1": 2, "col0": 0, "col1": 1})["cells"]
    assert [(r, c) for r, c, _ in window] == [(1, 0), (1, 1), (2, 0)]


def test_a_window_is_limited_in_size(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError, match="too large"):
        call(book, "cells", {"sheet": "s1", "row0": 0, "row1": 100_000, "col0": 0, "col1": 100})
    with pytest.raises(RequestError):
        call(book, "cells", {"sheet": "s1", "row0": 5, "row1": 1, "col0": 0, "col1": 1})


def test_the_extent_of_a_sheet_is_reported(book):
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(9, 3, "x")])
    (info,) = call(book, "sheets")
    assert (info["rows"], info["cols"]) == (10, 4)


def test_the_extent_shrinks_back_when_its_boundary_cell_is_cleared(book):
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(9, 3, "x"), (4, 1, "y")])
    typed(book, "s1", [(9, 3, "")])  # empty input clears; row 4 / col 1 is what is left
    (info,) = call(book, "sheets")
    assert (info["rows"], info["cols"]) == (5, 2)


def test_unknown_sheets_are_errors_and_change_nothing(book):
    with pytest.raises(RequestError) as caught:
        typed(book, "nope", [(0, 0, "x")])
    assert caught.value.code == "command_error" and book.revision is None


def test_viewers_may_read_but_not_type(book):
    call(book, "add_sheet", {"name": "S"})
    assert call(book, "sheets", account=VERA)
    with pytest.raises(RequestError) as caught:
        call(book, "set_cells", {"sheet": "s1", "cells": [{"row": 0, "col": 0, "input": "x"}]}, account=VERA)
    assert caught.value.code == "forbidden"


def test_malformed_cells_are_bad_requests(book):
    call(book, "add_sheet", {"name": "S"})
    for bad in (
        [{"row": "0", "col": 0, "input": "x"}],
        [{"row": 0, "col": 0}],
        ["A1"],
        [{"row": -1, "col": 0, "input": "x"}],
    ):
        with pytest.raises(RequestError) as caught:
            call(book, "set_cells", {"sheet": "s1", "cells": bad})
        assert caught.value.code in {"bad_request", "command_error"}


def test_editing_against_an_old_view_is_stale(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError) as caught:
        call(book, "set_cells", {"sheet": "s1", "cells": [{"row": 0, "col": 0, "input": "x"}], "base": "restore-1:3"})
    assert caught.value.code == "stale"


def test_rows_and_columns_can_be_inserted_and_deleted(book):
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(0, 0, "a"), (1, 0, "b")])
    call(book, "structure", {"sheet": "s1", "axis": "row", "insert": True, "at": 1, "count": 2})
    rows = [r for r, c, v in call(book, "cells", {"sheet": "s1", "row0": 0, "row1": 9, "col0": 0, "col1": 1})["cells"]]
    assert rows == [0, 3]
    with pytest.raises(RequestError):
        call(book, "structure", {"sheet": "s1", "axis": "diagonal", "insert": True, "at": 0})


def test_computes_has_everything_the_core_has(book):
    assert core_methods.names() <= computes_methods.names()
    assert {
        "sheets",
        "cells",
        "set_cells",
        "add_sheet",
        "structure",
        "sizes",
        "resize_lines",
    } <= computes_methods.names()
    assert "sheets" not in core_methods.names()


# ------------------------------------------------------------------ row heights and column widths (D135)
def test_a_new_sheet_has_no_resized_lines(book):
    call(book, "add_sheet", {"name": "S"})
    assert call(book, "sizes", {"sheet": "s1"}) == {"revision": "main:1", "rows": [], "cols": []}


def test_resizing_rows_and_columns(book):
    call(book, "add_sheet", {"name": "S"})
    resized = call(book, "resize_lines", {"sheet": "s1", "axis": "row", "sizes": [[0, 40], [2, 50]]})
    assert resized["revision"] == "main:2"
    assert call(book, "resize_lines", {"sheet": "s1", "axis": "col", "sizes": [[1, 120]]})
    assert call(book, "sizes", {"sheet": "s1"}) == {
        "revision": "main:3",
        "rows": [[0, 40], [2, 50]],
        "cols": [[1, 120]],
    }


def test_a_null_size_clears_a_line_back_to_default(book):
    call(book, "add_sheet", {"name": "S"})
    call(book, "resize_lines", {"sheet": "s1", "axis": "row", "sizes": [[0, 40]]})
    call(book, "resize_lines", {"sheet": "s1", "axis": "row", "sizes": [[0, None]]})
    assert call(book, "sizes", {"sheet": "s1"})["rows"] == []


def test_resize_lines_rejects_a_bad_axis(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError) as caught:
        call(book, "resize_lines", {"sheet": "s1", "axis": "diagonal", "sizes": [[0, 40]]})
    assert caught.value.code == "bad_request"


def test_resize_lines_rejects_malformed_lines(book):
    call(book, "add_sheet", {"name": "S"})
    for bad in ([["0", 40]], [[0]], [[0, 40, 1]], ["A1"], [[-1, 40]], [[0, "forty"]]):
        with pytest.raises(RequestError) as caught:
            call(book, "resize_lines", {"sheet": "s1", "axis": "row", "sizes": bad})
        assert caught.value.code == "bad_request"


def test_resize_lines_rejects_a_size_outside_the_allowed_range(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError, match="between"):
        call(book, "resize_lines", {"sheet": "s1", "axis": "row", "sizes": [[0, 100_000]]})


def test_resize_lines_is_limited_in_size(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError, match="at most"):
        call(book, "resize_lines", {"sheet": "s1", "axis": "row", "sizes": [[i, 20] for i in range(1_001)]})


def test_viewers_may_read_sizes_but_not_resize(book):
    call(book, "add_sheet", {"name": "S"})
    assert call(book, "sizes", {"sheet": "s1"}, account=VERA) == {"revision": "main:1", "rows": [], "cols": []}
    with pytest.raises(RequestError) as caught:
        call(book, "resize_lines", {"sheet": "s1", "axis": "row", "sizes": [[0, 40]]}, account=VERA)
    assert caught.value.code == "forbidden"


def test_unknown_sheets_are_errors_for_sizes_too(book):
    with pytest.raises(RequestError) as caught:
        call(book, "resize_lines", {"sheet": "nope", "axis": "row", "sizes": [[0, 40]]})
    assert caught.value.code == "command_error" and book.revision is None


def test_resizing_against_an_old_view_is_stale(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError) as caught:
        call(book, "resize_lines", {"sheet": "s1", "axis": "row", "sizes": [[0, 40]], "base": "restore-1:3"})
    assert caught.value.code == "stale"


def test_the_workbook_helper_adds_sheets_to_documents_that_exist():
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet("s1", "Old"), author="ann")
    assert call(doc, "add_sheet", {"name": "New"})["sheet"] == "s2"


def window(doc, sheet="s1"):
    reply = call(doc, "cells", {"sheet": sheet, "row0": 0, "row1": 9, "col0": 0, "col1": 9})
    return {(r, c): v for r, c, v in reply["cells"]}


def test_a_formula_comes_back_with_its_value_and_its_text(book):
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(0, 0, "20"), (1, 0, "22"), (2, 0, "=sum(a1:a2)"), (0, 1, "=A1/2"), (1, 1, "=A1/0")])
    cells = window(book)
    assert cells[(2, 0)] == {"t": "int", "v": 42, "f": "=SUM(A1:A2)"}, "the text is the canonical one"
    assert cells[(0, 1)] == {"t": "float", "v": 10.0, "f": "=A1/2"}
    assert cells[(1, 1)]["t"] == "error" and cells[(1, 1)]["v"] == "#DIV/0!" and cells[(1, 1)]["f"] == "=A1/0"
    typed(book, "s1", [(0, 0, "30")])
    assert window(book)[(2, 0)]["v"] == 52, "the formula follows what it reads"


def test_a_formula_that_cannot_be_read_is_kept_so_it_can_be_corrected(book):
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(0, 0, "=1+*2")])
    assert window(book)[(0, 0)] == {"t": "error", "v": "#ERROR!", "f": "=1+*2", "d": window(book)[(0, 0)]["d"]}


def test_inserting_rows_moves_formulas_and_what_they_read(book):
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(0, 0, "5"), (1, 0, "=A1*2")])
    call(book, "structure", {"sheet": "s1", "axis": "row", "insert": True, "at": 0})
    assert window(book)[(2, 0)] == {"t": "int", "v": 10, "f": "=A2*2"}
