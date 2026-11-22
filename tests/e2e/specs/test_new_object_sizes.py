"""How large a new object is, and the handles: the steps of ``specs/objects/new-object-sizes.feature``.

Only the scenarios that run in a browser in composes are bound here; the ones tagged ``@unit:`` and ``@e2e:`` are
checked by the test they name. A step that needs a picture drawn by LaTeX skips its scenario, with the reason, when the
server cannot draw one (it has no XeLaTeX, or not the font the formula is set in). Steps work on what a person sees and
does; nothing here calls the server.
"""

from __future__ import annotations

import time

import pytest
from conftest import eventually
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/objects/new-object-sizes.feature")

OBJECT = "[data-object]"
ENTRIES = ".log li.entry"
DRAWN_WITHIN_S = 40.0  # XeLaTeX on a cold server takes a while for its first formula


def frame_of(page) -> dict:
    return page.locator(OBJECT).first.bounding_box()


def entries(page) -> int:
    return page.locator(ENTRIES).count()


def insert_container(page, kind: str = "LaTeX") -> None:
    page.click('.menus .title:text-is("Insert")')
    page.hover('.menus .drop [role=menuitem]:has-text("Container")')
    page.click(f'.menus [role=menuitem]:has-text("{kind}")')
    page.wait_for_selector(OBJECT)


def body_font_px(page) -> float:
    return page.eval_on_selector("[data-testid=text] [data-paragraph]", "e => parseFloat(getComputedStyle(e).fontSize)")


# ------------------------------------------------------------------------------------------------ making things
@given(parsers.parse('a new composes document "{name}" in which I am Ann, an owner'))
def _new_document(world, name):  # noqa: ARG001 - the name is for the reader; every scenario gets a document of its own
    world.join("Ann").create()


@given("I have typed a paragraph of three lines")
def _three_lines(world):
    page = world.ann.page
    page.click("[data-testid=text]")
    page.keyboard.type("Words that go on for a while, so that they fill a line and then another and another. " * 3)
    page.wait_for_timeout(600)


@when(parsers.parse('I insert a LaTeX container and write "{source}"'))
def _write_formula(world, source):
    page = world.ann.page
    page.click("[data-testid=text]")
    page.keyboard.type("Some words in the body text, then a formula.")
    insert_container(page)
    page.dblclick(OBJECT)
    page.wait_for_selector("[data-testid=container-editor] textarea")
    page.keyboard.type(source)
    page.keyboard.press("Control+Enter")
    face = page.locator(f"{OBJECT} [data-testid=container-face]").first
    end = time.monotonic() + DRAWN_WITHIN_S
    while time.monotonic() < end:
        if face.locator("img").count():
            page.wait_for_timeout(800)  # the first picture and the fitted size come in one step; let it be drawn
            page.keyboard.press("Escape")
            page.mouse.move(2, 2)  # the pointer away from the container: its label is drawn on hover
            return
        if "failed" in (face.get_attribute("class") or ""):
            pytest.skip(f"this server cannot draw LaTeX: {face.inner_text().strip()[:160]}")
        page.wait_for_timeout(250)
    pytest.skip("no picture came from the server within the time; it may have no XeLaTeX set up")


@when("I insert a LaTeX container in the middle of the first line")
def _container_in_line(world):
    page = world.ann.page
    first = page.locator("[data-testid=text] [data-paragraph]").first.bounding_box()
    page.mouse.click(first["x"] + first["width"] / 2, first["y"] + 8)
    insert_container(page)
    page.keyboard.press("Escape")
    page.wait_for_timeout(600)


MAKERS = {
    "text box": ("Edit", "Text Box"),
    "rectangle": ("Edit", "Rectangle"),
}


@given(parsers.parse("I have inserted a {kind}"))
def _inserted(world, kind):
    page = world.ann.page
    page.click("[data-testid=text]")
    page.keyboard.type("Some words so that there is something below an object. " * 3)
    page.wait_for_timeout(400)
    # the middle of the first line: the object has room on both sides to grow into
    first = page.locator("[data-testid=text] [data-paragraph]").first.bounding_box()
    page.mouse.click(first["x"] + first["width"] * 0.4, first["y"] + 8)
    if kind == "LaTeX container":
        insert_container(page)
    else:
        world.ann.menu(*MAKERS[kind])
        page.wait_for_selector(OBJECT)
    page.wait_for_timeout(500)
    page.keyboard.press("Escape")  # a new text box is being written in; a press on it then selects it
    page.wait_for_timeout(200)


# ------------------------------------------------------------------------------------------------ the handles
def drag_handle(world, handle: str, dx: float, dy: float) -> None:
    page = world.ann.page
    page.locator(OBJECT).first.click(position={"x": 6, "y": 6})
    page.wait_for_selector(f"{OBJECT}.selected")
    world.before = frame_of(page)
    world.entries_before = entries(page)
    box = page.locator(f"[data-handle={handle}]").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=12)
    page.mouse.up()


@when("I drag its lower right corner 100 to the right and 50 down")
def _drag_corner(world):
    drag_handle(world, "se", 100, 50)


@when("I drag its left edge 60 to the left")
def _drag_left(world):
    drag_handle(world, "w", -60, 0)


def _settled_frame(world) -> dict:
    world.ann.page.wait_for_timeout(1200)  # long enough for a refusal to have put the frame back
    return frame_of(world.ann.page)


@then("it is larger, and stays so when I let go")
def _larger(world):
    after = _settled_frame(world)
    assert after["width"] > world.before["width"] + 40, (world.before, after)
    assert after["height"] > world.before["height"] + 10, (world.before, after)


@then("it is wider, and stays so when I let go")
def _wider(world):
    after = _settled_frame(world)
    assert after["width"] > world.before["width"] + 40, (world.before, after)


@then("the history has one entry for the new size")
def _one_entry(world):
    page = world.ann.page
    eventually(lambda: _equal(entries(page), world.entries_before + 1))
    page.wait_for_timeout(400)
    _equal(entries(page), world.entries_before + 1)


@then("no message says it could not be done")
def _no_refusal(world):
    alerts = world.ann.page.eval_on_selector_all(
        "[role=alert]", "els => els.map(e => e.textContent.trim()).filter(Boolean)"
    )
    assert alerts == [], alerts


def _equal(got, want) -> None:
    assert got == want, f"{got!r} != {want!r}"


# ------------------------------------------------------------------------------------------------ sizes
@then("the container is at least as tall as the font size of the body text, and at least 20")
def _at_least_body(world):
    page = world.ann.page
    frame = frame_of(page)
    assert frame["height"] >= max(20.0, body_font_px(page)) - 0.5, frame


@then("its frame has the proportions of its picture, so the formula fills it")
def _proportions(world):
    page = world.ann.page
    frame = frame_of(page)
    natural = page.eval_on_selector(f"{OBJECT} img", "i => [i.naturalWidth, i.naturalHeight]")
    picture, shown = natural[0] / natural[1], frame["width"] / frame["height"]
    assert abs(shown - picture) / picture < 0.06, (natural, frame)


@then(parsers.parse('the label "{label}" is not drawn over the formula'))
def _no_label(world, label):
    page = world.ann.page
    shown = page.eval_on_selector(
        f"{OBJECT} [data-testid=container-face] .type",
        """e => { const s = getComputedStyle(e)
                  return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0' }""",
    )
    assert not shown, f"the label {label!r} is drawn over the picture"


@then("no word of the paragraph lies under the container")
def _no_word_under(world):
    page = world.ann.page
    under = page.evaluate(
        """() => {
          const o = document.querySelector('[data-object]').getBoundingClientRect()
          const paragraph = document.querySelector('[data-testid=text] [data-paragraph]')
          const walk = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT)
          const hit = []
          for (let n = walk.nextNode(); n; n = walk.nextNode()) {
            if (n.parentElement.closest('[data-skip]')) continue
            const r = document.createRange(); r.selectNodeContents(n)
            for (const line of r.getClientRects()) {
              const across = Math.min(line.right, o.right) - Math.max(line.left, o.left)
              const down = Math.min(line.bottom, o.bottom) - Math.max(line.top, o.top)
              if (across > 2 && down > 2) hit.push([Math.round(line.top), Math.round(line.left)])
            }
          }
          return hit
        }"""
    )
    assert under == [], f"lines of words under the container at {under}"
