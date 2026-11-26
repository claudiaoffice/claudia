"""Menus that show what fits: the steps of ``claudiaoffice-log/specs/menus/menus-that-fit.feature`` (E5.23, E5.24).

A step that is not here skips its scenario with its words (see ``conftest.py``): what is bound below is what the menus,
the context menus and the keys do today (slices 4 and 5 of the menu work); the copy guard, Paste As ▸ Plain Text and
the Shortcuts dialog's switch come with their slices. Steps work on what a person sees and does: the menu bar, a right
press, a key and the notice that is said. Nothing here calls the server or reads the app's state.
"""

from __future__ import annotations

import re

import pytest
from conftest import Person, World, eventually
from pytest_bdd import given, parsers, scenarios, then, when
from test_names import make_heading, type_paragraphs

scenarios("../../../claudiaoffice-log/specs/menus/menus-that-fit.feature")

TITLES = ["File", "Edit", "Insert", "Format", "View", "Tools", "Preferences", "Help"]
CONTEXT_MENU = "[role=menu]:not(.menus [role=menu])"
NAME_BOX = ".formulaRow input.name"
WHAT = {"text": "composes", "document": "composes", "sheet": "computes", "presentation": "creates"}
ROLES = {"the owner": "owner", "an editor": "editor", "a viewer": "viewer"}


@pytest.fixture
def world(suite_world: World) -> World:
    """Every scenario here runs on the server of all three apps."""
    return suite_world


def me(world: World) -> Person:
    """The person the scenario speaks as ("I"): the owner, or the one the owner let in."""
    return world.people.get("Ben") or world.ann


def as_role(world: World, role: str, what: str, prepare=None) -> Person:
    """A new document of the app ``what`` names, with me in it as ``role``. ``prepare`` is what the owner does first."""
    ann = world.join("Ann", WHAT[what])
    ann.create()
    if prepare:
        prepare(ann)
    if role == "owner":
        return ann
    ben = world.join("Ben")
    ann.share(ben, role)
    ben.open()
    ben.wait_until_open()
    return ben


# ------------------------------------------------------------------------------------------------ the menu bar
def open_menu(person: Person, title: str) -> None:
    if person.page.locator(".menus .drop").count():  # one open already: closed first, as Esc does
        person.page.keyboard.press("Escape")
    person.page.click(f'.menus .title:text-is("{title}")')
    person.page.wait_for_selector(".menus .drop")


# A menu's lines: `—` for a separator, `(off)` after a greyed entry; `{words}` is where an entry keeps its words
LINES = """els => els.map(li => li.classList.contains('sep') ? '—'
  : li.querySelector('{words}').textContent.trim() + (li.querySelector('button').disabled ? ' (off)' : ''))"""


def shown(person: Person) -> list[str]:
    """The open menu of the bar, a line each."""
    return person.page.eval_on_selector_all(".menus .drop:not(.sub) > li", LINES.replace("{words}", ".label"))


def labels(person: Person, title: str) -> list[str]:
    open_menu(person, title)
    try:
        return [line.removesuffix(" (off)") for line in shown(person) if line != "—"]
    finally:
        person.page.keyboard.press("Escape")


@given(parsers.re(r"I am (?P<role>the owner|an editor|a viewer) of a (?P<what>document|text|sheet|presentation)$"))
def _role_of(world, role, what):
    as_role(world, ROLES[role], what)


@given("I am a viewer of a sheet with nothing selected")
def _viewer_of_a_sheet(world):
    as_role(world, "viewer", "sheet")


@given("I am the owner of a new text")
@given("I am the owner of a new text with nothing selected")
def _owner_of_a_new_text(world):
    as_role(world, "owner", "text")


@given("I am the owner of a text")
def _owner_of_a_text(world):
    ann = as_role(world, "owner", "text")
    ann.page.click("[data-testid=text]")
    ann.page.keyboard.type("Plans for the spring")
    eventually(lambda: _assert(ann.paragraphs() == ["Plans for the spring"], ann.paragraphs()))


@given("I am the owner of a text on a server without a real ai")
def _owner_without_ai(world):
    as_role(world, "owner", "text")  # the servers of the tests answer with the stand-in (D1615)


@then("the menu bar shows File, Edit, Insert, Format, View, Tools, Preferences and Help")
def _titles(world):
    titles = me(world).page.locator(".menus .title").all_inner_texts()
    assert [title.strip() for title in titles] == TITLES


@when(parsers.parse("I open the {title} menu"))
def _open(world, title):
    open_menu(me(world), title)


@when(parsers.parse("I open the Insert menu and press {key}"))
def _open_insert_and_press(world, key):
    open_menu(me(world), "Insert")
    me(world).page.keyboard.press(key.replace("Ctrl", "Control"))


@then(parsers.parse('it holds only the greyed line "{line}"'))
def _only_line(world, line):
    assert shown(me(world)) == [f"{line} (off)"]


@then(parsers.parse("it shows neither {entries}"))
def _shows_neither(world, entries):
    names = re.split(r", | nor ", entries)
    lines = [line.removesuffix(" (off)") for line in shown(me(world))]
    assert not set(names) & set(lines), lines


@when("I select a word and open the Edit menu again")
def _select_a_word(world):
    person = me(world)
    person.page.keyboard.press("Escape")  # the Edit menu, open from the step before
    person.page.click("[data-testid=text]")
    person.page.keyboard.type("Spring")
    person.page.keyboard.press("Shift+Home")  # at once: the word is not sent yet (UX-100)
    person.page.wait_for_timeout(300)  # a person's next press comes after the page has seen the selection
    open_menu(person, "Edit")


@then(parsers.re(r"it shows (?!neither |all its )(?P<entries>.+)$"))
def _shows(world, entries):
    names = re.split(r", | and ", entries)
    lines = [line.removesuffix(" (off)") for line in shown(me(world))]
    assert set(names) <= set(lines), lines


@then("it shows all its entries, greyed")
def _all_greyed(world):
    lines = [line for line in shown(me(world)) if line != "—"]
    assert lines and all(line.endswith(" (off)") for line in lines), lines
    assert not any(line.startswith("Nothing to") for line in lines), lines


@then("the Edit menu shows no Undo")
def _no_undo(world):
    assert not any(label.startswith("Undo") for label in labels(me(world), "Edit"))


@when("I type a word")
def _type_a_word(world):
    person = me(world)
    person.page.click("[data-testid=text]")
    person.page.keyboard.type("Spring ")
    person.page.locator(".health.open").wait_for(state="attached")


@then("the Edit menu shows Undo")
def _undo(world):
    eventually(lambda: _assert(any(label.startswith("Undo") for label in labels(me(world), "Edit")), "no Undo"))


@then("the Edit menu shows Undo, greyed")
def _undo_greyed(world):
    open_menu(me(world), "Edit")
    assert "Undo (off)" in shown(me(world))


@then("in every menu and submenu no separator comes first, last or right after another")
def _no_stray_lines(world):
    person = me(world)
    for title in TITLES:
        open_menu(person, title)
        lines = shown(person)
        _assert_lines(lines, title)
        for submenu in person.page.locator(".menus .drop:not(.sub) > li button[aria-haspopup=menu]").all():
            submenu.hover()
            sub = person.page.eval_on_selector_all(".menus .drop.sub > li", LINES.replace("{words}", ".label"))
            _assert_lines(sub, f"{title} ▸ {submenu.inner_text().strip()}")
        person.page.keyboard.press("Escape")


def _assert_lines(lines: list[str], where: str) -> None:
    assert lines, f"{where} is empty"
    assert lines[0] != "—" and lines[-1] != "—", f"{where}: {lines}"
    assert all(not (a == b == "—") for a, b in zip(lines, lines[1:], strict=False)), f"{where}: {lines}"


@then("the File menu offers Download, Export… and Print…")
def _file_offers(world):
    person = me(world)
    open_menu(person, "File")
    lines = shown(person)
    assert {"Download", "Print…"} <= set(lines), lines
    person.menu_item("Manage").hover()
    sub = person.page.locator(".menus .drop.sub [role=menuitem]").all_inner_texts()
    assert any(line.startswith("Export…") for line in sub), sub


# ------------------------------------------------------------------------------------------------ context menus
def context_lines(person: Person) -> list[str]:
    person.page.wait_for_selector(CONTEXT_MENU)
    return person.page.eval_on_selector_all(f"{CONTEXT_MENU} > li", LINES.replace("{words}", "button > span"))


@given("I am a viewer of a presentation with a text box")
def _viewer_with_a_text_box(world):
    def text_box(ann: Person) -> None:
        ann.menu("Insert", "Text Box")
        ann.page.wait_for_selector("[data-testid=slide] .obj.text")

    as_role(world, "viewer", "presentation", text_box)


@when("I press the right button on the text box")
def _right_on_text_box(world):
    me(world).page.locator("[data-testid=slide] .obj.text").first.click(button="right")


@then(parsers.parse('the menu holds only the greyed line "{line}"'))
def _context_only_line(world, line):
    assert context_lines(me(world)) == [f"{line} (off)"]


@when("I press the right button on a paragraph")
def _right_on_paragraph(world):
    me(world).page.locator("[data-testid=text] [data-paragraph]").first.click(button="right")


@then(parsers.parse("the menu shows {entries}"))
def _context_shows(world, entries):
    names = re.split(r", | and ", re.sub(r", the same as .*$", "", entries))
    lines = [line.removesuffix(" (off)").removesuffix(" ▸") for line in context_lines(me(world))]
    assert set(names) <= set(lines), lines
    if entries.endswith("the same as the slide's tab"):
        page = me(world).page
        page.keyboard.press("Escape")
        page.locator(".foot [role=tab][aria-selected=true]").click(button="right")
        assert context_lines(me(world)) == lines


@when(parsers.re(r"I choose (?P<entry>[^▸]+)$"))
def _choose_in_context(world, entry):
    me(world).page.locator(f"{CONTEXT_MENU} [role^=menuitem]", has_text=entry).first.click()


REFERENCE = "[data-testid=text] [data-atom]"


@given(parsers.parse('I am the owner of a text with a reference to its heading "{title}"'))
def _text_with_reference(world, title):
    ann = as_role(world, "owner", "text")
    type_paragraphs(ann, [title, "See "])
    make_heading(ann, 0)
    ann.page.keyboard.press("Control+End")
    ann.menu("Insert", "Cross Reference")
    picker = ann.page.locator("[data-testid=reference-picker]")
    picker.locator("input[type=search]").fill(title)
    # the heading reaches the list once the server has it (slow on CI): Enter puts in only what is chosen
    picker.locator("[role=option][aria-selected=true]", has_text=title).wait_for()
    picker.locator("input[type=search]").press("Enter")
    ann.page.wait_for_selector(REFERENCE)


@when("I press the right button on the reference")
def _right_on_reference(world):
    me(world).page.locator(REFERENCE).first.click(button="right")


def open_show_as(person: Person) -> None:
    person.page.locator(f"{CONTEXT_MENU} > li > [role^=menuitem]", has_text="Show As").click()


@when(parsers.parse("I choose Show As ▸ {way}"))
def _choose_show_as(world, way):
    person = me(world)
    open_show_as(person)
    person.page.locator(f"{CONTEXT_MENU} .sub [role^=menuitem]", has_text=re.compile(f"^✓?{re.escape(way)}$")).click()


@then(parsers.parse("Show As ▸ {way} is ticked"))
def _show_as_ticked(world, way):
    person = me(world)
    open_show_as(person)
    ticked = person.page.eval_on_selector_all(
        f"{CONTEXT_MENU} .sub [aria-checked=true]", "els => els.map(e => e.textContent.replace('✓', '').trim())"
    )
    assert ticked == [way], ticked


@then("there is no reference in the text")
def _no_reference(world):
    eventually(lambda: _assert(me(world).page.locator(REFERENCE).count() == 0, "a reference is still there"))


@then("the paragraph style popover opens for that paragraph")
def _style_popover(world):
    me(world).page.wait_for_selector("[data-testid=style-menu][data-mode=apply]")


@given("I am the owner of a sheet with a pivot table")
def _owner_with_a_pivot(world):
    ann = as_role(world, "owner", "sheet")
    page = ann.page
    rows = [["Region", "Amount"], ["East", "100"], ["West", "50"]]
    for r, row in enumerate(rows):
        for c, words in enumerate(row):
            box = page.locator(NAME_BOX)
            box.fill(f"{'AB'[c]}{r + 1}")
            box.press("Enter")
            page.keyboard.type(words)
            page.keyboard.press("Enter")
    box = page.locator(NAME_BOX)
    box.fill("A1:B3")
    box.press("Enter")
    box.fill("Sales")
    box.press("Enter")
    page.click('[data-testid=name-define] button:text-is("Define")')
    page.wait_for_selector("[data-testid=name-define]", state="detached")
    box.fill("A2")
    box.press("Enter")
    page.keyboard.press("Control+Alt+v")
    page.click('[data-testid=pivot-create] button:text-is("Create")')
    panel = page.locator("[data-testid=pivot-panel]")
    for field in ("Region", "Amount"):
        panel.locator(f'.fields li:has(.field:text-is("{field}")) input').check()
    page.wait_for_selector("[data-pivot-role=total]")
    page.keyboard.press("Escape")  # the field panel
    page.wait_for_selector("[data-testid=pivot-panel]", state="detached")


@when("I press the right button on the pivot table")
def _right_on_pivot(world):
    # the pivot table's first row of values, in the middle of the grid's cells (96 by 26 pixels after the headers)
    viewport = me(world).page.locator(".viewport")
    viewport.click(button="right", position={"x": 52 + 40, "y": 26 + 2 * 26 + 13})


@then("the Tools menu has the single entry Pivot Table…")
def _single_pivot_entry(world):
    person = me(world)
    person.page.keyboard.press("Escape")
    pivot = [label for label in labels(person, "Tools") if "Pivot" in label]
    assert pivot == ["Pivot Table…"], pivot


@given("I am the owner of a presentation")
def _owner_of_a_presentation(world):
    as_role(world, "owner", "presentation")


@when("I press the right button on the slide, away from any object")
def _right_on_slide(world):
    slide = me(world).page.locator("[data-testid=slide]")
    box = slide.bounding_box()
    assert box
    slide.click(button="right", position={"x": box["width"] - 12, "y": box["height"] - 12})


# ------------------------------------------------------------------------------------------------ keys
@when(parsers.re(r"I press (?P<key>(?:Ctrl|Shift|Alt|F\d)[\w+]*)$"))
def _press(world, key):
    person = me(world)
    person.page.locator(".menus .title").first.focus()  # a key goes to the window, not into a field
    person.page.keyboard.press(key.replace("Ctrl", "Control"))


@then(parsers.parse('I am told "{words}", not that nothing is selected'))
@then(parsers.parse('I am told "{words}"'))
def _told(world, words):
    person = me(world)
    eventually(lambda: _assert(words in person.notices(), person.notices()))


@then("no dialog opens")
def _no_dialog(world):
    me(world).page.wait_for_timeout(300)
    assert me(world).page.locator(".modal").count() == 0


# ------------------------------------------------------------------------------------------------ the trial
@given("the trial setting greys what does not fit my role")
def _grey_role(world):
    world.query = "?fits=role:grey"


@given("the trial setting always shows Undo")
def _undo_stays(world):
    world.query = "?fits-entry=edit.undo:grey"  # an entry's own setting is grey or hide (D1653)


def _assert(ok: bool, what) -> None:
    assert ok, what


# ------------------------------------------------------------------------------------ Preferences ▸ Shortcuts
SHORTCUTS = "[data-testid=shortcuts-list]"


@when("I choose Preferences ▸ Shortcuts and switch to Everything")
def _shortcuts_everything(world):
    person = me(world)
    person.menu("Preferences", "Shortcuts")
    person.page.locator("[data-testid=shortcuts-switch] [role=radio]", has_text="Everything").click()


@when("I switch to What Fits Now")
def _shortcuts_now(world):
    me(world).page.locator("[data-testid=shortcuts-switch] [role=radio]", has_text="What Fits Now").click()


def shortcut_row(person: Person, label: str):
    return person.page.locator(f"{SHORTCUTS} tr", has=person.page.locator("td.label", has_text=label))


@then(parsers.re(r'(?P<label>.+) is listed with (?P<keys>\S+), "(?P<when>[^"]+)" and the tag "(?P<tag>[^"]+)"$'))
def _listed(world, label, keys, when, tag):
    row = shortcut_row(me(world), label)
    assert row.count() == 1, f"{label} is listed {row.count()} times"
    cells = [text.strip() for text in row.locator("td").all_inner_texts()]
    assert cells[0] == keys and cells[1].endswith(label) and cells[2] == when and cells[3] == tag, cells


@then(parsers.re(r"(?P<label>.+) is not listed$"))
def _not_listed(world, label):
    assert shortcut_row(me(world), label).count() == 0
