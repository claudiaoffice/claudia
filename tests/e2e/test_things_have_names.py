"""Everything a person can add to a document has a name, end to end (D550, D552): one real server of every app, each
kind of thing added over the wire as the web client adds it, and read back the way the client reads it.

The kernel and the server test each kind on its own. This test is the list: when a new kind of thing becomes addable,
it belongs here, and a kind that comes without a name (or with one that clashes with another thing's) fails here. It
also checks the one namespace across kinds and the tag's way back to a thing that is gone (`thing_last_seen`).

A text's paragraphs (headings, list items, paragraphs) are things too (D554), named when somebody first points at one
(`name_thing`). Not in the list: the styles of every app, which have names of their own outside the namespace.
"""

from __future__ import annotations

import base64
import struct
import zlib
from collections.abc import Iterator

import pytest
from live import Live, Session, server


def tiny_png() -> str:
    """A 2×1 PNG, base64: the smallest picture every app accepts."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = zlib.compress(b"\x00\xff\x00\x00\x00\x00\xff")
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", raw)
    return base64.b64encode(png + chunk(b"IEND", b"")).decode()


@pytest.fixture(scope="module")
def live(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Live]:
    with server(tmp_path_factory.mktemp("names")) as running:
        yield running


def renderable(session: Session) -> str | None:
    """A container type this server can make (the tools are the administrator's, D392), or ``None``."""
    found = [each["type"] for each in session.ok("container_types")["types"]]
    return found[0] if found else None


def cells(sheet: str, rows: int) -> dict:
    """The first ``rows`` cells of column A of ``sheet``, as a range on the wire."""

    def ref(row: int) -> dict:
        return {"row": row, "col": 0, "sheet": sheet, "row_abs": False, "col_abs": False}

    return {"first": ref(0), "last": ref(rows - 1)}


def rate(sheet: str) -> dict:
    """A one-cell name, as the Names dialog defines it."""
    area = {"sheet": sheet, "row0": 0, "col0": 0, "row1": 0, "col1": 0}
    return {"name": "Rate", "range": area, "header": False, "grows": False, "purpose": "input"}


def assert_named(names: dict[str, str]) -> None:
    """Every thing has a name, and no two things share one (compared as the namespace compares them)."""
    assert all(name.strip() for name in names.values()), f"a thing without a name: {names}"
    folded = [" ".join(name.split()).casefold() for name in names.values()]
    assert len(set(folded)) == len(folded), f"two things share a name: {names}"


# ------------------------------------------------------------------------------------------------------- creates
def creates_things(session: Session) -> dict[str, str]:
    things = {}
    for slide in session.ok("slides"):
        things[slide["id"]] = slide["name"]
        for obj in session.ok("slide", slide=slide["id"])["objects"]:
            things[obj["id"]] = obj["name"]
    return things


def test_everything_added_to_a_presentation_has_a_name(live: Live) -> None:
    with live.socket("creates", "deck") as session:
        session.hello(create=True)
        first = session.ok("slides")[0]["id"]
        second = session.ok("add_slide")["slide"]
        added = [
            session.ok("add_object", slide=first, kind="text", x=10, y=10, w=300, h=80, text="Hello")["object"],
            session.ok("add_object", slide=first, kind="shape", shape="rectangle", x=10, y=200, w=200, h=100)["object"],
            session.ok(
                "add_image", slide=second, x=0, y=0, w=40, h=20, data=tiny_png(), alt="a dot", source_name="dot.png"
            )["object"],
        ]
        kind = renderable(session)
        if kind is not None:
            made = session.ok("add_container", slide=second, x=0, y=300, w=200, h=100, type=kind, source="x")
            added.append(made["object"])

        things = creates_things(session)
        assert {first, second, *added} <= set(things)
        assert_named(things)


def test_a_slide_and_an_object_cannot_share_a_name(live: Live) -> None:
    with live.socket("creates", "clash") as session:
        session.hello(create=True)
        slide = session.ok("slides")[0]["id"]
        box = session.ok("add_object", slide=slide, kind="text", x=0, y=0, w=100, h=50)["object"]
        session.ok("rename_thing", id=slide, name="Intro")
        refused = session.call("rename_thing", id=box, name="  intro ")
        assert not refused["ok"] and refused["error"]["code"] == "command_error"
        assert creates_things(session)[box] != "intro"


def test_a_tag_finds_a_thing_that_is_gone(live: Live) -> None:
    with live.socket("creates", "gone") as session:
        session.hello(create=True)
        slide = session.ok("slides")[0]["id"]
        box = session.ok("add_object", slide=slide, kind="text", x=0, y=0, w=100, h=50)["object"]
        session.ok("rename_thing", id=box, name="Figure 1")
        session.ok("remove_object", id=box)
        seen = session.ok("thing_last_seen", id=box)
        assert seen is not None and seen.get("revision") is not None, seen


# ------------------------------------------------------------------------------------------------------ computes
def computes_things(session: Session) -> dict[str, str]:
    things = {}
    for sheet in session.ok("sheets"):
        things[sheet["id"]] = sheet["name"]
        for obj in session.ok("objects", sheet=sheet["id"])["objects"]:
            things[obj["id"]] = obj["name"]
    for chart in session.ok("charts"):
        things[chart["id"]] = chart["name"]
    for named in session.ok("names")["names"]:
        things[named["id"]] = named["name"]
    return things


def test_everything_added_to_a_workbook_has_a_name(live: Live) -> None:
    with live.socket("computes", "book") as session:
        session.hello(create=True)
        sheet = session.ok("sheets")[0]["id"]
        session.ok("set_cells", sheet=sheet, cells=[{"row": r, "col": 0, "input": str(r + 1)} for r in range(3)])
        costs = session.ok("add_sheet", name="Costs")["sheet"]
        diagram = session.ok(
            "define_diagram", definition={"kind": "bar", "range": cells(sheet, 3), "series_in": "columns"}
        )["diagram"]
        added = [
            session.ok("add_diagram_object", sheet=sheet, row=4, col=2, w=200, h=120, diagram=diagram)["object"],
            session.ok(
                "add_image", sheet=sheet, row=0, col=4, w=40, h=20, data=tiny_png(), alt="a dot", source_name="dot.png"
            )["object"],
        ]
        session.ok("add_chart", name="Sales chart", spec_id=diagram)
        session.ok("define_name", definition=rate(sheet))
        kind = renderable(session)
        if kind is not None:
            added.append(
                session.ok("add_container", sheet=sheet, row=8, col=0, w=200, h=100, type=kind, source="x")["object"]
            )

        things = computes_things(session)
        assert set(added) <= set(things)
        assert {"Sales chart", "Rate"} <= set(things.values())
        assert things[costs] == "Costs"
        assert_named(things)


def test_an_object_cannot_be_named_like_a_range_or_a_sheet(live: Live) -> None:
    with live.socket("computes", "ranges") as session:
        session.hello(create=True)
        sheet = session.ok("sheets")[0]["id"]
        session.ok("define_name", definition=rate(sheet))
        picture = session.ok(
            "add_image", sheet=sheet, row=0, col=4, w=40, h=20, data=tiny_png(), alt="a dot", source_name="dot.png"
        )["object"]
        for taken in ("rate", "Sheet1"):
            refused = session.call("rename_thing", id=picture, name=taken)
            assert not refused["ok"] and refused["error"]["code"] == "command_error", (taken, refused)


# ------------------------------------------------------------------------------------------------------ composes
def test_a_container_in_a_text_has_a_name(live: Live) -> None:
    with live.socket("composes", "letter") as session:
        session.hello(create=True)
        kind = renderable(session)
        if kind is None:
            pytest.skip("this server has no tool to render a container with (D392); the text has nothing else to add")
        paragraph = session.ok("snapshot")["state"]["paragraphs"][0]["id"]
        made = session.ok("add_container", paragraph=paragraph, offset=0, w=200, h=100, type=kind, source="x")["object"]
        objects = {obj["id"]: obj["name"] for obj in session.ok("objects")["objects"]}
        assert made in objects
        assert_named(objects)


def test_a_paragraph_pointed_at_gets_a_name_in_the_one_namespace(live: Live) -> None:
    with live.socket("composes", "essay") as session:
        session.hello(create=True)
        first = session.ok("paragraphs")["paragraphs"][0]["id"]
        session.ok("replace_text", paragraph=first, start=0, end_paragraph=first, end=0, text="Introduction")
        session.ok("set_style", paragraph=first, style="heading-1")
        assert session.ok("name_thing", id=first)["name"] == "Introduction"
        (seen,) = [b for b in session.ok("paragraphs")["paragraphs"] if b["id"] == first]
        assert seen["name"] == "Introduction"

        # a heading is called by its words and is not renamed (D1311): the words are changed instead
        refused = session.call("rename_thing", id=first, name="Intro")
        assert not refused["ok"] and refused["error"]["code"] == "command_error", refused
        session.ok("replace_text", paragraph=first, start=0, end_paragraph=first, end=len("Introduction"), text="Intro")
        assert session.ok("name_thing", id=first)["name"] == "Intro", "a heading's name follows its words"

        # any other paragraph keeps a name it was given
        session.ok("replace_text", paragraph=first, start=5, end_paragraph=first, end=5, text="\nThe gardens.")
        second = session.ok("paragraphs")["paragraphs"][1]["id"]
        session.ok("rename_thing", id=second, name="Gardens")
        assert session.ok("name_thing", id=second)["name"] == "Gardens", "a name, once given, is kept"
        assert session.ok("thing_last_seen", id=second)["present"]
