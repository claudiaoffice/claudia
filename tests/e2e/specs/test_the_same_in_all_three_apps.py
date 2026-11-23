"""The steps of ``specs/objects/the-same-in-all-three-apps.feature`` (D1431, D1432, CODE-75): a viewer is refused
before anything is sent, two people see each other's objects, styles and palette at once, and undo and redo take what
an object shows with it. One server of all three apps; every scenario has a document of its own.

"I" is Ann in the scenarios of two people and of undo, and Vera, a viewer, in the scenarios of a viewer (Ann is her
colleague there). What a person sees is read from the page. Two checks read the wire, because no person can see them
(D1454): "nothing is sent" (no request that the server's protocol description marks as a change,
``/api/<app>/protocol``), and "the document no longer keeps what it showed" (the server's event that forgets the
picture, shape, chart or container an object showed, D1431).
"""

from __future__ import annotations

import json
import struct
import urllib.request
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from conftest import READY, Person, World, eventually
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/objects/the-same-in-all-three-apps.feature")

DOCUMENT = "(?P<document>text|workbook|presentation)"
APPS = {"text": "composes", "workbook": "computes", "presentation": "creates"}
OBJECTS = {
    "composes": "[data-testid=object-layer] .object[data-object]",
    "computes": ".viewport .object[data-object]",
    "creates": "[data-testid=slide] .obj",
}
#: Where an object's place is measured from: the sheet's cells, not the grid with its headers.
AREA = {**READY, "computes": ".viewport"}
ENTRIES = "ol.log > li.entry"
TOLD_WITHIN_MS = 2000
NEW_STYLE_NAME = "Words of others"
NEW_ACCENT = "#aa3355"


@pytest.fixture
def world(suite_world: World) -> World:
    """Every scenario here runs on the server of all three apps."""
    return suite_world


def _png(width: int = 200, height: int = 100) -> bytes:
    """A gradient, big enough to hold with a pointer and not to be mistaken for an empty frame."""
    rows = b"".join(
        b"\x00" + b"".join(bytes((255 * x // width, 255 * y // height, 160)) for x in range(width))
        for y in range(height)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    head = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


PICTURE = _png()


@dataclass
class Scene:
    """What a scenario remembers between its steps."""

    tries: list[tuple[str, str | None]] = field(default_factory=list)  # what was tried, and what she was told
    sent_before: int = 0
    before: dict = field(default_factory=dict)  # the document as people saw it before the viewer tried
    seen: Callable[[Person], None] | None = None  # the check of "sees it", for anyone
    inserted: dict = field(default_factory=dict)  # the object inserted: its ref and how it looked


@pytest.fixture
def scene() -> Scene:
    """A fresh memory for each scenario."""
    return Scene()


# ----------------------------------------------------------------------------------------------- what people see
def objects(person: Person) -> list[dict]:
    """The objects on the page: where they are in the document's area, how large, and what they show."""
    return person.page.eval_on_selector_all(
        OBJECTS[person.app],
        """(els, area) => { const a = document.querySelector(area).getBoundingClientRect()
          return els.map(e => {
            const r = e.getBoundingClientRect(), img = e.querySelector('img'), path = e.querySelector('svg path')
            return {x: Math.round(r.x - a.x), y: Math.round(r.y - a.y), w: Math.round(r.width), h: Math.round(r.height),
                    picture: img ? img.src : null, outline: path ? path.getAttribute('d') : null} }) }""",
        AREA[person.app],
    )


def looks(person: Person) -> list[dict]:
    """What the objects show and how large they are, wherever the page has them."""
    return [{k: v for k, v in o.items() if k not in ("x", "y")} for o in objects(person)]


def entries(person: Person) -> int:
    """How many entries the history shows."""
    return person.page.locator(ENTRIES).count()


def wait_for_objects(person: Person, count: int) -> None:
    """Until the page shows ``count`` objects."""
    person.page.wait_for_function(
        "([selector, count]) => document.querySelectorAll(selector).length === count",
        arg=[OBJECTS[person.app], count],
        timeout=15000,
    )


def style_names(person: Person) -> list[str]:
    """The names in Format ▸ All Styles…, read from the dialog, which is closed again."""
    person.menu("Format", "All Styles…")
    names = person.page.eval_on_selector_all(
        "[data-testid=styles-list] [data-style] .sample", "els => els.map(e => e.textContent.trim())"
    )
    person.page.keyboard.press("Escape")
    return names


def accent(person: Person) -> str:
    """The colour of the accent as Format ▸ Colours… shows it; the dialog is closed again."""
    person.menu("Format", "Colours…")
    colour = person.page.eval_on_selector(
        "[data-testid=role-list] [data-role=accent] i", "e => getComputedStyle(e).backgroundColor"
    )
    person.page.keyboard.press("Escape")
    return colour


def rgb(hex_colour: str) -> str:
    """``#aa3355`` as a browser writes a computed colour."""
    red, green, blue = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgb({red}, {green}, {blue})"


def the_document(person: Person) -> dict:
    """What the viewer scenario says stays as it was, as this person sees it: objects, styles, the accent."""
    return {"objects": objects(person), "styles": style_names(person), "accent": accent(person)}


# ----------------------------------------------------------------------------------------------- what people do
def insert_picture(person: Person) -> None:
    """Edit ▸ Image…, a gradient with its description."""
    person.menu("Edit", "Image…")
    page = person.page
    page.set_input_files(
        ".modal input[type=file]", files=[{"name": "gradient.png", "mimeType": "image/png", "buffer": PICTURE}]
    )
    page.wait_for_selector(".modal .preview img")
    page.fill('.modal input[maxlength="300"]', "a gradient, red to the right, green downwards")
    page.click(".modal button[type=submit]")


def insert_container(person: Person) -> None:
    """A LaTeX container, left as it is; the scenario is skipped where this server has no LaTeX (the entry is off)."""
    person.menu("Insert", "Container")
    latex = person.page.locator('.menus .drop [role=menuitem]:has-text("LaTeX")').first
    if latex.is_disabled():
        person.page.keyboard.press("Escape")
        pytest.skip("this server cannot make a LaTeX container (no XeLaTeX), so it has none to insert")
    latex.click()
    person.page.keyboard.press("Escape")  # a new container is open for writing: leave it as it is


def insert_shape(person: Person) -> None:
    """Edit ▸ Rectangle."""
    person.menu("Edit", "Rectangle")


def insert_chart(person: Person) -> None:
    """Three numbers in the first column, selected, and a chart of them as an object on the sheet."""
    page = person.page
    first_cell = {"x": 92, "y": 39}  # A1, below the column headers and right of the row headers
    page.locator(".viewport").click(position=first_cell)
    for number in ("1", "2", "3"):
        page.keyboard.type(number)
        page.keyboard.press("Enter")
    page.locator(".viewport").click(position=first_cell)
    page.keyboard.press("Shift+ArrowDown")
    page.keyboard.press("Shift+ArrowDown")
    person.menu("Edit", "Chart…")
    page.check(".modal input[value=sheet]")
    page.click(".modal button[type=submit]")
    page.wait_for_selector(f"{OBJECTS['computes']} .js-plotly-plot .main-svg", state="attached")  # drawn: it is there


INSERT = {
    "a picture": insert_picture,
    "a container": insert_container,
    "a shape": insert_shape,
    "a chart": insert_chart,
}


def insert(person: Person, what: str) -> None:
    """Insert ``what`` and wait until the page shows it."""
    count = len(objects(person))
    INSERT[what](person)
    wait_for_objects(person, count + 1)
    person.page.keyboard.press("Escape")


def drag_by(person: Person, locator, dx: float, dy: float) -> None:
    """Hold ``locator`` in its middle and move it by ``dx``, ``dy``."""
    box = locator.bounding_box()
    assert box, "it is not on the screen"
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    person.page.mouse.move(x, y)
    person.page.mouse.down()
    person.page.mouse.move(x + dx, y + dy, steps=10)
    person.page.mouse.up()


def rename_first_style(person: Person) -> None:
    """Format ▸ All Styles…, Rename on the first style, a new name."""
    person.menu("Format", "All Styles…")
    person.page.locator("[data-rename]").first.click()
    name = person.page.locator(".modal form.rename input")
    name.fill(NEW_STYLE_NAME)
    name.press("Enter")
    person.page.locator(f'[data-style] .sample:text-is("{NEW_STYLE_NAME}")').wait_for()
    person.page.keyboard.press("Escape")


def change_the_accent(person: Person) -> None:
    """Format ▸ Colours…, the accent, a new colour, Change it."""
    person.menu("Format", "Colours…")
    person.page.click("[data-testid=role-list] [data-role=accent] button")
    person.page.locator(".modal input.mono").fill(NEW_ACCENT)
    person.page.click("[data-testid=apply-role]")
    person.page.keyboard.press("Escape")


def _same(seen, wanted, what: str) -> None:
    assert seen == wanted, f"{what}: {seen} instead of {wanted}"


# -------------------------------------------------------------------------------------------------- a viewer
@given(parsers.re(rf"a {DOCUMENT} that I may only view"))
def _a_document_i_may_only_view(world, scene, document):
    ann = world.join("Ann", APPS[document])
    ann.create()
    insert(ann, "a picture")  # something to try to move, resize, turn or delete
    vera = world.join("Vera")
    ann.share(vera, "viewer")
    vera.open()
    vera.wait_until_open()
    wait_for_objects(vera, 1)
    scene.before = {"Ann": the_document(ann), "Vera": objects(vera), "entries": entries(ann)}
    scene.sent_before = len(vera.sent)


def _try(vera: Person, scene: Scene, what: str, action: Callable[[], None]) -> None:
    """Try ``action`` as Vera and note what she was told within a moment, if anything."""
    told = len(vera.notices())
    action()
    try:
        vera.page.wait_for_function("told => (window.__notices || []).length > told", arg=told, timeout=TOLD_WITHIN_MS)
        scene.tries.append((what, vera.notices()[told]))
    except Exception:  # noqa: BLE001 - no notice within the time is the answer here, whatever Playwright calls it
        scene.tries.append((what, None))
    _close_menus_and_dialogs(vera)


def _close_menus_and_dialogs(person: Person) -> None:
    """A greyed entry that was clicked leaves its menu open: its title closes it. Escape closes a dialog."""
    page = person.page
    open_menu = page.locator(".menus .title.open")
    if open_menu.count():
        open_menu.first.click()
    for _ in range(3):
        if not page.locator(".modal").count():
            return
        page.keyboard.press("Escape")


def _choose_even_if_off(person: Person, title: str, *path: str) -> None:
    """What a person does with an entry that may be greyed out: she clicks it anyway (``Person.menu`` waits for it)."""
    person.page.click(f'.menus .title:text-is("{title}")')
    *submenus, entry = path
    for submenu in submenus:
        person.page.locator(f'.menus .drop [role=menuitem]:has-text("{submenu}")').first.hover()
    person.page.locator(f'.menus .drop [role=menuitem]:has-text("{entry}")').first.click(force=True)


def _try_to_rename_a_style(vera: Person) -> None:
    """Format ▸ All Styles…, and Rename where the dialog offers it."""
    vera.menu("Format", "All Styles…")
    rename = vera.page.locator("[data-rename]")
    if rename.count():
        rename.first.click()
        vera.page.keyboard.type(NEW_STYLE_NAME)
        vera.page.keyboard.press("Enter")


def _try_to_change_a_colour(vera: Person) -> None:
    """Format ▸ Colours…, the accent, a new colour where the field takes one, and Change it."""
    vera.menu("Format", "Colours…")
    vera.page.click("[data-testid=role-list] [data-role=accent] button")
    colour = vera.page.locator(".modal input.mono").first
    if colour.is_enabled():
        colour.fill(NEW_ACCENT)
    vera.page.locator("[data-testid=apply-role]").click(force=True)


def _drag_a_handle(person: Person) -> None:
    """A selected object shows handles to scale it; for a viewer it may show none, and then there is nothing to drag."""
    handle = person.page.locator("[data-handle=se]")
    if handle.count():
        drag_by(person, handle.first, 40, 20)


def _tries_on_an_object(vera: Person) -> dict[str, Callable[[], None]]:
    """Each thing she may try on the picture, by what it is called in a failure."""
    picture = vera.page.locator(OBJECTS[vera.app]).first

    def selected(then_do: Callable[[], None]) -> Callable[[], None]:
        return lambda: (picture.click(), then_do())

    return {
        "move it": lambda: drag_by(vera, picture, 60, 30),
        "resize it": selected(lambda: _drag_a_handle(vera)),
        "turn it": selected(lambda: _choose_even_if_off(vera, "Format", "Rotate", "Rotate Right")),
        "delete it": selected(lambda: vera.page.keyboard.press("Delete")),
    }


@when(parsers.re(r"I try to (?P<change>.+)"))
def _i_try_to(world, scene, change):
    vera = world.people["Vera"]
    tries = {
        "insert a picture": {change: lambda: _choose_even_if_off(vera, "Edit", "Image…")},
        "insert a container": {change: lambda: _choose_even_if_off(vera, "Insert", "Container", "LaTeX")},
        "rename a style": {change: lambda: _try_to_rename_a_style(vera)},
        "change a colour of the palette": {change: lambda: _try_to_change_a_colour(vera)},
        "move, resize, turn or delete an object": _tries_on_an_object(vera),
    }
    assert change in tries, f"no step code for trying to {change!r}"
    for what, action in tries[change].items():
        _try(vera, scene, what, action)


@then(parsers.parse('I am told "{words}"'))
def _i_am_told(scene, words):
    untold = [f"{what}: {told!r}" for what, told in scene.tries if told != words]
    assert not untold, f'not told "{words}" when trying to:\n' + "\n".join(untold)


def _protocol_writes(world: World, app: str) -> set[str]:
    """The methods the server's own description of its protocol marks as changes of a document."""
    with urllib.request.urlopen(f"{world.url}/api/{app}/protocol", timeout=10) as answer:
        methods = json.load(answer)["methods"]
    return {name for name, method in methods.items() if method.get("write")}


@then("the document is as it was")
def _as_it_was(world, scene):
    vera, ann = world.people["Vera"], world.people["Ann"]
    changes = [m for m in vera.sent[scene.sent_before :] if m in _protocol_writes(world, vera.app)]
    assert not changes, f"Vera's page sent changes: {changes}"
    _same(objects(vera), scene.before["Vera"], "the objects on Vera's page")
    _same(the_document(ann), scene.before["Ann"], "the document")


@then("my colleague sees no change and no message")
def _colleague_sees_nothing(world, scene):
    ann = world.people["Ann"]
    _same(ann.notices(), [], "what Ann was told")
    _same(entries(ann), scene.before["entries"], "the entries of Ann's history")
    _same(objects(ann), scene.before["Ann"]["objects"], "the objects on Ann's page")


# -------------------------------------------------------------------------------------------------- two people
@given(parsers.re(rf"a {DOCUMENT} open by me and by a colleague"))
def _open_by_two(world, document):
    ann = world.join("Ann", APPS[document])
    ann.create()
    ben = world.join("Ben")
    ann.share(ben, "editor")
    ben.open()
    ben.wait_until_open()


def _moves_a_container(world: World, scene: Scene) -> None:
    ann = world.ann
    insert(ann, "a container")
    wait_for_objects(world.people["Ben"], 1)
    before = objects(ann)
    drag_by(ann, ann.page.locator(OBJECTS[ann.app]).first, 80, 40)
    eventually(lambda: _differs(objects(ann), before))
    moved = objects(ann)  # remembered: after a reload both must show this place, not just agree with each other
    scene.seen = lambda person: _same(objects(person), moved, "the container")


def _differs(now, before) -> None:
    assert now != before, "it did not move"


def _renames_a_style(world: World, scene: Scene) -> None:
    rename_first_style(world.ann)
    scene.seen = lambda person: _same(NEW_STYLE_NAME in style_names(person), True, f"a style named {NEW_STYLE_NAME!r}")


def _changes_the_accent(world: World, scene: Scene) -> None:
    change_the_accent(world.ann)
    scene.seen = lambda person: _same(accent(person), rgb(NEW_ACCENT), "the accent")


@when(parsers.re(r"I (?P<change>move a container|rename a style|change a colour of the palette)"))
def _i_change(world, scene, change):
    {
        "move a container": _moves_a_container,
        "rename a style": _renames_a_style,
        "change a colour of the palette": _changes_the_accent,
    }[change](world, scene)


@when(parsers.re(r"I insert (?P<thing>a picture|a shape|a container|a chart)"))
def _i_insert(world, scene, thing):
    """In the scenarios of two people the colleague is to see it as I do; in those of undo, how it looks is kept."""
    ann = world.ann
    insert(ann, thing)
    shown = looks(ann)
    scene.seen = lambda person: _same(looks(person), shown, "the objects")

    def placed() -> None:
        changed = [
            c for m in ann.events if m.get("event") == "objects" for c in (m.get("data") or {}).get("changed", [])
        ]
        assert changed, "no object came from the server"
        scene.inserted = {"ref": changed[-1]["ref"], "looks": shown}

    eventually(placed)


@then("my colleague sees it without reloading")
def _colleague_sees_it(world, scene):
    eventually(lambda: scene.seen(world.people["Ben"]))


@then("after a reload we both see the same")
def _after_a_reload(world, scene):
    for person in (world.ann, world.people["Ben"]):
        person.reopen()
        eventually(lambda person=person: scene.seen(person))


# -------------------------------------------------------------------------------------- what an object shows
@given(parsers.re(rf"a {DOCUMENT}"))
def _a_document(world, document):
    world.join("Ann", APPS[document]).create()


def _shown(person: Person, ref: str) -> list:
    """What the server said, event by event, about what the object ``ref`` shows; ``None`` where it forgot it."""
    found = []
    for message in person.events:
        data = message.get("data", message)
        if isinstance(data, dict) and data.get("id") == ref and ("asset" in data or "definition" in data):
            found.append(data.get("asset", data.get("definition")))
    return found


@when("I undo")
def _i_undo(world):
    world.ann.page.keyboard.press("Escape")  # nothing selected: undo is the document's, not an object's text
    world.ann.menu("Edit", "Undo")


@when("I redo")
def _i_redo(world):
    world.ann.menu("Edit", "Redo")


@then("the object is gone, and the document no longer keeps what it showed")
def _gone(world, scene):
    ann = world.ann
    wait_for_objects(ann, 0)
    eventually(lambda: _same(_shown(ann, scene.inserted["ref"])[-1:], [None], "what the server keeps of it"))


@then("the object is back and shows the same as before")
def _back(world, scene):
    ann = world.ann
    wait_for_objects(ann, 1)
    eventually(lambda: _same(looks(ann), scene.inserted["looks"], "the object"))
