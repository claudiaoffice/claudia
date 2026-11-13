"""The methods a table view needs: sheets, a window of cells, typing into cells, rows and columns (computes)."""

import base64
import struct

import pytest

from claudia_computes import AddSheet, CellRegion, WorkbookModel
from claudia_computes.model import MAX_ROWS
from claudia_core import Document, MemoryStore
from claudia_server.auth import Account
from claudia_server.computes import computes_methods
from claudia_server.i18n import translate
from claudia_server.protocol import Context, Limits, RequestError, core_methods

ANN = Account("ann", "owner")
BEN = Account("ben", "editor")
VERA = Account("vera", "viewer")


@pytest.fixture
def book():
    return Document(WorkbookModel(), store=MemoryStore())


def call(doc, name, params=None, account=ANN, locale="en"):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0, locale=locale)
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


# ------------------------------------------------------------------ export to Excel (D212)
def test_export_office_returns_xlsx_bytes_that_round_trip(book):
    from claudia_computes_io import xlsx_to_workbook

    call(book, "add_sheet", {"name": "Costs"})
    typed(book, "s1", [(0, 0, "a"), (0, 1, "3")])
    answer = call(book, "export_office", {"format": "xlsx"})
    assert answer["format"] == "xlsx"
    assert answer["content_type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    raw = base64.b64decode(answer["data"])
    assert raw[:2] == b"PK"  # an xlsx is a zip
    reloaded = xlsx_to_workbook(raw)
    assert [s.name for s in reloaded.sheets.values()] == ["Costs"]


def test_export_office_returns_an_ods_that_round_trips_with_its_values_and_says_who_made_it_when(book):
    from claudia_computes_io import ods_to_workbook

    from claudia_odf_io import problems, read_info
    from claudia_opc_io import read_parts

    call(book, "add_sheet", {"name": "Costs"})
    typed(book, "s1", [(0, 0, "2"), (0, 1, "=A1*3"), (0, 2, "words")])
    answer = call(book, "export_office", {"format": "ods"})
    assert answer["format"] == "ods"
    assert answer["content_type"] == "application/vnd.oasis.opendocument.spreadsheet"
    raw = base64.b64decode(answer["data"])
    assert problems(raw) == []
    reloaded = ods_to_workbook(raw)
    sheet = reloaded.sheets["s1"]
    assert [s.name for s in reloaded.sheets.values()] == ["Costs"]
    assert sheet.cells[(0, 1)] == {"t": "formula", "v": "=A1*3"} and sheet.grid[(0, 1)] == 6
    info = read_info(read_parts(raw)["meta.xml"])
    assert info.creator == "ann" and info.modifier == "ann"
    assert info.created and info.modified
    assert answer["losses"] == []


def test_export_office_to_xlsx_lists_what_excel_cannot_hold(book):
    call(book, "add_sheet", {"name": "Costs"})
    assert call(book, "export_office", {"format": "xlsx"})["losses"] == []
    typed(book, "s1", [(0, 0, '=RANDOM("triangular",1,2,3)'), (1, 0, "{1, 2}")])
    losses = call(book, "export_office", {"format": "xlsx"})["losses"]
    assert {(x["kind"], x["detail"]): x["count"] for x in losses} == {("formula", "random"): 1, ("alternatives", ""): 1}


def test_export_office_rejects_an_unknown_format(book):
    with pytest.raises(RequestError):
        call(book, "export_office", {"format": "numbers"})


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


# -- what an object says to someone who cannot see it (BITV 1.1.1) -----------------------------------------------
def test_a_decorative_picture_is_imported_with_no_description(book):
    call(book, "add_sheet", {"name": "S"})
    add_image(book, alt="", decorative=True)
    (obj,) = objects(book)
    assert obj["decorative"] is True and obj["description"] == "" and obj["imported"]["alt"] == ""


def test_a_picture_needs_a_description_or_the_decorative_mark(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError, match="decorative") as caught:
        add_image(book, alt="")
    assert caught.value.code == "command_error"
    with pytest.raises(RequestError, match="decorative") as caught:
        add_image(book, alt="a flourish", decorative=True)
    assert caught.value.code == "command_error"


def test_a_picture_is_described_better_later_and_marked_decorative_later_still(book):
    call(book, "add_sheet", {"name": "S"})
    picture = add_image(book)
    call(book, "describe_object", {"id": picture, "description": "the quarterly sales chart as a picture"})
    assert objects(book)[0]["description"] == "the quarterly sales chart as a picture"
    assert book.history_for("ann").undo_label == "Describe object"
    call(book, "describe_object", {"id": picture, "description": "", "decorative": True})
    assert (objects(book)[0]["description"], objects(book)[0]["decorative"]) == ("", True)


def test_a_picture_cannot_be_left_with_neither_a_description_nor_the_decorative_mark(book):
    call(book, "add_sheet", {"name": "S"})
    picture = add_image(book)
    with pytest.raises(RequestError, match="decorative") as caught:
        call(book, "describe_object", {"id": picture, "description": ""})
    assert caught.value.code == "command_error"


def test_a_viewer_may_not_describe(book):
    call(book, "add_sheet", {"name": "S"})
    picture = add_image(book)
    with pytest.raises(RequestError) as caught:
        call(book, "describe_object", {"id": picture, "description": "x"}, account=VERA)
    assert caught.value.code == "forbidden"


# -- images and floating objects (E6.17): add_image, move_object, remove_object, and the never-resize guarantee
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


def test_function_help_is_in_the_language_of_the_connection(book):
    """E13.8, D323: descriptions and the words of the worked examples are German for a German window; the formula,
    its result and the signature are not words and stay as they are."""
    german = call(book, "function_help", {"name": "round"}, locale="de")
    english = call(book, "function_help", {"name": "round"})
    assert german["signature"] == english["signature"] and "2.68" in german["help"]
    assert german["tooltip"].startswith("ROUND(number, digits?): Rundet")
    assert "ergibt" in german["help"] and "gives" not in german["help"]
    assert "Rundet" not in english["help"] and "gives" in english["help"]


def test_functions_are_listed_and_searched_in_the_language_of_the_connection(book):
    summed = {f["name"]: f["tooltip"] for f in call(book, "functions", {"query": "Summe"}, locale="de")}
    assert (
        summed["SUM"]
        == "SUM(*values): Die Summe der Zahlen in den Bereichen. Text und leere Zellen werden übersprungen."
    )
    assert call(book, "functions", {"query": "Summe"}) == []  # English has no word "Summe"
    assert [f["name"] for f in call(book, "functions", {"query": "sum"}, locale="de")][:1] == ["SUM"]


def test_every_function_has_a_german_description():
    """Nothing in the catalog is left out of ``po/de.po``: a new function comes with its translation."""
    from claudia_computes import function_catalog

    for entry in function_catalog():
        if entry.description:
            assert entry.translated(lambda text: translate(text, "de")).description != entry.description, entry.name


def test_function_help_refuses_an_unknown_name(book):
    with pytest.raises(RequestError) as caught:
        call(book, "function_help", {"name": "NOSUCHFUNCTION"})
    assert caught.value.code == "command_error"


# -- charts (E6.6): a diagram definition, shown as a floating object, a tab, or both at once ---------------------
def cell_range(sheet="s1", first=(0, 0), last=(2, 2)):
    def ref(row, col):
        return {"row": row, "col": col, "sheet": sheet, "row_abs": False, "col_abs": False}

    return {"first": ref(*first), "last": ref(*last)}


def define_diagram(doc, **changes):
    given = {"kind": "bar", "range": cell_range(), "series_in": "columns", **changes}
    return call(doc, "define_diagram", {"definition": given})["diagram"]


def fill_table(doc, sheet="s1"):
    """A header row (East, West) and a header column (Jan, Feb) around a 2x2 block of numbers."""
    typed(
        doc,
        sheet,
        [
            (0, 1, "East"), (0, 2, "West"),
            (1, 0, "Jan"), (1, 1, "10"), (1, 2, "20"),
            (2, 0, "Feb"), (2, 1, "15"), (2, 2, "25"),
        ],
    )  # fmt: skip


def test_a_diagram_definition_is_taken_in_and_listed(book):
    call(book, "add_sheet", {"name": "S"})
    diagram_id = define_diagram(book, title="Sales")
    (listed,) = call(book, "diagrams")
    assert listed["id"] == diagram_id and listed["title"] == "Sales" and listed["kind"] == "bar"


def test_define_diagram_assigns_the_id_the_client_may_not(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError, match="assigned by the server") as caught:
        call(book, "define_diagram", {"definition": {"id": "g1", "kind": "bar", "range": cell_range()}})
    assert caught.value.code == "bad_request"


def test_a_malformed_diagram_definition_is_a_command_error(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError) as caught:
        call(book, "define_diagram", {"definition": {"kind": "pie", "range": cell_range()}})
    assert caught.value.code == "command_error"


def test_a_diagram_needs_a_sheet_and_range_this_document_has(book):
    with pytest.raises(RequestError, match="does not know the sheet"):
        define_diagram(book)
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError, match="inside the sheet"):
        define_diagram(book, range=cell_range(first=(0, 0), last=(MAX_ROWS, 1)))


def test_a_diagram_is_placed_as_a_floating_object_and_behaves_like_any_other_object(book):
    call(book, "add_sheet", {"name": "S"})
    diagram_id = define_diagram(book)
    added = call(
        book, "add_diagram_object", {"sheet": "s1", "row": 1, "col": 1, "w": 300, "h": 200, "diagram": diagram_id}
    )
    (obj,) = objects(book)
    assert obj["id"] == added["object"] and obj["kind"] == "diagram" and obj["diagram"] == diagram_id
    assert (obj["anchor"]["row"], obj["anchor"]["col"], obj["w"], obj["h"]) == (1, 1, 300, 200)
    call(book, "resize_object", {"id": obj["id"], "row": 1, "col": 1, "w": 500, "h": 150})  # no fixed aspect
    (obj,) = objects(book)
    assert (obj["w"], obj["h"]) == (500, 150)
    call(book, "remove_object", {"id": obj["id"]})
    assert objects(book) == []


def test_add_diagram_object_refuses_an_unknown_diagram_or_sheet(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError, match="does not know the diagram"):
        call(book, "add_diagram_object", {"sheet": "s1", "row": 0, "col": 0, "w": 100, "h": 100, "diagram": "nope"})
    diagram_id = define_diagram(book)
    with pytest.raises(RequestError, match="unknown sheet"):
        call(
            book,
            "add_diagram_object",
            {"sheet": "nope", "row": 0, "col": 0, "w": 100, "h": 100, "diagram": diagram_id},
        )


def test_a_chart_tab_and_a_floating_object_may_share_the_same_definition(book):
    call(book, "add_sheet", {"name": "S"})
    diagram_id = define_diagram(book)
    call(book, "add_diagram_object", {"sheet": "s1", "row": 0, "col": 0, "w": 300, "h": 200, "diagram": diagram_id})
    chart_id = call(book, "add_chart", {"name": "Sales chart", "spec_id": diagram_id})["chart"]
    (tab,) = call(book, "charts")
    assert tab["id"] == chart_id and tab["name"] == "Sales chart" and tab["spec_id"] == diagram_id
    with pytest.raises(RequestError, match="in use") as caught:
        call(book, "forget_diagram", {"id": diagram_id})  # refused: the object and the tab both still show it
    assert caught.value.code == "command_error"


def test_add_chart_rejects_a_blank_or_unknown_definition(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError, match="does not know the diagram"):
        call(book, "add_chart", {"name": "X", "spec_id": "nope"})
    diagram_id = define_diagram(book)
    with pytest.raises(RequestError, match="1 to"):
        call(book, "add_chart", {"name": "   ", "spec_id": diagram_id})


def test_removing_a_chart_tab_leaves_its_definition_for_whatever_else_shows_it(book):
    call(book, "add_sheet", {"name": "S"})
    diagram_id = define_diagram(book)
    chart_id = call(book, "add_chart", {"name": "Sales", "spec_id": diagram_id})["chart"]
    call(book, "remove_chart", {"id": chart_id})
    assert call(book, "charts") == []
    assert [d["id"] for d in call(book, "diagrams")] == [diagram_id]
    call(book, "forget_diagram", {"id": diagram_id})  # nothing shows it any more
    assert call(book, "diagrams") == []


def test_update_diagram_redefines_it_in_place_for_every_viewer(book):
    call(book, "add_sheet", {"name": "S"})
    diagram_id = define_diagram(book, title="First")
    call(book, "add_chart", {"name": "Sales", "spec_id": diagram_id})
    call(
        book,
        "update_diagram",
        {"id": diagram_id, "definition": {"kind": "bar", "range": cell_range(), "title": "Second"}},
    )
    (listed,) = call(book, "diagrams")
    assert listed["title"] == "Second"


def test_update_diagram_refuses_an_unknown_id(book):
    call(book, "add_sheet", {"name": "S"})
    with pytest.raises(RequestError, match="does not know the diagram"):
        call(book, "update_diagram", {"id": "nope", "definition": {"kind": "bar", "range": cell_range()}})


def test_chart_figure_reads_the_headers_and_the_data_with_series_in_columns(book):
    call(book, "add_sheet", {"name": "S"})
    fill_table(book)
    diagram_id = define_diagram(book, title="Sales", x_title="Month", y_title="Units")
    figure = call(book, "chart_figure", {"diagram": diagram_id})["figure"]
    assert [trace["name"] for trace in figure["data"]] == ["East", "West"]
    assert figure["data"][0]["x"] == ["Jan", "Feb"]
    assert figure["data"][0]["y"] == [10.0, 15.0]
    assert figure["data"][1]["y"] == [20.0, 25.0]
    assert figure["layout"]["title"]["text"] == "Sales"
    assert figure["layout"]["xaxis"]["title"]["text"] == "Month"
    assert figure["layout"]["yaxis"]["title"]["text"] == "Units"


def test_chart_figure_reads_series_in_rows_as_the_transpose(book):
    call(book, "add_sheet", {"name": "S"})
    fill_table(book)
    diagram_id = define_diagram(book, series_in="rows")
    figure = call(book, "chart_figure", {"diagram": diagram_id})["figure"]
    assert [trace["name"] for trace in figure["data"]] == ["Jan", "Feb"]
    assert figure["data"][0]["x"] == ["East", "West"]
    assert figure["data"][0]["y"] == [10.0, 20.0]


def test_chart_figure_updates_live_as_cells_change(book):
    call(book, "add_sheet", {"name": "S"})
    fill_table(book)
    diagram_id = define_diagram(book)
    before = call(book, "chart_figure", {"diagram": diagram_id})["figure"]
    assert before["data"][0]["y"] == [10.0, 15.0]  # East column: Jan, Feb
    typed(book, "s1", [(1, 1, "99")])  # Jan's East value
    after = call(book, "chart_figure", {"diagram": diagram_id})["figure"]
    assert after["data"][0]["y"] == [99.0, 15.0]


def test_chart_figure_on_a_single_cell_range_makes_up_a_category_and_a_series_name(book):
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(0, 0, "5")])  # one row and one column: no room for either header
    diagram_id = define_diagram(book, range=cell_range(first=(0, 0), last=(0, 0)))
    figure = call(book, "chart_figure", {"diagram": diagram_id})["figure"]
    assert [trace["name"] for trace in figure["data"]] == ["Series 1"]
    assert figure["data"][0]["x"] == ["1"]
    assert figure["data"][0]["y"] == [5.0]


def test_chart_figure_on_a_single_row_reads_its_first_column_as_category_labels(book):
    # More than one column still means a header column under the convention, even with only one row of
    # data left over (``chart_figure``'s docstring): col 0 here is "5", read as the one category's name,
    # and only col 1 becomes a series ("Series 1" has no header row to draw a name from).
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(0, 0, "5"), (0, 1, "6")])
    diagram_id = define_diagram(book, range=cell_range(first=(0, 0), last=(0, 1)))
    figure = call(book, "chart_figure", {"diagram": diagram_id})["figure"]
    assert [trace["name"] for trace in figure["data"]] == ["Series 1"]
    assert figure["data"][0]["x"] == ["5"]
    assert figure["data"][0]["y"] == [6.0]


def test_chart_figure_with_header_row_false_reads_every_row_as_data(book):
    """The header-row bug reported after the first round shipped: a 2-column, 3-row range of plain
    category/value pairs with no header line of its own used to silently lose its first row — read as a bogus
    header whose "series name" was really the first row's own value — leaving only the second and third rows on
    the chart. ``header_row=False`` is the fix: every row becomes a category, and the one data column becomes
    one series with a generated name (there is still no header row to draw a name from)."""
    call(book, "add_sheet", {"name": "S"})
    typed(
        book,
        "s1",
        [(0, 0, "Jan"), (0, 1, "10"), (1, 0, "Feb"), (1, 1, "15"), (2, 0, "Mar"), (2, 1, "20")],
    )
    diagram_id = define_diagram(book, range=cell_range(first=(0, 0), last=(2, 1)), header_row=False)
    figure = call(book, "chart_figure", {"diagram": diagram_id})["figure"]
    assert [trace["name"] for trace in figure["data"]] == ["Series 1"]
    assert figure["data"][0]["x"] == ["Jan", "Feb", "Mar"]
    assert figure["data"][0]["y"] == [10.0, 15.0, 20.0]


def test_chart_figure_header_row_has_no_room_to_turn_off_on_a_single_row_range(book):
    """``header_row=False`` only matters where there is a second row to read as data; a single-row range has no
    room for a header on that axis regardless of the setting, same as before this field existed."""
    call(book, "add_sheet", {"name": "S"})
    typed(book, "s1", [(0, 0, "5"), (0, 1, "6")])
    diagram_id = define_diagram(book, range=cell_range(first=(0, 0), last=(0, 1)), header_row=False)
    figure = call(book, "chart_figure", {"diagram": diagram_id})["figure"]
    assert figure["data"][0]["x"] == ["5"]
    assert figure["data"][0]["y"] == [6.0]


def test_chart_figure_refuses_an_unknown_diagram(book):
    with pytest.raises(RequestError, match="does not know the diagram"):
        call(book, "chart_figure", {"diagram": "nope"})


def test_a_single_series_chart_shows_no_legend_but_two_series_do(book):
    call(book, "add_sheet", {"name": "S"})
    fill_table(book)
    single = define_diagram(book, range=cell_range(first=(0, 0), last=(2, 1)))  # Jan/Feb header + East only
    figure = call(book, "chart_figure", {"diagram": single})["figure"]
    assert len(figure["data"]) == 1 and figure["data"][0]["y"] == [10.0, 15.0]
    assert figure["layout"]["showlegend"] is False

    both = define_diagram(book)  # default range: East and West
    figure = call(book, "chart_figure", {"diagram": both})["figure"]
    assert len(figure["data"]) == 2
    assert figure["layout"]["showlegend"] is True


def test_viewers_may_read_diagrams_and_figures_but_not_change_them(book):
    call(book, "add_sheet", {"name": "S"})
    diagram_id = define_diagram(book)
    assert call(book, "diagrams", account=VERA)
    assert call(book, "chart_figure", {"diagram": diagram_id}, account=VERA)
    with pytest.raises(RequestError) as caught:
        call(book, "define_diagram", {"definition": {"kind": "bar", "range": cell_range()}}, account=VERA)
    assert caught.value.code == "forbidden"


def test_moving_and_removing_a_diagram_object_undo_round_trips_like_any_object(book):
    call(book, "add_sheet", {"name": "S"})
    diagram_id = define_diagram(book)
    added = call(
        book, "add_diagram_object", {"sheet": "s1", "row": 0, "col": 0, "w": 300, "h": 200, "diagram": diagram_id}
    )
    call(book, "move_object", {"id": added["object"], "row": 4, "col": 4})
    book.undo("ann")
    (obj,) = objects(book)
    assert (obj["anchor"]["row"], obj["anchor"]["col"]) == (0, 0)
    call(book, "remove_object", {"id": obj["id"]})
    book.undo("ann")
    assert [o["id"] for o in objects(book)] == [added["object"]]


# ------------------------------------------------------------------------------------------ search and replace (E6.20)
def budget_sheet(doc):
    doc.execute(AddSheet("s1", "Sheet1"), author="ann")
    typed(
        doc,
        "s1",
        [
            (0, 0, "Travel"),
            (0, 1, "€12,50"),
            (1, 1, "€80"),
            (2, 1, "$9.90 EUR"),
            (3, 1, '=VALUE(SUBSTITUTE(B1,"€",""))+1'),
            (4, 1, "42"),
        ],
    )


def search(doc, query, account=ANN, **more):
    return call(doc, "search_find", {"query": query, **more}, account=account)


def text(value, **more):
    return {"mode": "text", "text": value, **more}


def test_a_quick_search_lists_matches_with_where_and_what_kind(book):
    budget_sheet(book)
    found = search(book, text("€"), kinds=["text", "formulas"])
    assert [(m["row"], m["col"], m["kind"], m["start"], m["end"]) for m in found["matches"]] == [
        (0, 1, "text", 0, 1),
        (1, 1, "text", 0, 1),
        (3, 1, "formula", 22, 23),
    ]
    assert found["counts"] == {"text": 2, "formulas": 1, "values": 0}
    assert found["total"] == 3 and not found["truncated"] and not found["timed_out"]
    assert found["revision"] == book.revision.to_data()


def test_a_match_says_what_it_is_in_and_how_it_reads_there(book):
    budget_sheet(book)
    match = search(book, text("12,5"))["matches"][0]
    assert match["sheet"] == "s1" and match["text"] == "€12,50" and match["excerpt"] == [1, 5]
    assert match["clipped"] == [False, False]
    assert match["number"] == 0 and match["parts"] == [] and match["after"] is None


def test_search_looks_in_text_unless_told_otherwise(book):
    budget_sheet(book)
    assert [(m["row"]) for m in search(book, text("42"))["matches"]] == []
    assert [(m["row"]) for m in search(book, text("42"), kinds=["values"])["matches"]] == [4]


def test_a_long_cell_is_cut_around_the_match_and_says_so(book):
    budget_sheet(book)
    typed(book, "s1", [(8, 0, "a" * 200 + "NEEDLE" + "b" * 200)])
    match = search(book, text("needle"))["matches"][0]
    assert match["start"] == 200 and match["clipped"] == [True, True]
    assert match["text"][match["excerpt"][0] : match["excerpt"][1]] == "NEEDLE"


def test_the_scope_is_a_sheet_or_a_selection(book):
    budget_sheet(book)
    call(book, "add_sheet", {"name": "Other"})
    typed(book, "s2", [(0, 0, "€ elsewhere")])
    assert len(search(book, text("€"))["matches"]) == 3  # all sheets
    assert len(search(book, text("€"), scope={"sheet": "s2"})["matches"]) == 1
    selected = search(book, text("€"), scope={"sheet": "s1", "range": [1, 0, 2, 1]})
    assert [(m["row"], m["col"]) for m in selected["matches"]] == [(1, 1)]


def test_a_selection_needs_its_sheet_and_four_numbers(book):
    budget_sheet(book)
    for scope in ({"range": [0, 0, 1, 1]}, {"sheet": "s1", "range": [0, 0, 1]}, {"sheet": "s1", "range": [1, 0, 0, 0]}):
        with pytest.raises(RequestError) as caught:
            search(book, text("x"), scope=scope)
        assert caught.value.code == "bad_request"
    with pytest.raises(RequestError) as caught:
        search(book, text("x"), scope={"sheet": "nope"})
    assert caught.value.code == "command_error"


def test_a_search_in_the_builders_words(book):
    budget_sheet(book)
    query = {
        "mode": "builder",
        "parts": [{"what": "any_of", "chars": "€$£"}, {"what": "number", "keep": "amount"}],
        "conditions": [{"kind": "not_contains", "text": "EUR"}],
        "replace": [{"keep": "amount"}, {"text": " EUR"}],
    }
    found = search(book, query)
    assert [(m["row"], m["parts"], m["after"]) for m in found["matches"]] == [
        (0, ["12,50"], "12,50 EUR"),
        (1, ["80"], "80 EUR"),
    ]
    assert [(o["row"], o["why"]) for o in found["left_out"]] == [(2, {"kind": "not_contains", "text": "EUR"})]
    assert found["pattern"] == {"find": r"[€$£](\d+(?:[.,]\d+)*)", "filter": "^(?!.*EUR)", "replace": r"\g<1> EUR"}


def test_a_typed_pattern_is_searched_as_it_is_and_a_cell_reference_is_a_part(book):
    budget_sheet(book)
    found = search(book, {"mode": "pattern", "find": r"\d+,\d+"})
    assert [m["row"] for m in found["matches"]] == [0]
    refs = search(book, {"mode": "builder", "parts": [{"what": "cellref"}]}, kinds=["formulas"])
    assert [(m["row"], m["text"][m["excerpt"][0] : m["excerpt"][1]]) for m in refs["matches"]] == [(3, "B1")]


def test_a_mistake_in_the_pattern_comes_back_as_a_result_not_an_error(book):
    budget_sheet(book)
    found = search(book, {"mode": "pattern", "find": "a(bc"})
    assert found["error"] == {"message": "missing ), unterminated subpattern", "field": "find", "position": 1}
    assert found["matches"] == [] and found["counts"] == {"text": 0, "formulas": 0, "values": 0}


def test_a_pattern_that_could_run_forever_is_refused_in_the_same_way(book):
    budget_sheet(book)
    found = search(book, {"mode": "pattern", "find": "(a+)+$"})
    assert found["error"]["field"] == "find" and "repeat" in found["error"]["message"]


def test_a_query_that_is_not_a_query_is_a_bad_request(book):
    budget_sheet(book)
    for bad in ({}, {"mode": "regex"}, {"mode": "text"}, {"mode": "text", "text": 5}):
        found = search(book, bad)
        assert found["error"]["message"] and found["matches"] == []


def test_unknown_kinds_are_a_bad_request(book):
    budget_sheet(book)
    with pytest.raises(RequestError) as caught:
        search(book, text("x"), kinds=["words"])
    assert caught.value.code == "bad_request"


def test_a_search_that_runs_out_of_time_says_so(book, monkeypatch):
    budget_sheet(book)
    monkeypatch.setattr("claudia_server.computes.SEARCH_SECONDS", 0.0)
    found = search(book, text("€"))
    assert found["timed_out"] and found["matches"] == []


def test_a_viewer_may_search(book):
    budget_sheet(book)
    assert len(search(book, text("€"), account=VERA)["matches"]) == 2


def test_the_preview_says_what_would_change_and_changes_nothing(book):
    budget_sheet(book)
    before = book.revision
    shown = call(book, "search_preview", {"query": text("€", replace=[{"text": "EUR "}])}, account=VERA)
    assert [(c["row"], c["before"], c["after"]) for c in shown["changes"]] == [
        (0, "€12,50", "EUR 12,50"),
        (1, "€80", "EUR 80"),
    ]
    assert shown["skipped"] == [] and shown["total"] == 2
    assert book.revision == before


def test_replace_changes_the_cells_in_one_step_and_says_how_many(book):
    budget_sheet(book)
    done = call(book, "search_replace", {"query": text("€", replace=[{"text": "EUR "}])})
    assert done["replaced"] == 2 and done["skipped"] == []
    assert [book.model.get("s1", r, 1)["v"] for r in (0, 1)] == ["EUR 12,50", "EUR 80"]
    assert book.log.get(book.revision).command.label == "Replace in 2 cells"
    book.undo("ann")
    assert [book.model.get("s1", r, 1)["v"] for r in (0, 1)] == ["€12,50", "€80"]


def test_replace_leaves_formulas_alone_unless_they_are_asked_for(book):
    budget_sheet(book)
    call(book, "search_replace", {"query": text("€", replace=[{"text": ""}])})
    assert "€" in book.model.get("s1", 3, 1)["v"]
    call(book, "search_replace", {"query": text("€", replace=[{"text": "$"}]), "kinds": ["formulas"]})
    assert book.model.get("s1", 3, 1)["v"] == '=VALUE(SUBSTITUTE(B1,"$",""))+1'


def test_replace_can_leave_a_match_or_a_cell_alone(book):
    budget_sheet(book)
    typed(book, "s1", [(6, 0, "a-b-c")])
    call(
        book,
        "search_replace",
        {
            "query": text("-", replace=[{"text": "+"}]),
            "leave": [{"sheet": "s1", "row": 6, "col": 0, "match": 0}],
        },
    )
    assert book.model.get("s1", 6, 0)["v"] == "a-b+c"
    call(
        book,
        "search_replace",
        {"query": text("€", replace=[{"text": ""}]), "leave": [{"sheet": "s1", "row": 0, "col": 1, "match": None}]},
    )
    assert book.model.get("s1", 0, 1)["v"] == "€12,50" and book.model.get("s1", 1, 1)["v"] == "80"


def test_a_cell_somebody_else_holds_is_skipped_and_named(book):
    budget_sheet(book)
    book.lock("ben", [CellRegion.of("s1", 1, 1, 1, 1)], 30)
    shown = call(book, "search_preview", {"query": text("€", replace=[{"text": ""}])})
    assert [(s["row"], s["reason"], s["by"]) for s in shown["skipped"]] == [(1, "locked", "ben")]
    done = call(book, "search_replace", {"query": text("€", replace=[{"text": ""}])})
    assert done["replaced"] == 1 and done["skipped"] == shown["skipped"]
    assert book.model.get("s1", 0, 1)["v"] == "12,50" and book.model.get("s1", 1, 1)["v"] == "€80"


def test_my_own_hold_does_not_stop_me(book):
    budget_sheet(book)
    book.lock("ann", [CellRegion.of("s1", 0, 0, 5, 5)], 30)
    assert call(book, "search_replace", {"query": text("€", replace=[{"text": ""}])})["replaced"] == 2


def test_a_viewer_cannot_replace(book):
    budget_sheet(book)
    with pytest.raises(RequestError) as caught:
        call(book, "search_replace", {"query": text("€", replace=[{"text": ""}])}, account=VERA)
    assert caught.value.code == "forbidden"


def test_replace_needs_something_to_replace_with(book):
    budget_sheet(book)
    with pytest.raises(RequestError) as caught:
        call(book, "search_replace", {"query": text("€")})
    assert caught.value.code == "command_error" and "replace" in caught.value.message


def test_replace_that_changes_nothing_makes_no_history(book):
    budget_sheet(book)
    before = book.revision
    done = call(book, "search_replace", {"query": text("zzz", replace=[{"text": "y"}])})
    assert done["replaced"] == 0 and done["revision"] == before.to_data()
    assert book.revision == before


def test_replace_refuses_more_cells_than_one_step_may_change(book, monkeypatch):
    budget_sheet(book)
    monkeypatch.setattr("claudia_server.computes.MAX_REPLACED_CELLS", 1)
    with pytest.raises(RequestError) as caught:
        call(book, "search_replace", {"query": text("€", replace=[{"text": ""}])})
    assert caught.value.code == "bad_request" and "narrow" in caught.value.message
    assert book.model.get("s1", 0, 1)["v"] == "€12,50"


def test_replace_takes_the_base_revision_like_every_write(book):
    budget_sheet(book)
    done = call(book, "search_replace", {"query": text("€", replace=[{"text": ""}]), "base": book.revision.to_data()})
    assert done["replaced"] == 2


def test_the_assistant_may_replace_too():
    from claudia_server.apps import MODEL_METHODS

    assert "search_replace" in MODEL_METHODS["computes"]


# ------------------------------------------------------------------ random numbers, alternatives, follow (E6.21-E6.23)
@pytest.fixture
def pricing(book):
    call(book, "add_sheet", {"name": "Pricing"})
    typed(
        book,
        "s1",
        [
            (1, 1, "24"),
            (2, 1, "{800, 1000, 1300}"),
            (3, 1, "{9.5, 11, 14}"),
            (4, 1, "8500"),
            (6, 1, "=B2*B3"),
            (7, 1, "=B5+B3*B4"),
            (8, 1, "=B7-B8"),
            (0, 3, '=RANDOM("normal",1000,150)'),
        ],
    )
    return book


def test_cells_carry_alternatives_and_outcomes_for_a_client(pricing):
    cells = {
        (r, c): v
        for r, c, v in call(pricing, "cells", {"sheet": "s1", "row0": 0, "row1": 10, "col0": 0, "col1": 5})["cells"]
    }
    assert cells[(2, 1)]["f"] == "{800, 1000, 1300}"
    assert [a["v"] for a in cells[(2, 1)]["alts"]] == [800, 1000, 1300]
    assert cells[(8, 1)]["out"]["n"] == 9 and cells[(8, 1)]["out"]["median"] == 4500


def test_the_random_state_is_asked_for_and_resampled(pricing):
    assert call(pricing, "random_state") == {"revision": "main:2", "seed": 0, "draw": 0}
    before = call(pricing, "cells", {"sheet": "s1", "row0": 0, "row1": 0, "col0": 3, "col1": 3})["cells"][0][2]["v"]
    answer = call(pricing, "resample")
    assert answer["draw"] == 1 and answer["revision"] == "main:3"
    after = call(pricing, "cells", {"sheet": "s1", "row0": 0, "row1": 0, "col0": 3, "col1": 3})["cells"][0][2]["v"]
    assert after != before
    assert call(pricing, "resample", {"steps": 4})["draw"] == 5


def test_a_seed_makes_the_numbers_reproducible(pricing):
    call(pricing, "set_random_seed", {"seed": 42})
    first = call(pricing, "cells", {"sheet": "s1", "row0": 0, "row1": 0, "col0": 3, "col1": 3})["cells"][0][2]["v"]
    call(pricing, "set_random_seed", {"seed": 7})
    call(pricing, "set_random_seed", {"seed": 42})
    assert (
        call(pricing, "cells", {"sheet": "s1", "row0": 0, "row1": 0, "col0": 3, "col1": 3})["cells"][0][2]["v"] == first
    )
    assert call(pricing, "random_state")["seed"] == 42


def test_resampling_and_seeds_are_checked_and_are_for_editors(pricing):
    for params in ({"steps": 0}, {"steps": 1001}, {"steps": "many"}):
        with pytest.raises(RequestError):
            call(pricing, "resample", params)
    for params in ({"seed": -1}, {"seed": 2**60}, {"seed": 1.5}):
        with pytest.raises(RequestError):
            call(pricing, "set_random_seed", params)
    with pytest.raises(RequestError):
        call(pricing, "resample", account=VERA)
    assert call(pricing, "random_state", account=VERA)["draw"] == 0


def test_the_outcomes_of_a_cell_come_as_a_table(pricing):
    answer = call(pricing, "outcome_table", {"sheet": "s1", "row": 8, "col": 1})
    table = answer["table"]
    assert [i["row"] for i in table["inputs"]] == [2, 3] and table["inputs"][0]["count"] == 3
    assert [r["value"]["v"] for r in table["rows"]] == [3100, 1900, -500, 6000, 4500, 1500, 10350, 8400, 4500]
    assert table["rows"][1]["choice"] == [0, 1] and table["sampled"] is False
    assert {s["input"] for s in table["sensitivity"]} == {0, 1}


def test_outcome_tables_can_pair_inputs_and_say_when_they_cannot(pricing):
    paired = call(pricing, "outcome_table", {"sheet": "s1", "row": 8, "col": 1, "combine": "pair"})["table"]
    assert [r["choice"] for r in paired["rows"]] == [[0, 0], [1, 1], [2, 2]]
    typed(pricing, "s1", [(3, 1, "{9.5, 11}")])
    with pytest.raises(RequestError) as why:
        call(pricing, "outcome_table", {"sheet": "s1", "row": 8, "col": 1, "combine": "pair"})
    assert why.value.code == "command_error"
    with pytest.raises(RequestError):
        call(pricing, "outcome_table", {"sheet": "s1", "row": 8, "col": 1, "combine": "sideways"})


def test_a_cell_without_outcomes_has_no_table(pricing):
    assert call(pricing, "outcome_table", {"sheet": "s1", "row": 4, "col": 1})["table"] is None


def test_following_a_computation_lights_the_connected_cells_of_a_window(pricing):
    answer = call(pricing, "trace", {"sheet": "s1", "row": 8, "col": 1, "window": [0, 0, 20, 5]})
    trace = answer["trace"]
    roles = {(r, c): role for r, c, role in trace["cells"]}
    assert roles[(1, 1)] == "input" and roles[(6, 1)] == "calc" and roles[(8, 1)] == "output"
    assert (0, 3) not in roles and trace["connected"] is True and trace["reach"] == "group"


def test_following_can_be_cut_to_a_chain_and_to_a_window(pricing):
    chain = call(pricing, "trace", {"sheet": "s1", "row": 6, "col": 1, "reach": "chain"})["trace"]
    assert {(r, c) for r, c, _ in chain["cells"]} == {(1, 1), (2, 1), (6, 1), (8, 1)}
    cut = call(pricing, "trace", {"sheet": "s1", "row": 8, "col": 1, "window": [0, 0, 3, 5]})["trace"]
    assert {r for r, _, _ in cut["cells"]} <= {0, 1, 2, 3}


def test_following_checks_what_it_is_given(pricing):
    for params in (
        {"sheet": "s1", "row": 8, "col": 1, "reach": "all"},
        {"sheet": "s1", "row": 8, "col": 1, "window": [0, 0]},
        {"sheet": "s1", "row": 8, "col": 1, "window": [5, 0, 1, 5]},
        {"sheet": "s1", "row": 8, "col": 1, "window": [0, 0, 100000, 100]},
        {"sheet": "nope", "row": 0, "col": 0},
    ):
        with pytest.raises(RequestError):
            call(pricing, "trace", params)


# ------------------------------------------------------------------ the Random generator's preview (E6.22)
def test_a_distribution_can_be_previewed_before_it_is_typed(book):
    answer = call(book, "random_preview", {"distribution": "normal", "params": [1000, 150]})
    assert answer["formula"] == '=RANDOM("normal",1000,150)'
    assert answer["excel"] == "=NORMINV(RAND(),1000,150)"
    draws = answer["draws"]
    assert len(draws) == 200 and draws == sorted(draws)
    assert 990 < draws[100] < 1010 and answer["continuous"] is True


def test_a_preview_with_limits_stays_between_them(book):
    answer = call(book, "random_preview", {"distribution": "normal", "params": [1000, 150], "low": 900, "high": None})
    assert answer["formula"] == '=RANDOM("normal",1000,150,900,)'
    assert min(answer["draws"]) >= 900


def test_a_preview_says_when_excel_has_no_formula_for_it(book):
    answer = call(book, "random_preview", {"distribution": "triangular", "params": [9, 11, 14], "draws": 10})
    assert answer["excel"] is None and len(answer["draws"]) == 10


def test_a_discrete_preview_takes_values_and_weights(book):
    answer = call(book, "random_preview", {"distribution": "discrete", "params": [1, 3, 2, 1]})
    assert answer["formula"] == '=RANDOM("discrete",1,3,2,1)' and answer["continuous"] is False
    assert set(answer["draws"]) == {1, 2}


def test_a_preview_checks_what_it_is_given(book):
    for params in (
        {"distribution": "nope", "params": [1]},
        {"distribution": "normal", "params": [1]},
        {"distribution": "normal", "params": [1, -2]},
        {"distribution": "normal", "params": ["x", 2]},
        {"distribution": "poisson", "params": [3], "low": 1},
        {"distribution": "normal", "params": [1, 2], "draws": 0},
        {"distribution": "normal", "params": [1, 2], "draws": 5000},
    ):
        with pytest.raises(RequestError):
            call(book, "random_preview", params)
