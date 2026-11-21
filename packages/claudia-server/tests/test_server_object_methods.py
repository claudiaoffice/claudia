"""The methods that change one object are the same in every app; only the words that say where differ (CODE-27)."""

import base64
import struct

import pytest

from claudia_composes import TextModel
from claudia_computes import WorkbookModel
from claudia_core import Document, MemoryStore
from claudia_creates import SlideModel
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.computes import computes_methods
from claudia_server.creates import creates_methods
from claudia_server.protocol import Context, Limits, MethodTable, RequestError

ANN = Account("ann", "owner")

PICTURE = "w:int h:int data:image alt:str source_name:str source_path:str? decorative:bool? fit:bool? base:revision?"
DESCRIBE = "id:str description:text decorative:bool? base:revision?"
SAME_EVERYWHERE = {
    "images": "",
    "describe_object": DESCRIBE,
    "rotate_object": "id:str rotation:int base:revision?",
    "remove_object": "id:str base:revision?",
}
# Text boxes and shapes are put with the same words wherever a person can put them; the app says where.
ADD_OBJECT = "{where} kind:str w:int h:int shape:str? text:text? base:revision?"
# The words of each app: where a new object goes, where one is moved to, what a new frame is besides its size.
WORDS = {
    "computes": {
        "add_image": f"sheet:str row:int col:int {PICTURE}",
        "add_container": "sheet:str row:int col:int w:int h:int type:str source:text params:dict? alt:text? "
        "fit:bool? base:revision?",
        "move_object": "id:str row:int col:int base:revision?",
        "resize_object": "id:str row:int col:int w:int h:int base:revision?",
    },
    "creates": {
        "add_image": f"slide:str x:int y:int {PICTURE}",
        "add_container": "slide:str x:int y:int w:int h:int type:str source:text params:dict? alt:text? fit:bool? "
        "base:revision?",
        "add_object": ADD_OBJECT.format(where="slide:str x:int y:int"),
        "move_object": "id:str x:int y:int base:revision?",
        "resize_object": "id:str x:int y:int w:int h:int base:revision?",
    },
    "composes": {
        "add_image": f"block:str offset:int wrap:str? gap:int? {PICTURE}",
        "add_container": "block:str offset:int wrap:str? gap:int? w:int h:int type:str source:text params:dict? "
        "alt:text? fit:bool? base:revision?",
        "add_object": ADD_OBJECT.format(where="block:str offset:int wrap:str? gap:int?"),
        "set_wrap": "id:str wrap:str gap:int? base:revision?",
        "move_object": "id:str block:str offset:int dx:int? dy:int? base:revision?",
        "resize_object": "id:str w:int h:int base:revision?",
    },
}
TABLES = {"computes": computes_methods, "creates": creates_methods, "composes": composes_methods}
WRITES = {
    "add_image",
    "add_container",
    "add_object",
    "set_wrap",
    "describe_object",
    "move_object",
    "resize_object",
    "rotate_object",
}


def words_of(table: MethodTable, name: str) -> str:
    """A method's parameters written the way a spec writes them, so the expectations above read like the code."""
    described = table.describe()["methods"][name]
    return " ".join(f"{p['name']}:{p['type']}{'' if p['required'] else '?'}" for p in described["params"])


@pytest.mark.parametrize("app", sorted(TABLES))
def test_the_object_methods_speak_the_same_words_in_every_app_but_where(app):
    table = TABLES[app]
    for name, spec in {**SAME_EVERYWHERE, **WORDS[app]}.items():
        assert words_of(table, name) == spec, (app, name)
        assert table.describe()["methods"][name]["write"] == (name in WRITES or name == "remove_object"), (app, name)


@pytest.mark.parametrize("app", sorted(TABLES))
def test_the_help_of_a_move_explains_the_words_of_its_app(app):
    word = {"computes": "`row`", "creates": "`x`", "composes": "`block`"}[app]
    assert word in TABLES[app].describe()["methods"]["move_object"]["doc"]


# --------------------------------------------------------------------------------------------- one object, every app
def tiny_gif(width: int, height: int) -> str:
    header = b"GIF89a" + struct.pack("<HHBBB", width, height, 0, 0, 0)
    frame = b"\x2c" + struct.pack("<HHHH", 0, 0, width, height) + b"\x00" + b"\x02\x01\x00\x00"
    return base64.b64encode(header + frame + b"\x3b").decode("ascii")


def a_workbook():
    document = Document(WorkbookModel(), store=MemoryStore())
    call("computes", document, "add_sheet", {"name": "S"})
    return document


def a_deck():
    return Document(SlideModel.empty(), store=MemoryStore())


def a_text():
    document = Document(TextModel(), store=MemoryStore())
    params = {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "a text with a picture"}
    call("composes", document, "replace_text", params)
    return document


APPS = {
    # how to make a document, where a new object goes, where it moves, its new frame
    "computes": (a_workbook, {"sheet": "s1", "row": 2, "col": 3}, {"row": 4, "col": 1}, {"row": 4, "col": 1}),
    "creates": (a_deck, {"slide": "s1", "x": 100, "y": 80}, {"x": 300, "y": 200}, {"x": 300, "y": 200}),
    "composes": (a_text, {"block": "b1", "offset": 2}, {"block": "b1", "offset": 9, "dx": 30, "dy": 4}, {}),
}


def call(app, document, name, params=None):
    ctx = Context(document, ANN, Limits(), users=lambda: ["ann"], lock_seconds=30.0)
    return TABLES[app].dispatch(ctx, name, params)


def the_object(document, object_id):
    return document.model.get_object(object_id)


def add_picture(app, document, **extra):
    _make, where, _moved, _frame = APPS[app]
    given = {**where, "w": 40, "h": 20, "data": tiny_gif(40, 20), "alt": "a red square", "source_name": "red.gif"}
    return call(app, document, "add_image", {**given, **extra})


@pytest.mark.parametrize("app", sorted(APPS))
def test_a_picture_comes_in_from_disk_with_its_words_and_the_plain_image_style(app):
    document = APPS[app][0]()
    added = add_picture(app, document)
    body = the_object(document, added["object"]).body
    assert (body.kind, body.style, body.w, body.h) == ("image", "plain-image", 40, 20)
    assert body.imported.alt == "a red square"
    assert added["revision"] == document.revision.to_data()
    assert [image["width"] for image in call(app, document, "images")] == [40]


@pytest.mark.parametrize("app", sorted(APPS))
def test_a_picture_needs_words_unless_it_is_decoration(app):
    document = APPS[app][0]()
    with pytest.raises(RequestError):
        add_picture(app, document, alt="")
    added = add_picture(app, document, alt="", decorative=True)
    assert the_object(document, added["object"]).body.decorative


@pytest.mark.parametrize("app", sorted(APPS))
def test_an_object_is_described_moved_sized_turned_and_taken_away(app):
    make, _where, moved, frame = APPS[app]
    document = make()
    object_id = add_picture(app, document)["object"]

    call(app, document, "describe_object", {"id": object_id, "description": "a red square, the logo"})
    assert the_object(document, object_id).body.description == "a red square, the logo"

    call(app, document, "move_object", {"id": object_id, **moved})
    anchor = the_object(document, object_id).anchor.to_data()
    assert {key: anchor[key] for key in moved if key in anchor} == {k: v for k, v in moved.items() if k in anchor}

    call(app, document, "resize_object", {"id": object_id, **frame, "w": 80, "h": 40})
    assert (the_object(document, object_id).body.w, the_object(document, object_id).body.h) == (80, 40)
    assert the_object(document, object_id).anchor.to_data() == anchor

    call(app, document, "rotate_object", {"id": object_id, "rotation": -20})
    assert the_object(document, object_id).body.rotation == 340

    call(app, document, "remove_object", {"id": object_id})
    assert object_id not in document.model.objects
    call(app, document, "undo", {})
    assert the_object(document, object_id).anchor.to_data() == anchor


@pytest.mark.parametrize("app", sorted(APPS))
def test_a_describe_of_a_picture_without_words_is_refused(app):
    document = APPS[app][0]()
    object_id = add_picture(app, document)["object"]
    with pytest.raises(RequestError):
        call(app, document, "describe_object", {"id": object_id, "description": ""})
