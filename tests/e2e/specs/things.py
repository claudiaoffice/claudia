"""What people do with the objects of a document, the same in every step file: the page's objects in each app, and
how a person inserts a picture, a shape, a container or a chart. Not a test file."""

from __future__ import annotations

import struct
import zlib

import pytest
from conftest import READY, Person

OBJECTS = {
    "composes": "[data-testid=object-layer] .object[data-object]",
    "computes": ".viewport .object[data-object]",
    "creates": "[data-testid=slide] .obj",
}
#: Where an object's place is measured from: the sheet's cells, not the grid with its headers.
AREA = {**READY, "computes": ".viewport"}


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
FIRST_CELL = {"x": 92, "y": 39}  # where A1 is on a sheet: below the column headers, right of the row headers


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


def wait_for_objects(person: Person, count: int) -> None:
    """Until the page shows ``count`` objects."""
    person.page.wait_for_function(
        "([selector, count]) => document.querySelectorAll(selector).length === count",
        arg=[OBJECTS[person.app], count],
        timeout=15000,
    )


def insert_text_box(person: Person) -> None:
    """Edit ▸ Text Box."""
    person.menu("Edit", "Text Box")


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
    latex = person.menu_item("LaTeX")
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
    page.locator(".viewport").click(position=FIRST_CELL)
    for number in ("1", "2", "3"):
        page.keyboard.type(number)
        page.keyboard.press("Enter")
    page.locator(".viewport").click(position=FIRST_CELL)
    page.keyboard.press("Shift+ArrowDown")
    page.keyboard.press("Shift+ArrowDown")
    person.menu("Edit", "Chart…")
    page.check(".modal input[value=object]")
    page.click(".modal button[type=submit]")


INSERT = {
    "a text box": insert_text_box,
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
