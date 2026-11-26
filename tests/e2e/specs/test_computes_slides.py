"""Slides in computes: the steps of ``claudiaoffice-log/specs/computes/slides.feature`` (E6.31).

Bound here are the rules a chart makes and takes away a slide by (step 3, D1475): a chart as a slide, "Move to Slide"
and a slide that goes with its last object. A step that is not here skips its scenario with its words (see
``conftest.py``); the rules of search are the browser script ``web/e2e/computes-slides.cjs``
(``@e2e:computes-slides.cjs``).

Steps work on what a person sees and does: the name box, the menus, the dialog, the tabs, the slide and its chart. What
a chart is called is read where a person reads it, in Name & describe…; that selects the chart, so whether anything was
selected is noted the moment the slide is shown. How high a bar is, is read off the chart drawn on the slide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pytest
from conftest import Person, World, eventually
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/computes/slides.feature")

TABS = ".foot [role=tablist] [role=tab]"
NAME_BOX = ".formulaRow input.name"
SLIDE = "[data-testid=slide]"
CHART_ON_SLIDE = f"{SLIDE} .obj.chart"
CHART_ON_SHEET = ".viewport .object[data-object]"
OBJECT_MENU = "[role=menu][aria-label='Object menu']"
FRAME_SLACK_PX = 2  # a box measured on the screen is rounded to whole pixels


@pytest.fixture
def world(suite_world: World) -> World:
    """Every scenario here runs on the server of all three apps."""
    return suite_world


@dataclass
class Scene:
    """What a scenario remembers between its steps."""

    selected_when_shown: int | None = None  # how many objects were selected when the slide was shown
    floating: dict | None = None  # where the chart floated on Sheet1, and how big it was, from the corner of the cells


@pytest.fixture
def scene() -> Scene:
    return Scene()


def quoted(words: str) -> list[str]:
    return re.findall(r'"([^"]*)"', words)


def tab_names(person: Person) -> list[str]:
    return [text.strip() for text in person.page.locator(TABS).all_inner_texts()]


def shown_tab(person: Person) -> tuple[str | None, str]:
    tab = person.page.locator(f"{TABS}[aria-selected=true]")
    return tab.get_attribute("data-kind"), tab.inner_text().strip()


def go_to(person: Person, where: str) -> None:
    """Type a cell or a range into the name box, as a person goes somewhere on the sheet shown."""
    box = person.page.locator(NAME_BOX)
    box.fill(where)
    box.press("Enter")


def tab_called(person: Person, name: str):
    return person.page.locator(TABS).filter(has_text=re.compile(rf"^\s*{re.escape(name)}\s*$"))


def pick_tab(person: Person, name: str) -> None:
    tab_called(person, name).click()


def type_cells(person: Person, cells: dict[str, str]) -> None:
    for where, words in cells.items():
        go_to(person, where)
        person.page.keyboard.type(words)
        person.page.keyboard.press("Enter")


def box_in(person: Person, selector: str, area: str) -> dict:
    """The box of ``selector`` from the top left corner of ``area``, in pixels."""
    inner = person.page.locator(selector).first.bounding_box()
    outer = person.page.locator(area).first.bounding_box()
    assert inner and outer, f"{selector} or {area} is not on the screen"
    return {"x": inner["x"] - outer["x"], "y": inner["y"] - outer["y"], "w": inner["width"], "h": inner["height"]}


def assert_close(got: dict, want: dict) -> None:
    assert all(abs(got[k] - want[k]) <= FRAME_SLACK_PX for k in want), f"{got} is not {want}"


def object_menu(person: Person, selector: str) -> None:
    person.page.locator(selector).first.click(button="right")
    person.page.wait_for_selector(OBJECT_MENU)


def menu_entries(person: Person) -> list[str]:
    """The entries of the open object menu, without the keys beside them."""
    return person.page.eval_on_selector_all(
        f"{OBJECT_MENU} [role^=menuitem] > span", "els => els.map(e => e.textContent.trim())"
    )


# ------------------------------------------------------------------------------------------------ the document
@given('a new computes document "sales" in which I am Ann, an owner')
def _new_workbook(world: World) -> None:
    world.join("Ann", app="computes").create()


@given('Sheet1 has "Region" and "Amount" in A1 and B1, and East 300, West 120 and North 70 below them')
def _sales(world: World) -> None:
    ann = world.ann
    type_cells(ann, {"A1": "Region", "B1": "Amount", "A2": "East", "B2": "300", "A3": "West", "B3": "120"})
    type_cells(ann, {"A4": "North", "B4": "70"})
    ann.page.locator(".cell", has_text=re.compile("^70$")).wait_for(timeout=5000)


@given(parsers.parse('there is a second sheet "{name}"'))
def _second_sheet(world: World, name: str) -> None:
    ann = world.ann
    ann.page.click(".foot .add")
    field = ann.page.locator(".modal input")
    field.fill(name)
    field.press("Enter")
    ann.page.locator(TABS).filter(has_text=name).wait_for(timeout=5000)
    pick_tab(ann, "Sheet1")  # a new sheet is shown as it is made; the scenario goes on from Sheet1
    ann.page.wait_for_selector("[role=grid]")


# ------------------------------------------------------------------------------------------------ Insert ▸ Chart…
def open_chart_dialog(person: Person, cells: str) -> None:
    go_to(person, cells)
    person.menu("Insert", "Chart…")
    person.page.wait_for_selector(".modal >> text=Show as")


@when("I select A1:B4 and choose Insert ▸ Chart…")
def _choose_chart(world: World) -> None:
    open_chart_dialog(world.ann, "A1:B4")


@then(parsers.parse('the dialog offers to show the chart as "{first}" or as "{second}"'))
def _shown_as(world: World, first: str, second: str) -> None:
    show_as = world.ann.page.locator(".modal fieldset", has_text="Show as")
    assert [t.strip() for t in show_as.locator("label").all_inner_texts()] == [first, second]


@then(parsers.parse('"{choice}" is chosen'))
def _chosen(world: World, choice: str) -> None:
    assert world.ann.page.get_by_role("radio", name=choice).is_checked()


@then("the name field asks for the name of the chart")
def _name_field(world: World) -> None:
    field = world.ann.page.get_by_label("Name of the chart")
    assert field.is_visible()
    eventually(lambda: _assert(re.fullmatch(r"Chart \d+", field.input_value()), "the field starts with Chart n"))


def insert_chart(person: Person, name: str, how: str) -> None:
    open_chart_dialog(person, "A1:B4")
    dialog = person.page.locator(".modal")
    choice = {"as a slide": "A slide", "as a floating object on the sheet": "A floating object on the sheet"}
    dialog.get_by_role("radio", name=choice[how]).check()
    dialog.get_by_label("Name of the chart").fill(name)
    dialog.locator("button[type=submit]").click()
    person.page.wait_for_selector(".modal >> text=Show as", state="detached")


INSERTED_AS = r'"(?P<name>[^"]+)" of A1:B4 (?P<how>as a slide|as a floating object on the sheet)'


@when(parsers.re(f"I insert a bar chart {INSERTED_AS}"))
@given(parsers.re(r'I inserted a bar chart "(?P<name>[^"]+)" of A1:B4 (?P<how>as a slide)'))
def _insert_chart(world: World, scene: Scene, name: str, how: str) -> None:
    insert_chart(world.ann, name, how)
    if how == "as a slide":
        note_shown(world.ann, scene)


@given(parsers.parse('a bar chart "{name}" of A1:B4 floats on Sheet1'))
def _floats(world: World, scene: Scene, name: str) -> None:
    ann = world.ann
    insert_chart(ann, name, "as a floating object on the sheet")
    ann.page.wait_for_selector(f"{CHART_ON_SHEET} .js-plotly-plot")
    scene.floating = box_in(ann, CHART_ON_SHEET, ".viewport")


# ------------------------------------------------------------------------------------------------ Move to Slide
@when("I open the object menu of the chart")
def _open_menu(world: World) -> None:
    object_menu(world.ann, CHART_ON_SHEET)


@then(parsers.parse("it offers {entries}"))
def _offers(world: World, entries: str) -> None:
    assert menu_entries(world.ann) == quoted(entries)


@when(parsers.parse('I choose "{entry}" in the object menu of the chart'))
def _choose_in_menu(world: World, scene: Scene, entry: str) -> None:
    ann = world.ann
    object_menu(ann, CHART_ON_SHEET)
    ann.page.locator(f"{OBJECT_MENU} [role=menuitem]", has_text=entry).click()
    if entry == "Move to Slide":
        note_shown(ann, scene)


@then("Sheet1 has no chart")
def _no_chart_on_sheet1(world: World) -> None:
    ann = world.ann
    pick_tab(ann, "Sheet1")
    ann.page.wait_for_selector("[role=grid]")
    assert ann.page.locator(CHART_ON_SHEET).count() == 0


@then("the chart floats on Sheet1 at the place and in the size it had")
def _floats_again(world: World, scene: Scene) -> None:
    ann = world.ann
    assert scene.floating is not None
    eventually(lambda: _assert(shown_tab(ann) == ("sheet", "Sheet1"), "Sheet1 is shown"))
    ann.page.wait_for_selector(f"{CHART_ON_SHEET} .js-plotly-plot")
    assert_close(box_in(ann, CHART_ON_SHEET, ".viewport"), scene.floating)


# ------------------------------------------------------------------------------------------------ the slide
def note_shown(person: Person, scene: Scene) -> None:
    """Wait for a slide to be shown with its chart, and note what was selected on it at that moment."""
    person.page.wait_for_selector(CHART_ON_SLIDE)
    scene.selected_when_shown = person.page.locator(f"{SLIDE} .obj.selected").count()


@then(parsers.parse("the tabs read {names}"))
def _tabs_read(world: World, names: str) -> None:
    eventually(lambda: _assert_equal(tab_names(world.ann), quoted(names)))


@then(parsers.parse('the tab "{name}" is marked as a slide'))
def _marked(world: World, name: str) -> None:
    tab = tab_called(world.ann, name)
    assert tab.get_attribute("data-kind") == "slide"
    assert tab.get_attribute("aria-label") == f"Slide: {name}"


@then(parsers.parse('the slide "{name}" is shown, and the chart fills its frame'))
def _slide_shown(world: World, name: str) -> None:
    ann = world.ann
    eventually(lambda: _assert_equal(shown_tab(ann), ("slide", name)))
    ann.page.wait_for_selector(f"{CHART_ON_SLIDE} .js-plotly-plot")
    slide = ann.page.locator(SLIDE).bounding_box()
    assert slide is not None
    assert_close(box_in(ann, CHART_ON_SLIDE, SLIDE), {"x": 0, "y": 0, "w": slide["width"], "h": slide["height"]})


@then(parsers.re(r'the chart on it is (?:still )?called "(?P<name>[^"]+)"'))
def _called(world: World, name: str) -> None:
    ann = world.ann
    object_menu(ann, CHART_ON_SLIDE)
    ann.page.locator(f"{OBJECT_MENU} [role=menuitem]", has_text="Name & Describe…").click()
    field = ann.page.locator(".modal").get_by_label("Name (what a tag in the chat points at)")
    assert field.input_value() == name
    ann.page.keyboard.press("Escape")
    ann.page.wait_for_selector(".modal", state="detached")


@then("nothing is selected")
def _nothing_selected(scene: Scene) -> None:
    assert scene.selected_when_shown == 0


@then("instead of the formula bar there are the tools Text, Image, Circle, Rectangle and Triangle")
def _tools(world: World) -> None:
    page = world.ann.page
    assert page.locator(".formulaRow").count() == 0
    tools = page.eval_on_selector_all("button.tool", "els => els.map(e => e.getAttribute('aria-label'))")
    assert tools == ["text box", "image", "Circle", "Rectangle", "Triangle"], tools


@then("there are no speaker notes and there is no Present")
def _no_notes(world: World) -> None:
    page = world.ann.page
    assert page.locator("[data-testid=notes]").count() == 0
    assert page.locator("[data-tool=present]").count() == 0


@then(parsers.parse('the slide "{name}" shows the chart'))
def _shows_chart(world: World, name: str) -> None:
    ann = world.ann
    if shown_tab(ann) != ("slide", name):
        pick_tab(ann, name)
    ann.page.wait_for_selector(f"{CHART_ON_SLIDE} .js-plotly-plot")


def drag(person: Person, selector: str, dx: float, dy: float) -> None:
    box = person.page.locator(selector).first.bounding_box()
    assert box is not None, f"{selector} is not on the screen"
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    person.page.mouse.move(x, y)
    person.page.mouse.down()
    person.page.mouse.move(x + dx, y + dy, steps=8)
    person.page.mouse.up()


@when("I make the chart half as wide")
def _half_as_wide(world: World) -> None:
    ann = world.ann
    chart = ann.page.locator(CHART_ON_SLIDE)
    chart.click()
    ann.page.wait_for_selector(f"{CHART_ON_SLIDE}.selected")
    width = chart.bounding_box()["width"]
    drag(ann, f"{SLIDE} [data-handle=e]", -width / 2, 0)
    eventually(lambda: _assert(abs(chart.bounding_box()["width"] - width / 2) <= FRAME_SLACK_PX, "half as wide"))


@when(parsers.parse('I add a text box saying "{words}" beside it with the tool Text'))
def _text_beside(world: World, words: str) -> None:
    page = world.ann.page
    page.click("[data-tool=text]")
    box = page.locator(f"{SLIDE} .obj.text")
    box.wait_for(timeout=5000)
    box.dblclick()
    page.wait_for_selector("[data-testid=paragraph-editor]")
    page.keyboard.type(words)
    page.keyboard.press("Enter")
    eventually(lambda: _assert(words in box.inner_text(), "the words are in the text box"))
    # the tool puts it near the top left corner, over the chart: it is dragged into the half the chart left free
    chart = page.locator(CHART_ON_SLIDE).bounding_box()
    drag(world.ann, f"{SLIDE} .obj.text", chart["width"], 0)
    beside = chart["x"] + chart["width"]
    eventually(lambda: _assert(box.bounding_box()["x"] >= beside, "the text box is beside the chart"))


@when("I load the page again")
def _load_again(world: World) -> None:
    world.ann.reopen()


@then(parsers.parse('the slide "{name}" shows the chart and the text box "{words}"'))
def _chart_and_words(world: World, name: str, words: str) -> None:
    _shows_chart(world, name)
    assert words in world.ann.page.locator(f"{SLIDE} .obj.text").inner_text()


@when("I delete the chart")
def _delete(world: World) -> None:
    ann = world.ann
    ann.page.locator(CHART_ON_SLIDE).click()
    ann.page.wait_for_selector(f"{CHART_ON_SLIDE}.selected")
    ann.page.keyboard.press("Delete")


@then("Sheet1 is shown")
def _sheet1_shown(world: World) -> None:
    ann = world.ann
    eventually(lambda: _assert_equal(shown_tab(ann), ("sheet", "Sheet1")))
    ann.page.wait_for_selector("[role=grid]")


# ------------------------------------------------------------------------------------------------ undo, history, cells
@when("I undo")
def _undo(world: World) -> None:
    world.ann.page.keyboard.press("Escape")  # nothing selected: undo is the document's
    world.ann.menu("Edit", "Undo")


@then("the history shows one entry for the chart")
def _one_entry(world: World) -> None:
    # an entry reads who, what and when; undo has an entry of its own ("undo · Insert chart")
    said = [entry.splitlines()[1].strip() for entry in world.ann.page.locator("ol.log > li.entry").all_inner_texts()]
    assert said.count("Insert chart") == 1, said


@when(parsers.parse("I change {cell} on Sheet1 to {value}"))
def _change(world: World, cell: str, value: str) -> None:
    ann = world.ann
    pick_tab(ann, "Sheet1")
    ann.page.wait_for_selector("[role=grid]")
    type_cells(ann, {cell: value})


@then(parsers.parse('the bar of East on the slide "{name}" is {height:d} high'))
def _bar(world: World, name: str, height: int) -> None:
    ann = world.ann
    pick_tab(ann, name)
    plot = f"{CHART_ON_SLIDE} .js-plotly-plot"
    ann.page.wait_for_selector(plot)

    def east() -> None:
        drawn = ann.page.eval_on_selector(plot, "el => [el.data[0].x[0], el.data[0].y[0]]")
        assert drawn == ["East", height], drawn

    eventually(east)


def _assert(ok: object, what: str) -> None:
    assert ok, what


def _assert_equal(got: object, want: object) -> None:
    assert got == want, f"{got!r} is not {want!r}"
