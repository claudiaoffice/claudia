"""The caret at the edges of a composes text: the steps of ``claudiaoffice-log/specs/composes/caret.feature``.

Steps work on what a person sees and does: keys, the words of the paragraphs and where the caret is.
"""

from __future__ import annotations

from conftest import eventually
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/composes/caret.feature")


def _equal(got, want) -> None:
    assert got == want, f"expected {want!r}, the page shows {got!r}"


def saved(page) -> None:
    """Wait until what was typed is in the document: no unsent words are drawn over the text."""
    page.wait_for_selector("[data-testid=text] [data-overlay]", state="detached")
    page.wait_for_timeout(300)


@given(parsers.parse('a new composes document "{name}" in which I am Ann, an owner'))
def _new_document(world, name):  # noqa: ARG001 - every scenario gets a document of its own
    world.join("Ann").create()


@given(parsers.parse('I have written "{text}" and it is saved'))
def _written_saved(world, text):
    page = world.ann.page
    page.click("[data-testid=text]")
    page.keyboard.type(text)
    saved(page)


@given(parsers.parse('I have written "{text}"'))
def _written(world, text):
    page = world.ann.page
    page.click("[data-testid=text]")
    page.keyboard.type(text)


@given(parsers.parse('I have written "{first}" and "{second}" in two paragraphs and it is saved'))
def _two(world, first, second):
    page = world.ann.page
    page.click("[data-testid=text]")
    page.keyboard.type(first)
    page.keyboard.press("Enter")
    page.keyboard.type(second)
    saved(page)


def put_caret(world, text: str, key: str, offset: int) -> None:
    page = world.ann.page
    page.click(f'[data-testid=text] [data-paragraph]:has-text("{text}")')
    page.keyboard.press(key)
    # the page has taken the caret where it was put before the next key (a person is not faster than that)
    eventually(lambda: _equal(world.ann.caret(), (text, offset)))
    page.wait_for_timeout(200)


@given(parsers.parse('my caret is at the start of "{text}"'))
def _at_start(world, text):
    put_caret(world, text, "Home", 0)


@given(parsers.parse('my caret is at the end of "{text}"'))
def _at_end(world, text):
    put_caret(world, text, "End", len(text))


@when("I press Home and the up arrow at once")
def _home_up(world):
    # before the word is sent: it is sent after 700 ms without a key (IDLE_FLUSH_MS), and drawn over the text till then
    world.ann.page.wait_for_selector("[data-testid=text] [data-overlay]")
    world.ann.page.keyboard.press("Home")
    world.ann.page.keyboard.press("ArrowUp")


@when("I press the up arrow")
def _up(world):
    world.ann.page.keyboard.press("ArrowUp")


@when("I press the down arrow")
def _down(world):
    world.ann.page.keyboard.press("ArrowDown")


@when("I press Shift and the up arrow")
def _shift_up(world):
    world.ann.page.keyboard.press("Shift+ArrowUp")


@when(parsers.parse('I type "{text}"'))
def _type(world, text):
    world.ann.page.keyboard.type(text)


@then(parsers.parse('the caret is at the start of "{text}"'))
def _caret_start(world, text):
    eventually(lambda: _equal(world.ann.caret(), (text, 0)))


@then(parsers.parse('the caret is at the end of "{text}"'))
def _caret_end(world, text):
    eventually(lambda: _equal(world.ann.caret(), (text, len(text))))


@then(parsers.parse('the caret is in "{text}"'))
def _caret_in(world, text):
    eventually(lambda: _equal((world.ann.caret() or ("", 0))[0], text))


@then(parsers.parse('the text reads "{text}"'))
def _reads(world, text):
    eventually(lambda: _equal(world.ann.paragraphs(), [text]))
    saved(world.ann.page)
    _equal(world.ann.paragraphs(), [text])


@then(parsers.parse('"{text}" is selected'))
def _selected(world, text):
    eventually(lambda: _equal(world.ann.page.evaluate("getSelection().toString()"), text))
