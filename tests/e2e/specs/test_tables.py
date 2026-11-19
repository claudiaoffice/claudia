"""Tables in a composes text: the steps of ``claudiaoffice-log/specs/composes/tables.feature``.

A step that is not here skips its scenario with its words (see ``conftest.py``), so what is bound below is exactly
what is automated. Steps work on what a person sees and does: menu entries, keys, the boxes' words and where the caret
is. Nothing here calls the server or reads the app's state.
"""

from __future__ import annotations

import re
import time

from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/composes/tables.feature")

SETTLE_MS = 500  # long enough for a late echo from the server (a word that comes twice) to have shown itself
TABLE = "[data-testid=table]"


def quoted(words: str) -> list[str]:
    """``"Roof 1", "Kale", "12"`` as a list."""
    return re.findall(r'"([^"]*)"', words)


class Shape:
    """What a scenario knows of the table it made: columns, rows, how many of the rows are the header, and the words
    typed into boxes since (for the history)."""

    def __init__(self, cols: int, rows: int, header: int):
        self.cols, self.rows, self.header = cols, rows, header
        self.typed: list[str] = []


def entries_with(person, word: str) -> int:
    """How many entries of the history panel speak of ``word`` being typed."""
    return person.page.locator(".log li.entry .what", has_text=f"“{word}”").count()


def settle(person) -> None:
    person.page.wait_for_timeout(SETTLE_MS)


def eventually(check, seconds: float = 5.0) -> None:
    """Run ``check`` (it asserts) until it holds, for at most ``seconds``; the last failure is the answer."""
    end = time.monotonic() + seconds
    while True:
        try:
            check()
            return
        except AssertionError:
            if time.monotonic() > end:
                raise
            time.sleep(0.1)


@given('a new composes document "report" in which I am Ann, an owner')
def _new_document(world):
    world.join("Ann").create()


@given('the text has the paragraphs "Before" and "After"')
def _paragraphs(world):
    ann = world.ann
    ann.page.click("[data-testid=text]")
    ann.page.keyboard.type("Before")
    ann.page.keyboard.press("Enter")
    ann.page.keyboard.type("After")
    eventually(lambda: _assert_equal(ann.paragraphs(), ["Before", "After"]))


@given('my caret is at the end of "Before"')
def _caret_before(world):
    # no pause on purpose: a person's next key can come before the page has told the app where the caret went (B2)
    world.ann.page.click('[data-testid=text] [data-block]:has-text("Before")')
    world.ann.page.keyboard.press("End")


# ------------------------------------------------------------------------------------------------ the dialog
def open_dialog(ann) -> None:
    ann.menu("Insert", "Table…")
    ann.page.wait_for_selector("[data-testid=table-dialog]")


def fill_dialog(ann, cols: int, rows: int, header: bool) -> Shape:
    page = ann.page
    page.fill("[data-testid=table-cols]", str(cols))
    page.fill("[data-testid=table-rows]", str(rows))
    page.set_checked("[data-testid=table-header]", header)
    page.click("[data-testid=table-insert]")
    page.wait_for_selector(TABLE)
    return Shape(cols, rows, 1 if header else 0)


@when("I choose Insert ▸ Table…")
def _choose_insert_table(world):
    open_dialog(world.ann)


@then("a dialog asks for the number of columns and rows and whether the first row is the header")
def _dialog_asks(world):
    page = world.ann.page
    for field in ("table-cols", "table-rows", "table-header"):
        assert page.is_visible(f"[data-testid={field}]"), f"the dialog has no {field}"


@when("I close it with Esc")
def _close_dialog(world):
    world.ann.page.keyboard.press("Escape")
    world.ann.page.wait_for_selector("[data-testid=table-dialog]", state="detached")


@when("I press Ctrl+Shift+F")
def _press_insert_key(world):
    world.ann.page.keyboard.press("Control+Shift+F")


@then("the same dialog is open, with the focus in the first field")
def _same_dialog(world):
    page = world.ann.page
    page.wait_for_selector("[data-testid=table-dialog]")
    assert page.evaluate("document.activeElement.getAttribute('data-testid')") == "table-cols"


@when(
    parsers.re(r"I insert a table of (?P<cols>\d+) columns? and (?P<rows>\d+) rows? (?P<header>with|without) a header"),
    target_fixture="shape",
)
@given(
    parsers.re(
        r"I have inserted a table of (?P<cols>\d+) columns? and (?P<rows>\d+) rows? (?P<header>with|without) a header"
    ),
    target_fixture="shape",
)
def _insert_table(world, cols, rows, header):
    open_dialog(world.ann)
    return fill_dialog(world.ann, int(cols), int(rows), header == "with")


@when(
    parsers.re(
        r"I press Ctrl\+Shift\+F and insert a table of (?P<cols>\d+) columns and (?P<rows>\d+) rows"
        r" with a header at once"
    ),
    target_fixture="shape",
)
def _insert_at_once(world, cols, rows):
    ann = world.ann
    ann.page.keyboard.press("Control+Shift+F")
    ann.page.wait_for_selector("[data-testid=table-dialog]")
    return fill_dialog(ann, int(cols), int(rows), True)


# ------------------------------------------------------------------------------------------------ what was made
@then('the table is between "Before" and "After"')
def _between(world):
    eventually(lambda: _assert_equal(world.ann.order(), ["Before", "TABLE", "After"]))
    settle(world.ann)
    _assert_equal(world.ann.order(), ["Before", "TABLE", "After"])  # and still, once, a moment later


def _assert_equal(got, want) -> None:
    assert got == want, f"expected {want!r}, the page shows {got!r}"


@then(parsers.parse("the table has {cols:d} columns"))
def _columns(world, cols):
    first = world.ann.page.locator(f"{TABLE} tr").first
    assert first.locator("textarea").count() == cols


@then(parsers.parse("the table has a header row, in the header look, and {body:d} body rows"))
def _header_and_body(world, body):
    page = world.ann.page
    assert page.locator(f"{TABLE} thead tr").count() == 1, "no header row"
    assert page.locator(f"{TABLE} tbody tr").count() == body


@then("all boxes are empty")
def _all_empty(world):
    assert set(world.ann.boxes()) == {""}


@then(
    parsers.parse(
        "I can see where every box is, also while it is empty, and all {count:d} boxes are inside the text area"
    )
)
def _boxes_visible(world, count):
    page = world.ann.page
    area = page.locator("[data-testid=text]").bounding_box()
    boxes = page.locator("[data-box]")
    assert boxes.count() == count
    for i in range(count):
        rect = boxes.nth(i).bounding_box()
        assert rect and rect["width"] > 8 and rect["height"] > 8, f"box {i} has no size: {rect}"
        assert rect["x"] >= area["x"] - 1 and rect["x"] + rect["width"] <= area["x"] + area["width"] + 1, (
            f"box {i} sticks out"
        )


@then("the caret is in the first box of the header row")
def _caret_first_header(world):
    eventually(lambda: _assert_equal(world.ann.focused_box(), "r1/c1"))


@then(parsers.parse('the table has a name such as "{name}"'))
def _table_name(world, name):
    assert name in world.ann.page.inner_text(f"{TABLE} [data-testid=table-tab]")


# ------------------------------------------------------------------------------------------------ the keyboard
def box(shape: Shape, row_of_body: int, col: int) -> str:
    """The ``data-box`` of body row ``row_of_body`` (1 = the first body row) and column ``col`` (1-based)."""
    return f'[data-box="r{shape.header + row_of_body}/c{col}"]'


def body_row(world, shape: Shape, n: int) -> list[str]:
    start = (shape.header + n - 1) * shape.cols
    return world.ann.boxes()[start : start + shape.cols]


@given(parsers.re(r"I have typed the header (?P<words>.+)"))
def _typed_header(world, shape, words):
    page = world.ann.page
    for word in quoted(words):
        page.keyboard.type(word)
        page.keyboard.press("Tab")
    settle(world.ann)


@when(parsers.parse('I type "{text}" in the first body box and press {key}'))
def _type_in_first_and_key(world, shape, text, key):
    page = world.ann.page
    page.click(box(shape, 1, 1))
    shape.typed.append(text)
    page.keyboard.type(text)
    page.keyboard.press(key)


@when(parsers.parse('I type "{text}" in the first body box'))
def _type_in_first(world, shape, text):
    page = world.ann.page
    page.click(box(shape, 1, 1))
    shape.typed.append(text)
    page.keyboard.type(text)


@when(parsers.parse('I type "{text}" and press {key}'))
def _type_and_key(world, shape, text, key):
    shape.typed.append(text)
    world.ann.page.keyboard.type(text)
    world.ann.page.keyboard.press(key)


@when(parsers.re(r"I type (?P<words>.+) into the first body row as fast as the keyboard allows, a Tab after each"))
def _type_fast(world, shape, words):
    page = world.ann.page
    page.click(box(shape, 1, 1))
    for word in quoted(words):
        page.keyboard.type(word)
        page.keyboard.press("Tab")


@when("I press Shift+Tab")
def _shift_tab(world):
    world.ann.page.keyboard.press("Shift+Tab")


@when("I press Tab")
def _tab(world):
    world.ann.page.keyboard.press("Tab")


@when(parsers.parse('I click into the paragraph "{text}"'))
def _click_paragraph(world, text):
    world.ann.page.click(f'[data-testid=text] [data-block]:has-text("{text}")')


@given("the caret is in the first box of the second body row")
def _given_second_row(world, shape):
    world.ann.page.click(box(shape, 2, 1))


@given("the caret is in the last box of the last row")
def _given_last_box(world, shape):
    world.ann.page.click(f'[data-box="r{shape.rows}/c{shape.cols}"]')
    shape.rows_before = shape.rows


@then("the caret is in the first box of the second body row")
def _caret_second_row(world, shape):
    eventually(lambda: _assert_equal(world.ann.focused_box(), f"r{shape.header + 2}/c1"))


@then("the caret is in the last box of the first body row")
def _caret_last_of_first(world, shape):
    eventually(lambda: _assert_equal(world.ann.focused_box(), f"r{shape.header + 1}/c{shape.cols}"))


@then(parsers.re(r"the first body row reads exactly (?P<words>.+), each once"))
def _first_row_reads(world, shape, words):
    want = quoted(words)
    eventually(lambda: _assert_equal(body_row(world, shape, 1)[: len(want)], want))
    settle(world.ann)
    _assert_equal(body_row(world, shape, 1)[: len(want)], want)


@then(parsers.parse('the first body box reads exactly "{text}", once'))
def _first_box_reads(world, shape, text):
    eventually(lambda: _assert_equal(body_row(world, shape, 1)[0], text))
    settle(world.ann)
    _assert_equal(body_row(world, shape, 1)[0], text)


@then("the box did not get a second line")
def _no_second_line(world, shape):
    assert "\n" not in body_row(world, shape, 1)[0]


@then("the table has one more body row, at the end")
def _one_more_row(world, shape):
    page = world.ann.page
    eventually(lambda: _assert_equal(page.locator(f"{TABLE} tbody tr").count(), shape.rows - shape.header + 1))
    shape.rows += 1


@then("the caret is in the first box of that row")
def _caret_new_row(world, shape):
    eventually(lambda: _assert_equal(world.ann.focused_box(), f"r{shape.rows}/c1"))


# ------------------------------------------------------------------------------------------------ N2: rows and columns
@given(parsers.re(r"the body is filled with (?P<rows>.+)"))
def _fill_body(world, shape, rows):
    page = world.ann.page
    page.click(box(shape, 1, 1))
    lines = [quoted(line) for line in rows.split(" / ")]
    words = [w for line in lines for w in line]
    for i, word in enumerate(words):
        page.keyboard.type(word)
        if i < len(words) - 1:
            page.keyboard.press("Tab")  # the last Tab of the last box would add a row
    settle(world.ann)
    shape.rows = shape.header + len(lines)  # Tab in the last box added the rows that were missing


@given(parsers.parse('my caret is in the box "{text}"'))
def _caret_in_box(world, text):
    world.ann.page.locator("[data-box]").filter(has_text=re.compile(f"^{re.escape(text)}$")).first.click()


def _first_column_of_body(world, shape: Shape) -> list[str]:
    values = world.ann.boxes()
    return [values[(shape.header + n) * shape.cols] for n in range(len(values) // shape.cols - shape.header)]


@when("I add a row above")
def _row_above(world):
    world.ann.page.keyboard.press("Shift+Alt+ArrowUp")


@when("I add a row below")
def _row_below(world):
    world.ann.page.keyboard.press("Shift+Alt+ArrowDown")


@when("I add a column to the right")
def _column_right(world):
    world.ann.page.keyboard.press("Shift+Alt+ArrowRight")


@when("I delete the row")
def _delete_row(world):
    world.ann.page.keyboard.press("Control+Alt+-")


@when("I delete the column")
def _delete_column(world):
    world.ann.page.keyboard.press("Control+Alt+_")


@then(parsers.re(r"the body reads, from the top: (?P<words>.+)"))
def _body_reads(world, shape, words):
    found = re.findall(r'"([^"]*)"|(an empty row)', words)
    want = ["" if empty else text for text, empty in found]
    eventually(lambda: _assert_equal(_first_column_of_body(world, shape), want))


@then(parsers.parse('my caret is still in the box "{text}"'))
def _caret_still(world, text):
    eventually(lambda: _assert_equal(world.ann.page.evaluate("document.activeElement.value"), text))


@then(parsers.parse('the table has 4 columns, the new one after "Crop", with an empty header and empty boxes'))
def _four_columns(world, shape):
    page = world.ann.page
    eventually(lambda: _assert_equal(page.locator(f"{TABLE} tr").first.locator("textarea").count(), 4))
    _assert_equal(world.ann.boxes()[:4], ["Bed", "Crop", "", "Kilos"])


# ------------------------------------------------------------------------------------------------ the history
@then("the history shows one entry for each of the three boxes")
def _history_three(world, shape):
    settle(world.ann)
    for word in shape.typed:
        assert entries_with(world.ann, word) == 1, (
            f"the history has {entries_with(world.ann, word)} entries for {word!r}"
        )


@then("the history shows one entry for it")
def _history_one(world, shape):
    settle(world.ann)
    for word in shape.typed:
        assert entries_with(world.ann, word) == 1, (
            f"the history has {entries_with(world.ann, word)} entries for {word!r}"
        )
