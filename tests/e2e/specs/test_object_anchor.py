"""Where an object hangs, and dragging it to another paragraph: the steps of
``claudiaoffice-log/specs/composes/object-anchor.feature`` (D1351, D1352).

Which paragraph an object hangs from is read from what a person sees: the anchor mark of the selected object. Steps
that need a second person are not bound (the sharing they need is not automated yet), so their scenario skips.
"""

from __future__ import annotations

import time

from conftest import eventually
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/composes/object-anchor.feature")

OBJECT = "[data-object]"
PARAGRAPHS = "[data-testid=text] [data-paragraph]"
MARK = "[data-testid=anchor-mark]"
LINE = "Paragraph number {n} has enough words in it to fill a line and then go on to a second line, which it does."
MOVED = "Moved an object"  # how the history speaks of a move


def _equal(got, want) -> None:
    assert got == want, f"expected {want!r}, the page shows {got!r}"


def settled_box(page, locator) -> dict:
    """The box of a paragraph once the layout stopped moving it (a click at a stale box lands in another paragraph)."""
    last = None
    end = time.monotonic() + 5.0
    while time.monotonic() < end:
        box = locator.bounding_box()
        if box is not None and box == last:
            return box
        last = box
        page.wait_for_timeout(150)
    raise AssertionError("the layout of the first paragraph does not settle")


def paragraph_id(page, n: int) -> str:
    return page.locator(PARAGRAPHS).nth(n - 1).get_attribute("data-paragraph")


def moves(page) -> int:
    return page.locator(".log li.entry .what", has_text=MOVED).count()


def select(page) -> None:
    page.locator(OBJECT).first.click(position={"x": 6, "y": 6})
    page.wait_for_selector(f"{OBJECT}.selected")


def hangs_from(page) -> str | None:
    """The paragraph the selected object's mark is in."""
    marks = page.locator(MARK)
    return marks.first.get_attribute("data-paragraph") if marks.count() else None


def press_on_object(world) -> tuple[float, float]:
    page = world.ann.page
    select(page)
    world.moves_before = moves(page)
    box = page.locator(OBJECT).first.bounding_box()
    x, y = box["x"] + 20, box["y"] + 20
    page.mouse.move(x, y)
    page.mouse.down()
    return x, y


def onto_third(world, start: tuple[float, float]) -> None:
    page = world.ann.page
    third = page.locator(PARAGRAPHS).nth(2).bounding_box()
    page.mouse.move(start[0] + 40, third["y"] + 30, steps=15)  # the grip is 20 below the corner: the corner is in it
    page.wait_for_timeout(150)


# ------------------------------------------------------------------------------------------------ the text
@given(parsers.parse('a new composes document "{name}" in which I am Ann, an owner'))
def _new_document(world, name):  # noqa: ARG001 - every scenario gets a document of its own
    world.join("Ann").create()


@given("the text has four paragraphs of two lines each")
def _four(world):
    page = world.ann.page
    page.click("[data-testid=text]")
    for n in range(1, 5):
        page.keyboard.type(LINE.format(n=n))
        if n < 4:
            page.keyboard.press("Enter")
    page.wait_for_selector("[data-testid=text] [data-overlay]", state="detached")
    eventually(lambda: _equal(page.locator(PARAGRAPHS).count(), 4))


@given("I have put a text box in the first paragraph")
def _text_box(world):
    page = world.ann.page
    first = settled_box(page, page.locator(PARAGRAPHS).first)
    page.mouse.click(first["x"] + first["width"] * 0.3, first["y"] + 8)
    world.ann.menu("Edit", "Text Box")
    page.wait_for_selector(OBJECT)
    page.wait_for_timeout(500)
    page.keyboard.press("Escape")  # a new text box is being written in
    page.wait_for_timeout(200)


@given("a table of 2 columns and 2 rows after the first paragraph")
def _table(world):
    page = world.ann.page
    first = settled_box(page, page.locator(PARAGRAPHS).first)
    page.mouse.click(first["x"] + first["width"] - 4, first["y"] + first["height"] - 8)  # its last line, past the box
    page.keyboard.press("End")
    world.ann.menu("Insert", "Table…")
    page.fill("[data-testid=table-cols]", "2")
    page.fill("[data-testid=table-rows]", "2")
    page.click("[data-testid=table-insert]")
    page.wait_for_selector("[data-testid=table]")
    page.keyboard.press("Escape")


# ------------------------------------------------------------------------------------------------ dragging
@when("I drag the text box onto the third paragraph and let go")
@given("I have dragged the text box onto the third paragraph")
def _drag_and_drop(world):
    onto_third(world, press_on_object(world))
    world.ann.page.mouse.up()
    world.ann.page.wait_for_timeout(800)


@when("I drag the text box onto the third paragraph without letting go")
def _drag_hold(world):
    onto_third(world, press_on_object(world))


@when("I drag the text box onto the third paragraph and press Esc before I let go")
def _drag_escape(world):
    onto_third(world, press_on_object(world))
    world.ann.page.keyboard.press("Escape")
    world.ann.page.mouse.up()
    world.ann.page.wait_for_timeout(800)


@when("I drag the table by its name tab onto the third paragraph")
def _drag_table(world):
    page = world.ann.page
    tab = page.locator("[data-testid=table-tab]").bounding_box()
    third = page.locator(PARAGRAPHS).nth(2).bounding_box()
    page.mouse.move(tab["x"] + 10, tab["y"] + 8)
    page.mouse.down()
    page.mouse.move(tab["x"] + 10, third["y"] + third["height"] - 4, steps=15)
    page.mouse.up()
    page.wait_for_timeout(800)


@when("I undo")
def _undo(world):
    page = world.ann.page
    page.click('.menus .title:text-is("Edit")')
    page.click('.menus .drop [role=menuitem]:has-text("Undo")')
    page.wait_for_timeout(800)


@when("I select the text box")
def _select(world):
    select(world.ann.page)


@when("I select the text box and press Esc")
def _select_escape(world):
    select(world.ann.page)
    world.ann.page.keyboard.press("Escape")
    world.ann.page.wait_for_timeout(200)


# ------------------------------------------------------------------------------------------------ what is seen
@then("the text box hangs from the third paragraph")
def _hangs_third(world):
    page = world.ann.page
    select(page)
    eventually(lambda: _equal(hangs_from(page), paragraph_id(page, 3)))


@then("the text box hangs from the first paragraph, where it was")
def _hangs_first(world):
    page = world.ann.page
    select(page)
    eventually(lambda: _equal(hangs_from(page), paragraph_id(page, 1)))


@then("it stays where I dropped it")
def _stays(world):
    page = world.ann.page
    page.wait_for_timeout(600)  # long enough for a refusal to put it back
    top = page.locator(OBJECT).first.bounding_box()["y"]
    second = page.locator(PARAGRAPHS).nth(1).bounding_box()
    assert top > second["y"] + second["height"] - 4, (top, second)


@then("the history has one entry for the move")
def _one_move(world):
    page = world.ann.page
    eventually(lambda: _equal(moves(page), world.moves_before + 1))


@then("the history has no entry for a move")
def _no_move(world):
    _equal(moves(world.ann.page), world.moves_before)


@then("no message says it could not be done")
def _no_refusal(world):
    alerts = world.ann.page.eval_on_selector_all(
        "[role=alert]", "els => els.map(e => e.textContent.trim()).filter(Boolean)"
    )
    assert alerts == [], alerts


@then("an anchor mark is drawn at the character it hangs from, in the first paragraph")
def _mark_first(world):
    page = world.ann.page
    eventually(lambda: _equal(hangs_from(page), paragraph_id(page, 1)))
    mark = page.locator(MARK).bounding_box()
    first = page.locator(PARAGRAPHS).first.bounding_box()
    assert first["x"] <= mark["x"] <= first["x"] + first["width"], (mark, first)


@then("the anchor mark is in the third paragraph")
def _mark_third(world):
    page = world.ann.page
    eventually(lambda: _equal(hangs_from(page), paragraph_id(page, 3)))


@then(parsers.parse('a label says it will hang from "{where}"'))
def _label(world, where):
    page = world.ann.page
    label = page.locator("[data-testid=anchor-label]")
    eventually(lambda: _equal(label.count(), 1))
    assert where in label.inner_text(), label.inner_text()


@then("the anchor mark is faintly where it was")
def _was(world):
    _equal(world.ann.page.locator(".anchor-mark.was").count(), 1)


@then("no anchor mark is drawn")
def _no_mark(world):
    _equal(world.ann.page.locator(MARK).count(), 0)


@then("the table is after the third paragraph")
def _table_after(world):
    order = world.ann.order()
    eventually(lambda: _equal(world.ann.order().index("TABLE"), 3))
    assert order.count("TABLE") == 1
