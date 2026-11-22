"""The steps of ``specs/objects/the-same-in-all-three-apps.feature`` (D1431, D1432, CODE-75): a viewer is refused
before anything is sent, two people see each other's objects, styles and palette at once, and undo and redo take what
an object shows with it. One server of all three apps; every scenario has a document of its own.

"I" is Ann in the scenarios of two people and of undo, and Vera, a viewer, in the scenarios of a viewer (Ann is her
colleague there). What a person sees is read from the page. Two checks read the wire, because no person can see them:
"nothing is sent" (no request the server's own protocol description marks as a change, ``/api/<app>/protocol``), and
"the document no longer keeps what it showed" (the server's event that forgets the picture, shape, chart or container
an object showed, D1431).
"""

from __future__ import annotations

import json
import struct
import time
import urllib.request
import zlib
from dataclasses import dataclass, field

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/objects/the-same-in-all-three-apps.feature")

APPS = {"text": "composes", "workbook": "computes", "presentation": "creates"}
OBJECTS = {
    "composes": "[data-testid=object-layer] .object[data-object]",
    "computes": ".viewport .object[data-object]",
    "creates": "[data-testid=slide] .obj",
}
ENTRIES = "ol.log > li.entry"
TOLD_WITHIN_MS = 2000
SEEN_WITHIN_S = 10.0
NEW_STYLE_NAME = "Words of others"
NEW_ACCENT = "#aa3355"


@pytest.fixture
def world(suite_world):
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


def eventually(check, seconds: float = SEEN_WITHIN_S) -> None:
    """Run ``check`` (it asserts) until it holds, for at most ``seconds``; the last failure is the answer."""
    end = time.monotonic() + seconds
    while True:
        try:
            check()
            return
        except AssertionError:
            if time.monotonic() > end:
                raise
            time.sleep(0.2)


@dataclass
class Scene:
    """What a scenario remembers between its steps."""

    tries: list[tuple[str, str | None]] = field(default_factory=list)  # (what was tried, what the person was told)
    sent_before: int = 0
    entries_before: int = 0
    objects_before: list[dict] = field(default_factory=list)
    seen: object = None  # what "my colleague sees it" compares with
    inserted: dict | None = None  # the object inserted, and what it showed


@pytest.fixture
def scene() -> Scene:
    return Scene()


# ----------------------------------------------------------------------------------------------- what people do
def objects(person) -> list[dict]:
    """The objects on the page, where they are (rounded to whole pixels)."""
    return person.page.eval_on_selector_all(
        OBJECTS[person.app],
        "els => els.map(e => { const r = e.getBoundingClientRect()"
        "; return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)} })",
    )


def entries(person) -> int:
    return person.page.locator(ENTRIES).count()


def wait_for_objects(person, count: int) -> None:
    person.page.wait_for_function(
        "([selector, count]) => document.querySelectorAll(selector).length === count",
        arg=[OBJECTS[person.app], count],
        timeout=15000,
    )


def insert_picture(person) -> None:
    person.menu("Edit", "Image…")
    page = person.page
    page.set_input_files(
        ".modal input[type=file]", files=[{"name": "gradient.png", "mimeType": "image/png", "buffer": PICTURE}]
    )
    page.wait_for_selector(".modal .preview img")
    page.fill('.modal input[maxlength="300"]', "a gradient, red to the right, green downwards")
    page.click(".modal button[type=submit]")


def insert_container(person) -> None:
    """A LaTeX container, left as it is; the scenario is skipped where this server has no LaTeX (the entry is off)."""
    person.menu("Insert", "Container")
    latex = person.page.locator('.menus .drop [role=menuitem]:has-text("LaTeX")').first
    if latex.is_disabled():
        person.page.keyboard.press("Escape")
        pytest.skip("this server cannot make a LaTeX container (no XeLaTeX), so it has none to insert")
    latex.click()
    person.page.keyboard.press("Escape")  # a new container is open for writing: leave it as it is


def insert_shape(person) -> None:
    person.menu("Edit", "Rectangle")


def insert_chart(person) -> None:
    """Three numbers in the first column, selected, and a chart of them as an object on the sheet."""
    page = person.page
    first_cell = {"x": 92, "y": 39}
    page.locator(".viewport").click(position=first_cell)
    for number in ("1", "2", "3"):
        page.keyboard.type(number)
        page.keyboard.press("Enter")
    page.locator(".viewport").click(position=first_cell)
    page.keyboard.press("Shift+ArrowDown")
    page.keyboard.press("Shift+ArrowDown")
    person.menu("Edit", "Chart…")
    page.check(".modal input[value=object]")
    page.click(".modal button[type=submit]")


INSERT = {
    "a picture": insert_picture,
    "a container": insert_container,
    "a shape": insert_shape,
    "a chart": insert_chart,
}


def insert(person, what: str) -> None:
    """Insert ``what`` and wait until the page shows it."""
    count = len(objects(person))
    INSERT[what](person)
    wait_for_objects(person, count + 1)
    person.page.keyboard.press("Escape")


def share(owner, person, role: str) -> None:
    """The owner adds ``person`` with ``role`` (File ▸ Manage ▸ Share…), with the password that person will use."""
    owner.menu("File", "Manage", "Share…")
    dialog = owner.page.locator(".modal")
    dialog.get_by_label("Name", exact=True).fill(person.name.lower())
    dialog.locator("input[name=share-password]").fill(person.password)
    dialog.locator("select").select_option(role)
    dialog.get_by_role("button", name="Add person").click()
    owner.page.wait_for_selector(f'.added li:has-text("{person.name.lower()} ({role})")')
    dialog.get_by_role("button", name="Done").click()


def drag_by(person, locator, dx: float, dy: float) -> None:
    box = locator.bounding_box()
    assert box, "it is not on the screen"
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    person.page.mouse.move(x, y)
    person.page.mouse.down()
    person.page.mouse.move(x + dx, y + dy, steps=10)
    person.page.mouse.up()


def style_names(person) -> list[str]:
    """The names in Format ▸ All Styles…, read from the dialog and closed again."""
    person.menu("Format", "All Styles…")
    names = person.page.eval_on_selector_all(
        "[data-testid=styles-list] [data-style] .sample", "els => els.map(e => e.textContent.trim())"
    )
    person.page.keyboard.press("Escape")
    return names


def accent(person) -> str:
    """The colour of the accent in Format ▸ Colours…, as the dialog shows it."""
    person.menu("Format", "Colours…")
    colour = person.page.eval_on_selector(
        "[data-testid=role-list] [data-role=accent] i", "e => getComputedStyle(e).backgroundColor"
    )
    person.page.keyboard.press("Escape")
    return colour


def rgb(hex_colour: str) -> str:
    red, green, blue = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgb({red}, {green}, {blue})"


# -------------------------------------------------------------------------------------------------- a viewer
@given(parsers.re(r"a (?P<document>text|workbook|presentation) that I may only view"))
def _a_document_i_may_only_view(world, scene, document):
    ann = world.join("Ann", APPS[document])
    ann.create()
    insert(ann, "a picture")  # something to try to move, resize, turn or delete
    vera = world.join("Vera")
    share(ann, vera, "viewer")
    vera.open()
    vera.wait_until_open()
    wait_for_objects(vera, 1)
    scene.sent_before = len(vera.sent)
    scene.entries_before = entries(ann)
    scene.objects_before = objects(ann)


def _try(vera, scene: Scene, what: str, action) -> None:
    """Try ``action`` as Vera and note what she was told, if anything, within a moment."""
    vera.page.evaluate("() => document.querySelector('.toast')?.click()")  # a notice from before goes away first
    action()
    toast = vera.page.locator(".toast")
    try:
        toast.wait_for(timeout=TOLD_WITHIN_MS)
        scene.tries.append((what, toast.inner_text().strip()))
    except Exception:  # noqa: BLE001 - nothing shown is the answer here, whatever Playwright calls it
        scene.tries.append((what, None))
    _close_menus_and_dialogs(vera)


def _close_menus_and_dialogs(person) -> None:
    """A greyed entry that was clicked leaves its menu open: its title closes it. Escape closes a dialog."""
    page = person.page
    open_menu = page.locator(".menus .title.open")
    if open_menu.count():
        open_menu.first.click()
    for _ in range(3):
        if not page.locator(".modal").count():
            return
        page.keyboard.press("Escape")


def _choose_even_if_off(person, title: str, *path: str) -> None:
    """What a person does with an entry that may be greyed out: she clicks it anyway."""
    person.page.click(f'.menus .title:text-is("{title}")')
    *submenus, entry = path
    for submenu in submenus:
        person.page.locator(f'.menus .drop [role=menuitem]:has-text("{submenu}")').first.hover()
    person.page.locator(f'.menus .drop [role=menuitem]:has-text("{entry}")').first.click(force=True)


def _select_and(thing, then_do) -> None:
    thing.click()
    then_do()


def _drag_a_handle(person) -> None:
    """A selected object shows handles to scale it; for a viewer it may show none, and then there is nothing to drag."""
    handle = person.page.locator("[data-handle=se]")
    if handle.count():
        drag_by(person, handle.first, 40, 20)


def _try_rename_a_style(vera) -> None:
    vera.menu("Format", "All Styles…")
    rename = vera.page.locator("[data-rename]").first
    if rename.count():
        rename.click()
        vera.page.keyboard.type(NEW_STYLE_NAME)
        vera.page.keyboard.press("Enter")


def _try_change_a_colour(vera) -> None:
    vera.menu("Format", "Colours…")
    vera.page.click("[data-testid=role-list] [data-role=accent] button")
    colour = vera.page.locator(".modal input.mono").first
    if colour.is_enabled():
        colour.fill(NEW_ACCENT)
    vera.page.locator("[data-testid=apply-role]").click(force=True)


@when(parsers.re(r"I try to (?P<change>.+)"))
def _i_try_to(world, scene, change):
    vera = world.people["Vera"]
    page = vera.page
    picture = page.locator(OBJECTS[vera.app]).first
    if change == "insert a picture":
        _try(vera, scene, change, lambda: _choose_even_if_off(vera, "Edit", "Image…"))
    elif change == "insert a container":
        _try(vera, scene, change, lambda: _choose_even_if_off(vera, "Insert", "Container", "LaTeX"))
    elif change == "rename a style":
        _try(vera, scene, change, lambda: _try_rename_a_style(vera))
    elif change == "change a colour of the palette":
        _try(vera, scene, change, lambda: _try_change_a_colour(vera))
    elif change == "move, resize, turn or delete an object":
        _try(vera, scene, "move it", lambda: drag_by(vera, picture, 60, 30))
        _try(
            vera,
            scene,
            "resize it",
            lambda: _select_and(picture, lambda: _drag_a_handle(vera)),
        )
        _try(
            vera,
            scene,
            "turn it",
            lambda: _select_and(picture, lambda: _choose_even_if_off(vera, "Format", "Rotate", "Rotate Right")),
        )
        _try(vera, scene, "delete it", lambda: _select_and(picture, lambda: page.keyboard.press("Delete")))
    else:
        raise AssertionError(f"no step code for trying to {change!r}")


@then(parsers.parse('I am told "{words}"'))
def _i_am_told(scene, words):
    untold = [f"{what}: {told!r}" for what, told in scene.tries if told != words]
    assert not untold, f'not told "{words}" when trying to:\n' + "\n".join(untold)


def _protocol_writes(world, app: str) -> set[str]:
    with urllib.request.urlopen(f"{world.url}/api/{app}/protocol", timeout=10) as answer:
        methods = json.load(answer)["methods"]
    return {name for name, method in methods.items() if method.get("write")}


@then("the document is as it was")
def _as_it_was(world, scene):
    vera, ann = world.people["Vera"], world.people["Ann"]
    changes = [m for m in vera.sent[scene.sent_before :] if m in _protocol_writes(world, vera.app)]
    assert not changes, f"Vera's page sent changes: {changes}"
    assert objects(ann) == scene.objects_before, "the objects are not where they were"
    assert entries(ann) == scene.entries_before, "the history has a new entry"


@then("my colleague sees no change and no message")
def _colleague_sees_nothing(world, scene):
    ann = world.people["Ann"]
    assert ann.page.locator(".toast").count() == 0, f"Ann was told: {ann.page.locator('.toast').inner_text()}"
    assert objects(ann) == scene.objects_before and entries(ann) == scene.entries_before


# -------------------------------------------------------------------------------------------------- two people
@given(parsers.re(r"a (?P<document>text|workbook|presentation) open by me and by a colleague"))
def _open_by_two(world, document):
    ann = world.join("Ann", APPS[document])
    ann.create()
    ben = world.join("Ben")
    share(ann, ben, "editor")
    ben.open()
    ben.wait_until_open()


def _has(names: list[str], name: str) -> None:
    assert name in names, f"{name!r} is not among {names}"


def _equal(seen, wanted) -> None:
    assert seen == wanted, f"{seen} instead of {wanted}"


def _same_places(person, ann) -> None:
    """The objects lie where Ann has them, relative to the document's own area (the pages may scroll differently)."""
    assert _relative(person) == _relative(ann), f"{_relative(person)} instead of {_relative(ann)}"


def _relative(person) -> list[tuple[int, int]]:
    area = person.page.locator(READY_AREA[person.app]).first.bounding_box()
    return [(o["x"] - round(area["x"]), o["y"] - round(area["y"])) for o in objects(person)]


READY_AREA = {"composes": "[data-testid=text]", "computes": ".viewport", "creates": "[data-testid=slide]"}


def _sees_objects(count: int):
    return lambda person: wait_for_objects(person, count)


@when(parsers.re(r"I (?P<change>move a container|rename a style|change a colour of the palette)"))
def _i_change(world, scene, change):
    ann = world.ann
    if change == "move a container":
        insert(ann, "a container")
        wait_for_objects(world.people["Ben"], 1)
        before = _relative(ann)
        drag_by(ann, ann.page.locator(OBJECTS[ann.app]).first, 80, 40)
        eventually(lambda: _differ(_relative(ann), before))
        scene.seen = lambda person: _same_places(person, ann)
    elif change == "rename a style":
        ann.menu("Format", "All Styles…")
        ann.page.locator("[data-rename]").first.click()
        name = ann.page.locator(".modal form.rename input")
        name.fill(NEW_STYLE_NAME)
        name.press("Enter")
        ann.page.locator(f'[data-style] .sample:text-is("{NEW_STYLE_NAME}")').wait_for()
        ann.page.keyboard.press("Escape")
        scene.seen = lambda person: _has(style_names(person), NEW_STYLE_NAME)
    else:
        ann.menu("Format", "Colours…")
        ann.page.click("[data-testid=role-list] [data-role=accent] button")
        ann.page.locator(".modal input.mono").fill(NEW_ACCENT)
        ann.page.click("[data-testid=apply-role]")
        ann.page.keyboard.press("Escape")
        scene.seen = lambda person: _equal(accent(person), rgb(NEW_ACCENT))


def _differ(now, before) -> None:
    assert now != before, "it did not move"


@then("my colleague sees it without reloading")
def _colleague_sees_it(world, scene):
    eventually(lambda: scene.seen(world.people["Ben"]))


@then("after a reload we both see the same")
def _after_a_reload(world, scene):
    for person in (world.ann, world.people["Ben"]):
        person.reopen()
    for person in (world.ann, world.people["Ben"]):
        eventually(lambda person=person: scene.seen(person))


# -------------------------------------------------------------------------------------- what an object shows
@given(parsers.re(r"a (?P<document>text|workbook|presentation)"))
def _a_document(world, document):
    world.join("Ann", APPS[document]).create()


def _shown(person, ref: str) -> list[dict]:
    """Every event of the server about what the object ``ref`` shows (an image, a shape, a chart, a container)."""
    found = []
    for message in person.events:
        data = message.get("data", message)
        if isinstance(data, dict) and data.get("id") == ref and ("asset" in data or "definition" in data):
            found.append(data.get("asset", data.get("definition")))
    return found


@when(parsers.re(r"I insert (?P<thing>a picture|a shape|a container|a chart)"))
def _i_insert(world, scene, thing):
    """In the scenarios of two people the colleague is to see it; in those of undo, what it shows is remembered."""
    ann = world.ann
    insert(ann, thing)
    scene.seen = _sees_objects(len(objects(ann)))

    def placed() -> None:
        changed = [
            c for m in ann.events if m.get("event") == "objects" for c in (m.get("data") or {}).get("changed", [])
        ]
        assert changed, "no object came from the server"
        ref = changed[-1]["ref"]
        assert _shown(ann, ref), "nothing came for what it shows"
        scene.inserted = {"ref": ref, "shows": _shown(ann, ref)[-1]}

    eventually(placed)


@when("I undo")
def _i_undo(world):
    world.ann.page.mouse.click(5, 300)  # nothing selected: undo is the document's, not an object's text
    world.ann.menu("Edit", "Undo")


@when("I redo")
def _i_redo(world):
    world.ann.menu("Edit", "Redo")


@then("the object is gone, and the document no longer keeps what it showed")
def _gone(world, scene):
    ann = world.ann
    wait_for_objects(ann, 0)
    eventually(lambda: _forgotten(_shown(ann, scene.inserted["ref"])))


@then("the object is back and shows the same as before")
def _back(world, scene):
    ann = world.ann
    wait_for_objects(ann, 1)
    eventually(lambda: _equal(_shown(ann, scene.inserted["ref"])[-1], scene.inserted["shows"]))


def _forgotten(shown: list) -> None:
    assert shown[-1] is None, "the document still keeps what the object showed (no event forgot it)"
