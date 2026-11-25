"""What every object in a composes text must do: the steps of
``claudiaoffice-log/specs/invariants/objects-in-composes.feature`` (PROC-40). The scenarios are written once and run for
each kind of object in their ``Examples``; the pilot has the table only.

What is particular to a kind (how it is inserted, how a person works in it, how the history and the printed page show
it) is in one class per kind, in ``KINDS``; the steps around it are the same for every kind. A new kind is a new row of
``Examples`` and a new class here; until it has one, no step matches its words and its scenarios skip.

Everything is read where a person reads it: the objects and paragraphs on the page, the words in the boxes, where the
caret is, the history panel, the ``#`` list of the chat, the menus, the drawn print preview, the accessibility tree.

The connection is lost by pulling the cable: Ann's page talks to the server through a pass-through route of Playwright
(``Cable``), and the step closes both ends of every link it carries. The page sees a connection that went away, as on
a real network, and reconnects by itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from conftest import Person, World, eventually, steady
from playwright.sync_api import expect
from pytest_bdd import given, parsers, scenarios, then, when
from test_names import choose

scenarios("../../../claudiaoffice-log/specs/invariants/objects-in-composes.feature")

TEXT = "[data-testid=text]"
PARAGRAPHS = f"{TEXT} [data-paragraph]"
HISTORY = "ol.log > li.entry .what"
CHAT = ".write [role=combobox]"
OPTIONS = "#tag-list [role=option]"
DIALOG = ".modal"
PRINT_PAGES = "[data-testid=print-pages] .page svg"
#: The words a person types when a scenario says they worked in an object, and when they work in it again.
WORDS = ("Crop", "Kilos")
MORE_WORDS = ("Kale", "12")
FORMATS = {"OpenDocument": "odt", "Word": "docx"}


# ================================================================================================= reading the page
def _equal(got, want) -> None:
    assert got == want, f"expected {want!r}, the page shows {got!r}"


OFF = "e => e.disabled || e.getAttribute('aria-disabled') === 'true'"  # an entry shown as unavailable


def disabled(locator) -> bool:
    return locator.evaluate(OFF)


def text_and_objects(person: Person, selector: str) -> list[str]:
    """The paragraphs and the objects (``selector``) of the text in the order they are on the page: a paragraph is its
    words, without what is drawn into it for others (another person's caret and name), an object is ``OBJECT``."""
    return person.page.evaluate(
        """selector => [...document.querySelectorAll(`[data-testid=text] [data-paragraph], ${selector}`)].map(e => {
              if (e.matches(selector)) return 'OBJECT'
              const words = e.cloneNode(true)
              words.querySelectorAll('[data-skip]').forEach(s => s.remove())
              return words.textContent.trim() })""",
        selector,
    )


def paragraphs(person: Person) -> list[str]:
    return [part for part in text_and_objects(person, ":not(*)") if part != "OBJECT"]


def assert_visible(person: Person, locator) -> None:
    """It has a size and lies inside the text area (the "always" check 3 of the specs README)."""
    area = person.page.locator(TEXT).bounding_box()
    box = locator.bounding_box()
    assert box and box["width"] > 8 and box["height"] > 8, f"it has no size: {box}"
    assert area and box["x"] >= area["x"] - 1 and box["x"] + box["width"] <= area["x"] + area["width"] + 1, (
        f"it sticks out of the text area: {box} in {area}"
    )


def history(person: Person) -> list[str]:
    """What each entry of the history panel says was done, in order."""
    return person.page.eval_on_selector_all(HISTORY, "els => els.map(e => e.textContent.replace(/\\s+/g, ' ').trim())")


def hash_list(person: Person) -> list[tuple[str, str]]:
    """What the ``#`` list of the chat offers: (kind, name) of each thing."""
    page = person.page
    page.click(CHAT)
    page.keyboard.press("Control+a")
    page.keyboard.press("Backspace")
    page.keyboard.type("#")
    page.wait_for_selector(OPTIONS)
    offered = steady(
        person,
        lambda: page.eval_on_selector_all(
            OPTIONS,
            "els => els.map(e => ['.kind', '.nm'].map(part => e.querySelector(part)?.textContent.trim() ?? ''))",
        ),
    )
    page.keyboard.press("Escape")
    page.keyboard.press("Control+a")
    page.keyboard.press("Backspace")
    page.locator(CHAT).blur()  # while the caret is in the chat, a click on a thing writes a tag for it (D551)
    return [tuple(thing) for thing in offered]


def name_in_dialog(person: Person) -> str:
    """The name Name & describe… shows for what is selected or has the caret; the dialog is closed again."""
    choose(person, "Name & describe…")
    field = person.page.locator(f"{DIALOG} input[type=text]")
    field.wait_for()
    name = field.input_value()
    person.page.keyboard.press("Escape")
    person.page.wait_for_selector(DIALOG, state="detached")
    return name


@dataclass
class Printed:
    """What the print preview draws: each word with its place, each drawn line or area with its box (in points)."""

    words: list[tuple[str, float]]  # the words and the height of their line on the page, page after page
    drawn: list[tuple[float, float, float, float]]  # x, y, width and height of each, page after page

    def where(self, word: str) -> list[float]:
        return [y for words, y in self.words if words == word]

    def between(self, top: str, bottom: str) -> list[tuple[float, float, float, float]]:
        """What is drawn below the line of ``top`` and above the line of ``bottom`` (on one page, as in these tests)."""
        (upper,), (lower,) = self.where(top), self.where(bottom)
        return [item for item in self.drawn if upper < item[1] < lower]


def print_preview(person: Person) -> Printed:
    """File ▸ Print…, and what its pages show once they stopped changing."""
    person.menu("File", "Print…")
    page = person.page
    page.wait_for_selector(PRINT_PAGES, timeout=30000)
    pages = steady(
        person,
        lambda: page.eval_on_selector_all(
            PRINT_PAGES,
            """svgs => svgs.map(svg => ({
                 words: [...svg.querySelectorAll('text')].map(t => [t.textContent, t.getBBox().y + t.getBBox().height]),
                 drawn: [...svg.querySelectorAll('path')].map(p => { const b = p.getBBox()
                          return [b.x, b.y, b.width, b.height] }) }))""",
        ),
    )
    return Printed([tuple(w) for one in pages for w in one["words"]], [tuple(d) for one in pages for d in one["drawn"]])


def close_print_preview(person: Person) -> None:
    person.page.click("[data-testid=print-close]")
    person.page.wait_for_selector("[data-testid=print-preview]", state="detached")


def choose_view(person: Person, label: str) -> None:
    """View ▸ Flow or View ▸ Page (entries that are ticked, so not plain menu items)."""
    page = person.page
    page.click('.menus .title:text-is("View")')
    page.locator(".menus .drop [role^=menuitem]", has=page.locator(".label", has_text=re.compile(f"^{label}$"))).click()


def share_and_open(world: World, name: str, role: str) -> Person:
    """``name`` is given ``role`` in Ann's document by Ann and opens it."""
    other = world.join(name)
    world.ann.share(other, role)
    other.open()
    other.wait_until_open()
    return other


# ================================================================================================= the kinds
class Table:
    """A table of the text (E9.32), made with Insert ▸ Table… as the dialog offers it."""

    SELECTOR = "[data-testid=table]"
    ADDED = "Add table"  # how the history speaks of adding one
    KIND = "Table"  # how the # list says what a thing is
    #: the entries that change a table, by menu, as the menus of composes have them (claudia-menus.xlsx)
    CHANGES = {
        "Insert": ("Table…",),
        "Format": ("Name & describe…",),
        "Tools": ("Row", "Column", "Sort", "Merge Cells", "Split Cell", "Table Options…"),
    }

    def count(self, person: Person) -> int:
        return person.page.locator(self.SELECTOR).count()

    def insert(self, person: Person) -> None:
        before = self.count(person)
        person.menu("Insert", "Table…")
        person.page.wait_for_selector("[data-testid=table-dialog]")
        person.page.click("[data-testid=table-insert]")
        eventually(lambda: _equal(self.count(person), before + 1))

    def contents(self, person: Person) -> list[str]:
        """The words of every box, row by row."""
        return person.boxes()

    def box(self, person: Person, row: int, col: int):
        return person.page.locator(f'{self.SELECTOR} [data-box="r{row}/c{col}"]')

    def type_into(self, person: Person, words: tuple[str, ...]) -> None:
        """Type ``words`` into the boxes from where the caret is, a Tab after each (which puts the words in)."""
        for word in words:
            person.page.keyboard.type(word)
            person.page.keyboard.press("Tab")

    def work_in(self, person: Person) -> list[str]:
        """Click into the first box, type the words, a Tab after each, and leave the table; what it shows then."""
        self.box(person, 1, 1).click()
        self.type_into(person, WORDS)
        person.page.keyboard.press("Escape")
        wait_for_entries(person, WORDS)
        return steady(person, lambda: self.contents(person))

    def work_with_mouse(self, person: Person) -> tuple[str, ...]:
        """Into the first body box with the mouse and type, into the next one with the mouse and type, and click back
        (a box takes its words when it is left)."""
        for col, word in enumerate(MORE_WORDS, start=1):
            self.box(person, 2, col).click()
            person.page.keyboard.type(word)
        self.box(person, 2, 1).click()
        return MORE_WORDS

    def enter_with_keyboard(self, person: Person) -> None:
        """To the end of the first paragraph, the one above it, and the down arrow (D1330)."""
        for key in ("Control+Home", "End", "ArrowDown"):
            person.page.keyboard.press(key)
        eventually(lambda: _equal(person.focused_box(), "r1/c1"))

    def leave_with_keyboard(self, person: Person) -> None:
        person.page.keyboard.press("Escape")

    def tab(self, person: Person):
        """The tab with its name, above it: what selects it."""
        return person.page.locator(f"{self.SELECTOR} [data-testid=table-tab]")

    def select(self, person: Person) -> None:
        self.tab(person).click()

    def remove(self, person: Person) -> None:
        """Select it and press Delete."""
        self.select(person)
        person.page.keyboard.press("Delete")

    def try_to_change(self, person: Person) -> None:
        """What someone would try: type into a box, add a row with its keys, delete the table."""
        box = self.box(person, 2, 1)
        box.click()
        person.page.keyboard.type("changed")
        person.page.keyboard.press("Tab")
        box.click()
        person.page.keyboard.press("Shift+Alt+ArrowDown")
        self.remove(person)

    def times_on_paper(self, drawn: list[tuple[float, float, float, float]]) -> int:
        """How many tables the drawing shows: a table is drawn with a heavier line under its header, so the number of
        heights at which the heaviest line is drawn. Nothing drawn: no table."""
        lines = [item for item in drawn if item[2] > item[3]]
        if not lines:
            return 0
        heaviest = max(item[3] for item in lines)
        return len({round(item[1], 1) for item in lines if item[3] == heaviest})


KINDS = {"table": Table()}
KIND = "(?P<kind>" + "|".join(KINDS) + ")"
TOP, BOTTOM = '(?P<top>[^"]+)', '(?P<bottom>[^"]+)'


def kind_of(name: str):
    return KINDS[name]


def wait_for_entries(person: Person, words: tuple[str, ...]) -> None:
    """Until the history has an entry for each of ``words`` being typed: the server has them."""
    eventually(lambda: _equal([w for w in words if not any(f"“{w}”" in e for e in history(person))], []))


# ============================================================================================ what a scenario keeps
@dataclass
class Scene:
    """What a scenario remembers between its steps."""

    kind: Table | None = None
    left: list[str] = field(default_factory=list)  # what the object showed when I left it
    worked: list[str] = field(default_factory=list)  # the words I typed into it, in order
    name: str = ""
    description: str = ""
    copy: Person | None = None  # the new document a file was opened as
    printed: Printed | None = None  # what the print preview showed
    cable: Cable | None = None


@pytest.fixture
def scene() -> Scene:
    return Scene()


class Cable:
    """Every connection of one browser context, routed through Playwright so that a step can pull it out."""

    def __init__(self, person: Person):
        self.links: list = []
        self.made = 0
        person.context.route_web_socket(re.compile(r"^wss?://"), self._connect)

    def _connect(self, route) -> None:
        server = route.connect_to_server()
        self.links.append((route, server))
        self.made += 1

    def pull(self) -> None:
        """Both ends of every link close, as when the network goes away; the page tries again by itself."""
        links, self.links = self.links, []
        for page_end, server_end in links:
            page_end.close(code=1012, reason="the connection was lost")
            server_end.close()


# ================================================================================================= background
@given('a new composes document "report" in which I am Ann, an owner')
def _new_document(world, scene):
    ann = world.join("Ann")
    scene.cable = Cable(ann)
    ann.create()


@given('the text has the paragraphs "Before" and "After"')
def _paragraphs(world):
    ann = world.ann
    ann.page.click(TEXT)
    ann.page.keyboard.type("Before")
    ann.page.keyboard.press("Enter")
    ann.page.keyboard.type("After")
    eventually(lambda: _equal(paragraphs(ann), ["Before", "After"]))
    wait_for_entries(ann, ("Before", "After"))


@given(parsers.parse('my caret is at the end of "{words}"'))
def _caret_at_end(world, words):
    world.ann.page.click(f'{PARAGRAPHS}:has-text("{words}")')
    world.ann.page.keyboard.press("End")
    eventually(lambda: _equal(world.ann.caret(), (words, len(words))))


# ================================================================================================= making and working
@when(parsers.re(rf"I insert a {KIND}$"))
@given(parsers.re(rf"I have inserted a {KIND}$"))
def _insert(world, scene, kind):
    scene.kind = kind_of(kind)
    scene.kind.insert(world.ann)


@when(parsers.re(rf"I insert a {KIND} and work in it$"))
@given(parsers.re(rf"I have inserted a {KIND} and worked in it$"))
def _insert_and_work(world, scene, kind):
    scene.kind = kind_of(kind)
    scene.kind.insert(world.ann)
    scene.left = scene.kind.work_in(world.ann)
    scene.worked = list(WORDS)


@then(parsers.re(rf"I can work in the {KIND} with the mouse$"))
def _work_with_mouse(world, scene, kind):
    ann, made = world.ann, kind_of(kind)
    typed = made.work_with_mouse(ann)
    wait_for_entries(ann, typed)
    scene.worked += typed
    for word in typed:
        assert word in made.contents(ann), f"{word!r} is not in it: {made.contents(ann)!r}"


@then(parsers.re(rf"I can work in the {KIND} with the keyboard alone, and leave it again with the keyboard alone$"))
def _work_with_keyboard(world, scene, kind):
    ann, made = world.ann, kind_of(kind)
    made.leave_with_keyboard(ann)
    eventually(lambda: _equal((ann.focused_box(), ann.caret() is not None), (None, True)))
    made.enter_with_keyboard(ann)
    made.type_into(ann, WORDS)
    made.leave_with_keyboard(ann)
    eventually(lambda: _equal((ann.focused_box(), ann.caret() is not None), (None, True)))
    wait_for_entries(ann, WORDS)
    scene.worked += WORDS
    for word in WORDS:
        assert word in made.contents(ann), f"{word!r} is not in it: {made.contents(ann)!r}"


@then(parsers.re(rf"what I did is shown in the {KIND} and nowhere else on the page$"))
def _only_there(world, scene, kind):
    ann, made = world.ann, kind_of(kind)
    shown = steady(ann, lambda: made.contents(ann))
    for word in scene.worked:
        assert shown.count(word) == 1, f"{word!r} is in it {shown.count(word)} times: {shown!r}"
    _equal(paragraphs(ann), ["Before", "After"])
    _equal(ann.page.locator(f"{TEXT} [data-object], {TEXT} {made.SELECTOR}").count(), 1)
    outside = ann.page.inner_text(TEXT)  # the words of the text area; what a box holds is not among them
    for word in scene.worked:
        assert word not in outside, f"{word!r} is shown outside it, in the text: {outside!r}"


@when(parsers.parse('I type "{words}" at the end of "{paragraph}"'))
def _type_at_end(world, words, paragraph):
    page = world.ann.page
    page.click(f'{PARAGRAPHS}:has-text("{paragraph}")')
    page.keyboard.press("End")
    page.keyboard.type(words)
    eventually(lambda: _equal(paragraph + words in paragraphs(world.ann), True))


@when(parsers.parse('I type "{words}" at the start of "{paragraph}"'))
def _type_at_start(world, words, paragraph):
    page = world.ann.page
    page.click(f'{PARAGRAPHS}:has-text("{paragraph}")')
    page.keyboard.press("Home")
    page.keyboard.type(words)
    eventually(lambda: _equal(words + paragraph in paragraphs(world.ann), True))


# ================================================================================================= it is there once
def shown_once_between(person: Person, made, top: str, bottom: str) -> None:
    """The text reads ``top``, the object, ``bottom``, and still does once the page has settled."""
    want = [top, "OBJECT", bottom]
    eventually(lambda: _equal(text_and_objects(person, made.SELECTOR), want))
    _equal(steady(person, lambda: text_and_objects(person, made.SELECTOR)), want)
    assert_visible(person, person.page.locator(made.SELECTOR))


def shown_once(person: Person, made) -> None:
    eventually(lambda: _equal(made.count(person), 1))
    _equal(steady(person, lambda: made.count(person)), 1)
    assert_visible(person, person.page.locator(made.SELECTOR))


@then(parsers.re(rf'the {KIND} is shown once, between "{TOP}" and "{BOTTOM}"$'))
def _shown_between(world, kind, top, bottom):
    shown_once_between(world.ann, kind_of(kind), top, bottom)


@then(parsers.re(rf"the {KIND} is shown once$"))
def _shown(world, kind):
    shown_once(world.ann, kind_of(kind))


@then(parsers.re(rf'the {KIND} is in the list of things I can refer to with "#" in the chat, once$'))
def _in_hash_list(world, kind):
    ann, made = world.ann, kind_of(kind)
    name = made.tab(ann).inner_text().strip()
    offered = hash_list(ann)
    _equal([thing for thing in offered if thing[0] == made.KIND], [(made.KIND, name)])


@then('the paragraphs "Before" and "After" are as they were')
def _paragraphs_as_they_were(world):
    _equal(steady(world.ann, lambda: paragraphs(world.ann)), ["Before", "After"])


@then(parsers.re(rf"there is no {KIND} in the text$"))
def _none(world, kind):
    made = kind_of(kind)
    eventually(lambda: _equal(made.count(world.ann), 0))
    _equal(steady(world.ann, lambda: made.count(world.ann)), 0)


# ================================================================================================= reload, connection
@when('I reload the page and open "report" again')
def _reload(world):
    world.ann.reopen()


@when("the connection to the server is lost and comes back")
def _connection_lost(world, scene):
    ann, cable = world.ann, scene.cable
    made = cable.made
    cable.pull()
    eventually(lambda: _equal(cable.made > made, True), seconds=30, page=ann.page)  # it connected again
    eventually(lambda: _equal(ann.page.locator(".health.open").count(), 1), seconds=30)


@then(parsers.re(rf"I can still work in the {KIND}$"))
def _still_work(world, kind):
    ann, made = world.ann, kind_of(kind)
    typed = made.work_with_mouse(ann)
    wait_for_entries(ann, typed)
    for word in typed:
        assert word in made.contents(ann), f"{word!r} is not in it: {made.contents(ann)!r}"


# ================================================================================================= views
@when("I switch to the page view")
def _page_view(world):
    choose_view(world.ann, "Page")


@when("I switch back to the flow view")
def _flow_view(world):
    close_print_preview(world.ann)
    choose_view(world.ann, "Flow")


@when("I open the print preview")
def _open_print_preview(world, scene):
    scene.printed = print_preview(world.ann)


@then(parsers.re(rf"the {KIND} is shown once on the pages$"))
def _once_on_paper(scene, kind):
    printed, made = scene.printed, kind_of(kind)
    _equal((len(printed.where("Before")), len(printed.where("After"))), (1, 1))
    between = printed.between("Before", "After")
    _equal(made.times_on_paper(between), 1)
    assert len(printed.drawn) == len(set(printed.drawn)), "something is drawn twice, in the same place"
    _equal(len(between), len(printed.drawn))  # and nothing of it above "Before" or below "After"


# ================================================================================================= history
@when("I undo")
def _undo(world):
    world.ann.page.keyboard.press("Escape")  # out of a box: undo is the document's, not the words of a box
    world.ann.menu("Edit", "Undo")


@when("I redo")
def _redo(world):
    world.ann.menu("Edit", "Redo")


@then("the history shows one entry for adding it")
def _one_entry(world, scene):
    made = scene.kind
    _equal(steady(world.ann, lambda: history(world.ann)).count(made.ADDED), 1)


@when(parsers.re(rf"I remove the {KIND}$"))
def _remove(world, kind):
    kind_of(kind).remove(world.ann)


@then(parsers.re(rf'there is no {KIND} in the text, in the "#" list, or in the print preview$'))
def _gone_everywhere(world, scene, kind):
    ann, made = world.ann, kind_of(kind)
    eventually(lambda: _equal(made.count(ann), 0))
    _equal(steady(ann, lambda: made.count(ann)), 0)
    _equal([thing for thing in hash_list(ann) if thing[0] == made.KIND], [])
    printed = print_preview(ann)
    close_print_preview(ann)
    _equal(made.times_on_paper(printed.drawn), 0)
    _equal([word for word in scene.worked if printed.where(word)], [])


@then(parsers.re(rf"the {KIND} is shown once as I left it$"))
def _back_as_left(world, scene, kind):
    ann, made = world.ann, kind_of(kind)
    shown_once(ann, made)
    eventually(lambda: _equal(made.contents(ann), scene.left))


# ================================================================================================= other people
@given("Ben, an editor, has the document open as well")
def _ben(world):
    share_and_open(world, "Ben", "editor")


@then(parsers.re(rf'Ben sees the {KIND} once, between "{TOP}" and "{BOTTOM}", as I left it$'))
def _ben_sees_as_left(world, scene, kind, top, bottom):
    ben, made = world.people["Ben"], kind_of(kind)
    shown_once_between(ben, made, top, bottom)
    eventually(lambda: _equal(made.contents(ben), scene.left))


@when("Ben reloads the page")
def _ben_reloads(world):
    world.people["Ben"].reopen()


@then(parsers.re(rf"Ben sees the {KIND} once$"))
def _ben_sees(world, kind):
    shown_once(world.people["Ben"], kind_of(kind))


@given("Cleo, a reader, has the document open")
def _cleo(world):
    # A reader is who may only look: the role "viewer" of the Share dialog ("May only look").
    share_and_open(world, "Cleo", "viewer")


@then(parsers.re(rf"Cleo sees the {KIND} once$"))
def _cleo_sees(world, kind):
    shown_once(world.people["Cleo"], kind_of(kind))


@then(parsers.re(rf"Cleo cannot change anything in the {KIND}$"))
def _cleo_cannot_change(world, scene, kind):
    cleo, ann, made = world.people["Cleo"], world.ann, kind_of(kind)
    made.try_to_change(cleo)
    for person in (cleo, ann):
        _equal(steady(person, lambda p=person: (made.count(p), made.contents(p))), (1, scene.left))


@then(parsers.re(rf"the entries for changing a {KIND} are not offered to Cleo or are shown as unavailable$"))
def _cleo_has_no_entries(world, kind):
    cleo, made = world.people["Cleo"], kind_of(kind)
    page = cleo.page
    offered = []
    made.box(cleo, 2, 1).click()  # where the entries would work: in a box of the table
    for title, entries in made.CHANGES.items():
        page.click(f'.menus .title:text-is("{title}")')
        for entry in entries:
            item = page.locator(".menus .drop [role^=menuitem]", has=page.locator(".label", has_text=entry)).first
            if item.count() and not disabled(item):
                offered.append(f"{title} ▸ {entry}")
        page.keyboard.press("Escape")
    made.box(cleo, 2, 1).click(button="right")  # its own menu, if it has one for her
    menu = page.locator("ul.menu[role=menu] > li > [role^=menuitem]")
    entries = steady(cleo, lambda: menu.evaluate_all(f"els => els.map(e => [e.innerText, ({OFF})(e)])"))
    offered += [f"its menu ▸ {label}" for label, off in entries if not off]
    page.keyboard.press("Escape")
    _equal(offered, [])


# ================================================================================================= names
@then(parsers.re(rf"the {KIND} has a name$"))
def _has_name(world, scene, kind):
    ann = world.ann
    ann.page.keyboard.press("Escape")
    kind_of(kind).select(ann)
    scene.name = name_in_dialog(ann)
    assert scene.name.strip(), "Name & describe… shows no name"


@then("that name is different from the name of every other thing in the document")
def _name_is_its_own(world, scene):
    ann = world.ann
    others = []
    for index in range(ann.page.locator(PARAGRAPHS).count()):
        ann.page.locator(PARAGRAPHS).nth(index).click()
        others.append(name_in_dialog(ann))
    offered = [name for _, name in hash_list(ann)]
    _equal(offered.count(scene.name), 1)  # its own entry
    others += [name for name in offered if name != scene.name]
    assert scene.name not in others, f"{scene.name!r} is also the name of another thing: {others!r}"


@when("I give it a description")
def _describe(world, scene):
    ann = world.ann
    scene.description = "What we grow, by crop"
    scene.kind.select(ann)
    choose(ann, "Name & describe…")
    ann.page.fill(f"{DIALOG} textarea", scene.description)
    ann.page.click(f"{DIALOG} button[type=submit]")
    ann.page.wait_for_selector(DIALOG, state="detached")


@then(parsers.re(rf"a screen reader reads the {KIND} by its name and its description$"))
def _read_aloud(world, scene, kind):
    whole = world.ann.page.locator(kind_of(kind).SELECTOR).get_by_role("table")
    expect(whole).to_have_accessible_name(re.compile("^" + re.escape(scene.name)))
    name_read = whole.aria_snapshot().splitlines()[0]  # '- table "<accessible name>":'
    if scene.description not in name_read:  # else it must be read as the description
        expect(whole).to_have_accessible_description(re.compile(re.escape(scene.description)))


# ================================================================================================= files
@when(parsers.parse("I download the document as {format} and open that file as a new document"))
def _download_and_open(world, scene, format, tmp_path):  # noqa: A002 - the word of the step
    ann = world.ann
    ann.menu("File", "Manage", "Export…")
    ann.page.select_option("[data-testid=export-format]", FORMATS[format])
    with ann.page.expect_download(timeout=30000) as taken:
        ann.page.click(f'{DIALOG} button:text-is("Export")')
    target = tmp_path / taken.value.suggested_filename
    target.write_bytes(Path(taken.value.path()).read_bytes())
    ann.page.keyboard.press("Escape")
    copy = Person(world.browser, world.url, f"{ann.document}-{FORMATS[format]}", "Ann")
    world.people["Ann-file"] = copy
    copy.page.goto(world.url + "/", wait_until="domcontentloaded")
    copy.page.set_input_files("input[type=file]", str(target))
    copy.finish_import()
    copy.wait_until_open(timeout=30000)
    scene.copy = copy


@then(parsers.re(rf'the new document has the {KIND} once, between "{TOP}" and "{BOTTOM}", with what I put in it$'))
def _copy_has_it(scene, kind, top, bottom):
    made = kind_of(kind)
    shown_once_between(scene.copy, made, top, bottom)
    eventually(lambda: _equal(made.contents(scene.copy), scene.left))
