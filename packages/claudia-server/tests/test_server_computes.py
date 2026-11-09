"""The methods a table view needs: sheets, a window of cells, typing into cells, rows and columns (computes)."""

import base64
import struct

import pytest

from claudia_computes import AddSheet, WorkbookModel
from claudia_core import Document, MemoryStore
from claudia_server.auth import Account
from claudia_server.computes import computes_methods
from claudia_server.protocol import Context, Limits, RequestError, core_methods

ANN = Account("ann", "owner")
BEN = Account("ben", "editor")
VERA = Account("vera", "viewer")


@pytest.fixture
def book():
    return Document(WorkbookModel(), store=MemoryStore())


def call(doc, name, params=None, account=ANN):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0)
    return computes_methods.dispatch(ctx, name, params)


def typed(doc, sheet, cells):
    return call(
        doc, "set_cells", {"sheet": sheet, "cells": [{"row": r, "col": c, "input": text} for r, c, text in cells]}
    )


def tiny_gif(width=40, height=20) -> str:
    """A tiny, valid GIF (no real pixels), base64-encoded as a client would send it."""
    header = b"GIF89a" + struct.pack("<HHBBB", width, height, 0, 0, 0)
    frame = b"\x2c" + struct.pack("<HHHH", 0, 0, width, height) + b"\x00" + b"\x02\x01\x00\x00"
    return base64.b64encode(header + frame + b"\x3b").decode("ascii")


def add_image(doc, **params):
    given = {
        "sheet": "s1",
        "row": 2,
        "col": 2,
        "w": 400,
        "h": 200,
        "data": tiny_gif(400, 200),
        "alt": "a sample picture",
        "source_name": "pic.gif",
        **params,
    }
    return call(doc, "add_image", given)["object"]


def objects(doc, sheet="s1", account=ANN):
    return call(doc, "objects", {"sheet": sheet}, account=account)["objects"]


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


# -- images and floating objects (E10.11): add_image, move_object, remove_object, and the never-resize guarantee
def test_an_image_is_imported_and_anchored_to_a_cell(book):
    call(book, "add_sheet", {"name": "S"})
    added = add_image(book)
    (obj,) = objects(book)
    assert obj["id"] == added
    assert (obj["kind"], obj["anchor"]["row"], obj["anchor"]["col"], obj["w"], obj["h"]) == ("image", 2, 2, 400, 200)
    assert obj["image"] is not None
    assert obj["imported"]["alt"] == "a sample picture" and obj["imported"]["source"] == "disk"
    assert [i["id"] for i in call(book, "images")] == [obj["image"]]


def test_the_asset_is_shared_between_two_objects_using_the_same_picture(book):
    call(book, "add_sheet", {"name": "S"})
    data = tiny_gif(300, 150)
    first = add_image(book, w=300, h=150, data=data, alt="a")
    second = add_image(book, row=5, w=300, h=150, data=data, alt="b")
    assert first != second
    assert len(call(book, "images")) == 1, "the identical picture is decoded once and shared"


def test_an_image_keeps_its_proportions(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError, match="proportions") as caught:
        add_image(book, data=tiny_gif(400, 200), w=400, h=800)
    assert caught.value.code == "command_error"


def test_add_image_needs_a_real_image_and_a_description(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError) as caught:
        add_image(book, data="not an image at all!!")
    assert caught.value.code == "bad_request"  # not valid base64

    not_a_picture = base64.b64encode(b"hello, this is not a picture").decode("ascii")
    with pytest.raises(RequestError) as caught:
        add_image(book, data=not_a_picture)
    assert caught.value.code == "command_error"  # understood as a request, refused as an image


def test_moving_an_object_keeps_its_size_and_undo_puts_it_back(book):
    call(book, "add_sheet", {"name": "S"})
    added = add_image(book)
    call(book, "move_object", {"id": added, "row": 8, "col": 3})
    (obj,) = objects(book)
    assert (obj["anchor"]["row"], obj["anchor"]["col"], obj["w"], obj["h"]) == (8, 3, 400, 200)
    book.undo("ann")
    (obj,) = objects(book)
    assert (obj["anchor"]["row"], obj["anchor"]["col"]) == (2, 2)


def test_removing_an_object_is_one_step_and_undo_brings_it_and_its_image_back(book):
    call(book, "add_sheet", {"name": "S"})
    added = add_image(book)
    assert book.history_for("ann").undo_label == "Add image"
    call(book, "remove_object", {"id": added})
    assert objects(book) == []
    book.undo("ann")
    assert [o["id"] for o in objects(book)] == [added]
    assert len(call(book, "images")) == 1


def test_inserting_or_deleting_rows_and_columns_never_moves_or_resizes_an_object(book):
    call(book, "add_sheet", {"name": "S"})
    added = add_image(book, row=5, col=5, w=400, h=200)
    call(book, "structure", {"sheet": "s1", "axis": "row", "insert": True, "at": 0, "count": 3})
    call(book, "structure", {"sheet": "s1", "axis": "col", "insert": False, "at": 0, "count": 1})
    (obj,) = objects(book)
    assert obj["id"] == added
    assert (obj["anchor"]["row"], obj["anchor"]["col"], obj["w"], obj["h"]) == (5, 5, 400, 200)


def test_resizing_rows_or_columns_never_resizes_an_object(book):
    call(book, "add_sheet", {"name": "S"})
    add_image(book, row=1, col=1, w=400, h=200)
    call(book, "resize_lines", {"sheet": "s1", "axis": "row", "sizes": [[1, 60]]})
    call(book, "resize_lines", {"sheet": "s1", "axis": "col", "sizes": [[1, 300]]})
    (obj,) = objects(book)
    assert (obj["w"], obj["h"]) == (400, 200)


def test_the_source_path_is_sent_only_to_the_person_who_imported_the_image(book):
    call(book, "add_sheet", {"name": "S"})
    box = add_image(book, source_path="/Users/ann/Documents/chart.gif")  # imported by ANN
    (seen_by_importer,) = objects(book, account=ANN)
    assert seen_by_importer["imported"]["source_path"] == "/Users/ann/Documents/chart.gif"

    (seen_by_colleague,) = objects(book, account=BEN)
    assert seen_by_colleague["imported"]["source_path"] is None
    assert seen_by_colleague["imported"]["source"] == "disk"  # not hidden: only the path is
    assert seen_by_colleague["imported"]["imported_by"] == "ann"  # not hidden either
    assert seen_by_colleague["id"] == box


def test_viewers_may_look_at_images_but_not_add_one(book):
    call(book, "add_sheet", {"name": "S"})
    assert call(book, "images", account=VERA) == []
    with pytest.raises(RequestError) as caught:
        call(
            book,
            "add_image",
            {
                "sheet": "s1",
                "row": 0,
                "col": 0,
                "w": 100,
                "h": 50,
                "data": tiny_gif(100, 50),
                "alt": "x",
                "source_name": "x",
            },
            account=VERA,
        )
    assert caught.value.code == "forbidden"


def test_removing_a_sheet_takes_its_objects_with_it_and_undo_restores_them(book):
    """There is no `remove_sheet` method on the wire yet (a pre-existing gap, not introduced here), so this
    goes through the document directly, the way `claudia_computes`' own tests do."""
    from claudia_computes import RemoveSheet

    call(book, "add_sheet", {"name": "S"})
    added = add_image(book)
    book.execute(RemoveSheet("s1"), author="ann")
    assert call(book, "sheets") == []
    book.undo("ann")
    assert [s["id"] for s in call(book, "sheets")] == ["s1"]
    assert [o["id"] for o in objects(book)] == [added]


def test_functions_lists_the_whole_catalog_with_no_query(book):
    found = call(book, "functions")
    names = {f["name"] for f in found}
    assert "SUM" in names and "XLOOKUP" in names  # a library function and a core one
    assert len(found) > 60
    assert set(found[0]) == {"name", "signature", "tooltip"}  # the summary shape, not the full help text


def test_functions_searches_by_name_or_description(book):
    found = [f["name"] for f in call(book, "functions", {"query": "sum"})]
    assert found[0] == "SUM"
    assert "SUMIF" in found


def test_a_viewer_may_search_functions_too(book):
    assert call(book, "functions", account=VERA) == call(book, "functions", account=ANN)


def test_function_help_gives_the_full_text_by_name_case_insensitively(book):
    found = call(book, "function_help", {"name": "round"})
    assert found["name"] == "ROUND"
    assert found["signature"] == "ROUND(number, digits?)"
    assert "2.68" in found["help"]  # the worked example survives into the full help text


def test_function_help_refuses_an_unknown_name(book):
    with pytest.raises(RequestError) as caught:
        call(book, "function_help", {"name": "NOSUCHFUNCTION"})
    assert caught.value.code == "command_error"
