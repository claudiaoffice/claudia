"""The steps of ``specs/objects/names.feature`` (E1.13; D550, D551, D554, D1303–D1305, D1310–D1312, D1317, D1318):
every thing has a name and can be described, a tag points at it by its name, and a tag that takes the view away leaves
a way back. One server of all three apps.

A scenario tagged with several ``@app:`` tags (and no table of examples) runs in each of those apps, one document per
app, in the apps that can have what it is about: a sheet has no text boxes and no paragraphs, so "a text box" there is
left out, as the specs README says a scenario runs "in all that the file's folder says" (D1456). A thing's name is
read where a person reads it: in Name & describe…, in the ``#`` list of the chat, on a tag. The Word and PowerPoint
files to import are made with ``python-docx`` and ``python-pptx``; what an export gives is read with ``python-docx``,
``zipfile`` and ``lxml``.

Name & describe… is chosen from the menu bar wherever it is (D1455): the menus workbook moves it from Format to Edit,
and that move belongs to the menu rework (`claudia-menus.xlsx`, Menus row 19: "the move to Edit is not done → ask").

A view that a tag or the way back moves scrolls smoothly, so a step waits for the view it expects (``eventually``) or
for the view to stop moving (``where``), never for a fixed time.
"""

from __future__ import annotations

import io
import itertools
import os
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest
from conftest import READY, Person, World, eventually, steady
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect
from pptx import Presentation
from pptx.util import Inches
from pytest_bdd import given, parsers, scenarios, then, when
from things import FIRST_CELL, OBJECTS, PICTURE, insert

scenarios("../../../claudiaoffice-log/specs/objects/names.feature")

DIALOG = ".modal"
NAME = f"{DIALOG} input[type=text]"
DESCRIPTION = f"{DIALOG} textarea"
DECORATIVE = f"{DIALOG} .check input[type=checkbox]"
NAME_PROBLEM = "#name-problem"
CHAT = ".write [role=combobox]"
OPTIONS = "#tag-list [role=option]"
TAGS = ".msg button.tag"
BACK = "[data-testid=back-chip] button"
PARAGRAPHS = "[data-testid=text] [data-paragraph]"
ENTRIES = "ol.log > li.entry"
TEXT_BOX_APPS = ("composes", "creates")  # a sheet has no text boxes
SLIDE_TABS = "[role=tablist][aria-label=slides] [role=tab]"
SHEET_TABS = "[role=tablist][aria-label^=sheets] [role=tab]"  # "sheets", or "sheets and slides" since E6.31
NAME_BOX = "input[aria-label=cell]"
_documents = itertools.count(1)


@pytest.fixture
def world(suite_world: World) -> World:
    """Every scenario here runs on the server of all three apps."""
    return suite_world


@dataclass
class Scene:
    """What a scenario remembers between its steps."""

    desks: dict[str, Person] = field(default_factory=dict)  # one document per app, its maker by app
    names: dict[str, str] = field(default_factory=dict)  # a thing's name before a change, by app
    entries: dict[str, int] = field(default_factory=dict)  # how many history entries there were, by app
    view: dict[str, object] = field(default_factory=dict)  # where the view was, by app (or by place)
    files: dict[str, bytes] = field(default_factory=dict)


@pytest.fixture
def scene() -> Scene:
    """A fresh memory for each scenario."""
    return Scene()


def apps_of(request) -> list[str]:
    """The apps the scenario's ``@app:`` tags name, in a fixed order."""
    tagged = {mark.name.removeprefix("app:") for mark in request.node.iter_markers() if mark.name.startswith("app:")}
    return [app for app in ("composes", "computes", "creates") if app in tagged]


def desk(world: World, scene: Scene, app: str, name: str = "Ann") -> Person:
    """A new document of ``app`` made by ``name``, kept in the scene and looked after by the world. (``World.join``
    keeps one document per scenario; these scenarios have one per app.)"""
    person = Person(world.browser, world.url, f"names-{next(_documents)}-{os.getpid()}", name, app)
    world.people[f"{name} {app}"] = person
    person.create()
    scene.desks[app] = person
    return person


def colleague(world: World, owner: Person, name: str = "Ben") -> Person:
    """A second person in ``owner``'s document, as an editor, with it open."""
    other = Person(world.browser, world.url, owner.document, name, owner.app)
    world.people[f"{name} {owner.app}"] = other
    owner.share(other, "editor")
    other.open()
    other.wait_until_open()
    return other


# ------------------------------------------------------------------------------------------------- reading names
def choose(person: Person, entry: str) -> None:
    """Choose ``entry`` from whichever top menu offers it; where none does and the caret is in a text, from the menu
    of the paragraph the caret is in (a caret is not something selected, D1601: Edit ▸ Name & Describe… is for what
    is selected, the paragraph's menu for the paragraph)."""
    page = person.page
    here = page.evaluate(
        "() => { const n = getSelection()?.focusNode; const e = n && (n.nodeType === 1 ? n : n.parentElement);"
        " return e?.closest('[data-testid=text] [data-paragraph]')?.dataset.paragraph ?? null }"
    )
    for title in page.eval_on_selector_all(".menus .title", "els => els.map(e => e.textContent.trim())"):
        page.click(f'.menus .title:text-is("{title}")')
        item = person.menu_item(entry)
        if item.count() and not item.is_disabled():
            item.click()
            return
        page.click(f'.menus .title:text-is("{title}")')
    if here is None:
        raise AssertionError(f"no menu has {entry!r}")
    page.locator(f'[data-testid=text] [data-paragraph="{here}"]').click(button="right")
    page.locator("[role=menu] [role=menuitem]", has_text=entry).first.click()


def open_name_and_describe(person: Person) -> None:
    """Name & describe… on what is selected or has the caret, and wait for its name field."""
    choose(person, "Name & Describe…")
    person.page.wait_for_selector(NAME)


def name_in_dialog(person: Person) -> str:
    """The name Name & describe… shows for what is selected or has the caret; the dialog is closed again."""
    open_name_and_describe(person)
    name = person.page.input_value(NAME)
    person.page.keyboard.press("Escape")
    return name


def save_name(person: Person, new: str) -> None:
    """In the open dialog: the name ``new``, Save. Whether the dialog closes is the caller's question."""
    person.page.fill(NAME, new)
    person.page.click(f"{DIALOG} button[type=submit]")


def rename(person: Person, new: str) -> None:
    """Name & describe… on what is selected, a new name, Save, and the dialog closed."""
    open_name_and_describe(person)
    save_name(person, new)
    person.page.wait_for_selector(DIALOG, state="detached")


def describe(person: Person, words: str) -> None:
    """Name & describe… on what is selected or has the caret, the description ``words``, Save."""
    open_name_and_describe(person)
    person.page.fill(DESCRIPTION, words)
    person.page.click(f"{DIALOG} button[type=submit]")
    person.page.wait_for_selector(DIALOG, state="detached")


def hash_list(person: Person, typed: str = "") -> list[str]:
    """What the # list of the chat offers after ``#`` and ``typed``: the text of each option after its kind."""
    page = person.page
    page.click(CHAT)
    page.keyboard.press("Control+a")
    page.keyboard.press("Backspace")
    page.keyboard.type("#" + typed)
    try:
        page.wait_for_selector(OPTIONS, timeout=3000)
    except PlaywrightTimeoutError:  # an empty list is an answer too
        return []
    offered = steady(
        person,
        lambda: page.eval_on_selector_all(
            OPTIONS,
            "els => els.map(e => [...e.childNodes].filter(n => !n.classList?.contains('kind'))"
            ".map(n => n.textContent).join('').trim())",
        ),
    )
    page.keyboard.press("Escape")
    page.keyboard.press("Control+a")
    page.keyboard.press("Backspace")
    return offered


def names_offered(person: Person, typed: str = "") -> list[str]:
    """The names in the # list (without what follows a name, like the first words of a paragraph)."""
    return [offered.split(" · ")[0] for offered in hash_list(person, typed)]


def tag_in_chat(person: Person, name: str) -> None:
    """A chat message with a tag to the thing called ``name``, picked from the # list."""
    page = person.page
    page.click(CHAT)
    page.keyboard.type("See #" + name)
    page.wait_for_selector(f'{OPTIONS}:has-text("{name}")')
    page.keyboard.press("Enter")
    page.keyboard.press("Enter")
    page.wait_for_selector(f'{TAGS}:text-is("#{name}")')
    leave_chat(person)


def reference_in_chat(person: Person) -> str:
    """Reference in Chat on what has the caret or is selected, by its key (the entry is in the context menus, D1607),
    and send it; the tag's words."""
    count = person.page.locator(TAGS).count()
    person.page.wait_for_timeout(300)  # a person presses the key after the page has seen where the caret went
    person.page.keyboard.press("Control+Alt+x")
    person.page.wait_for_function("sel => document.querySelector(sel)?.querySelector('.chip')", arg=CHAT)
    person.page.click(CHAT)
    person.page.keyboard.press("End")
    person.page.keyboard.press("Enter")
    person.page.wait_for_function("([sel, n]) => document.querySelectorAll(sel).length > n", arg=[TAGS, count])
    leave_chat(person)
    return person.page.locator(TAGS).last.inner_text().strip()


def leave_chat(person: Person) -> None:
    """Take the caret out of the chat box: while it is there, a click on a thing writes a tag for it (D551)."""
    person.page.locator(CHAT).blur()


def tab_names(person: Person) -> list[str]:
    """The names on the tabs of the slides or the sheets."""
    tabs = SLIDE_TABS if person.app == "creates" else SHEET_TABS
    return person.page.eval_on_selector_all(tabs, "els => els.map(e => e.textContent.trim())")


def object_names(person: Person) -> list[str]:
    """The name of every object on the page, as Name & describe… shows it."""
    names = []
    for index in range(person.page.locator(OBJECTS[person.app]).count()):
        select_object(person, index)
        names.append(name_in_dialog(person))
    return names


def tags(person: Person) -> list[str]:
    """The words of every tag in the chat, in order."""
    return person.page.eval_on_selector_all(TAGS, "els => els.map(e => e.textContent.trim())")


def history(person: Person) -> list[str]:
    """The text of every history entry, in order."""
    return person.page.eval_on_selector_all(ENTRIES, "els => els.map(e => e.innerText.replace(/\\s+/g, ' ').trim())")


# --------------------------------------------------------------------------------------------- making things
def type_paragraphs(person: Person, texts: list[str]) -> None:
    """Type ``texts`` as paragraphs at the end of the text (the first one into the empty paragraph of a new text)."""
    page = person.page
    page.click("[data-testid=text]")
    page.keyboard.press("Control+End")
    for i, words in enumerate(texts):
        if i or person.page.locator(PARAGRAPHS).first.inner_text().strip():
            page.keyboard.press("Enter")
        page.keyboard.type(words)
    eventually(lambda: _at_least(len(person.paragraphs()), len(texts)))


def _at_least(count: int, wanted: int) -> None:
    assert count >= wanted, f"{count} instead of at least {wanted}"


def caret_in(person: Person, index: int, where: str = "end") -> None:
    """The caret into paragraph ``index`` (from 0), at its end or in its middle."""
    paragraph = person.page.locator(PARAGRAPHS).nth(index)
    paragraph.scroll_into_view_if_needed()
    box = paragraph.bounding_box()
    assert box
    paragraph.click(position={"x": 4, "y": box["height"] / 2})
    person.page.keyboard.press("End")
    if where == "middle":
        for _ in range(len(paragraph.inner_text().strip()) // 2):
            person.page.keyboard.press("ArrowLeft")


def make_heading(person: Person, index: int) -> None:
    """Give paragraph ``index`` the style Heading 1."""
    caret_in(person, index)
    person.page.click("[data-testid=style-button]")
    person.page.click("[data-style=heading-1]")
    person.page.wait_for_selector("[data-testid=text] h2.st-heading-1")


def add_text_box(person: Person) -> None:
    """Edit ▸ Text Box, and out of the new box again."""
    insert(person, "a text box")
    person.page.keyboard.press("Escape")


def show_slide(person: Person, index: int) -> None:
    """Click the tab of slide ``index`` (from 0) and wait until it is the slide shown."""
    person.page.locator(SLIDE_TABS).nth(index).click()
    shown = "([tabs, i]) => document.querySelectorAll(tabs)[i]?.getAttribute('aria-selected') === 'true'"
    person.page.wait_for_function(shown, arg=[SLIDE_TABS, index])


def select_object(person: Person, index: int = 0) -> None:
    """Click object ``index`` of the page (from 0)."""
    person.page.keyboard.press("Escape")
    person.page.locator(OBJECTS[person.app]).nth(index).click()


def select_range(person: Person, rows_down: int = 2) -> None:
    """Select A1 and the ``rows_down`` cells below it."""
    person.page.locator(".viewport").click(position=FIRST_CELL)
    for _ in range(rows_down):
        person.page.keyboard.press("Shift+ArrowDown")


def undo(person: Person) -> None:
    """Edit ▸ Undo, with nothing open for writing."""
    person.page.keyboard.press("Escape")
    person.menu("Edit", "Undo")


# ---------------------------------------------------------------------------------------------- files to import
def docx_file(paragraphs: list[str], bookmark: tuple[int, str] | None = None) -> bytes:
    """A Word file with ``paragraphs``; ``bookmark`` puts a bookmark of that name around exactly one of them."""
    document = Document()
    for i, words in enumerate(paragraphs):
        paragraph = document.add_paragraph(words)
        if bookmark and bookmark[0] == i:
            start, end = OxmlElement("w:bookmarkStart"), OxmlElement("w:bookmarkEnd")
            start.set(qn("w:id"), "0")
            start.set(qn("w:name"), bookmark[1])
            end.set(qn("w:id"), "0")
            paragraph._p.insert(0, start)
            paragraph._p.append(end)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def pptx_file(picture_names: list[str]) -> bytes:
    """A presentation of two slides without names; slide 1 holds pictures named ``picture_names`` ('' for none)."""
    presentation = Presentation()
    blank = presentation.slide_layouts[6]
    first = presentation.slides.add_slide(blank)
    presentation.slides.add_slide(blank)
    for i, name in enumerate(picture_names):
        picture = first.shapes.add_picture(io.BytesIO(PICTURE), Inches(1 + 2.2 * i), Inches(1), Inches(2), Inches(1))
        picture.name = name
    out = io.BytesIO()
    presentation.save(out)
    return out.getvalue()


def import_file(world: World, scene: Scene, app: str, filename: str, data: bytes, *, tmp_path: Path) -> Person:
    """Give the file to the Open page and open it as a new document of Ann's."""
    person = Person(world.browser, world.url, f"names-{next(_documents)}-{os.getpid()}", "Ann", app)
    world.people[f"Ann {app}"] = person
    target = tmp_path / filename
    target.write_bytes(data)
    person.page.goto(world.url + "/", wait_until="domcontentloaded")
    person.page.set_input_files("input[type=file]", str(target))
    person.page.locator("input[name=import-name]").wait_for(timeout=20000)
    person.finish_import()
    person.wait_until_open(timeout=30000)
    scene.desks[app] = person
    return person


def export(person: Person, extension: str, comments: bool | None = None) -> bytes:
    """File ▸ Manage ▸ Export…, the format ``extension``, the comments option ticked or not, and the file it gives."""
    open_export(person, extension)
    if comments is not None:
        option = person.page.locator("[data-testid=export-description-comments] input")
        if option.is_checked() != comments:
            option.click()
    with person.page.expect_download(timeout=30000) as taken:
        person.page.click(f'{DIALOG} button:text-is("Export")')
    data = Path(taken.value.path()).read_bytes()
    person.page.keyboard.press("Escape")
    return data


def open_export(person: Person, extension: str) -> None:
    """File ▸ Manage ▸ Export…, with the format ``extension`` chosen."""
    person.menu("File", "Manage", "Export…")
    person.page.select_option("[data-testid=export-format]", extension)


# ================================================================================ a name from the start
@given("a text with two paragraphs")
def _two_paragraphs(world, scene):
    type_paragraphs(desk(world, scene, "composes"), ["The first paragraph of a text.", "The second paragraph of it."])


@when("I add a third paragraph")
def _third(scene):
    type_paragraphs(scene.desks["composes"], ["A third paragraph, added now."])


@then(parsers.parse('Name & describe… on it shows a name like "{name}"'))
def _shows_name(scene, name):
    ann = scene.desks["composes"]
    caret_in(ann, 2)
    scene.names["composes"] = name_in_dialog(ann)
    assert scene.names["composes"] == name


@then("the name is in my own language")
def _own_language(scene):
    # The page speaks English (the browser's language in these runs), so a name in her language starts with the English
    # word; no run here tries another language.
    assert scene.names["composes"].startswith("Paragraph ")


@given("a new document")
def _new_documents(world, scene, request):
    for app in apps_of(request):
        desk(world, scene, app)


@when("I add a text box, or a slide, or a sheet, or a chart")
def _add_each(scene):
    if "composes" in scene.desks:
        add_text_box(scene.desks["composes"])
    if "creates" in scene.desks:
        scene.desks["creates"].menu("Insert", "New Slide")
    if "computes" in scene.desks:
        computes = scene.desks["computes"]
        insert(computes, "a chart")
        computes.page.click("button[aria-label='new sheet']")
        dialog = computes.page.locator(DIALOG)
        expect(dialog).to_be_visible()  # the sheet is added once its dialog is answered with the name it offers
        offered = dialog.locator("input").first.input_value()
        assert offered, "the dialog of a new sheet offers no name"
        dialog.locator("button[type=submit]").click()


@then(parsers.parse('each has a name like "Text box 1", "Slide 2", "Sheet 2", "Chart 1"'))
def _each_named(scene):
    if "composes" in scene.desks:
        assert object_names(scene.desks["composes"]) == ["Text box 1"]
    if "creates" in scene.desks:
        eventually(lambda: _has(tab_names(scene.desks["creates"]), "Slide 2"))
    if "computes" in scene.desks:
        computes = scene.desks["computes"]
        # a sheet is named as in Excel, "Sheet2": a name "like" the spec's "Sheet 2"
        eventually(lambda: _same(any(re.fullmatch(r"Sheet ?2", n) for n in tab_names(computes)), True))
        computes.page.locator(SHEET_TABS).first.click()
        assert object_names(computes) == ["Chart 1"]


def _has(names: list[str], name: str) -> None:
    assert name in names, f"{name!r} is not among {names}"


@then("two things never have the same name")
def _all_different(scene):
    for app, person in scene.desks.items():
        names = [n.casefold() for n in object_names(person) + ([] if app == "composes" else tab_names(person))]
        assert len(names) == len(set(names)), f"{app}: a name occurs twice in {names}"


@given(parsers.parse('paragraphs called "Paragraph 1", "Paragraph 2" and "Paragraph 3" in this order'))
def _three_named(world, scene):
    ann = desk(world, scene, "composes")
    type_paragraphs(ann, ["Words of the first one.", "Words of the second one.", "Words of the third one."])
    for i in range(3):
        caret_in(ann, i)
        assert name_in_dialog(ann) == f"Paragraph {i + 1}"


@when("I insert a paragraph between the first and the second")
def _insert_between(scene):
    ann = scene.desks["composes"]
    caret_in(ann, 0)
    ann.page.keyboard.press("Enter")
    ann.page.keyboard.type("A paragraph in between.")
    eventually(lambda: _has(ann.paragraphs(), "A paragraph in between."))


@then(parsers.parse('it is called "{name}" and the others keep their names'))
def _between_named(scene, name):
    ann = scene.desks["composes"]
    found = []
    for i in range(4):
        caret_in(ann, i)
        found.append(name_in_dialog(ann))
    assert found == ["Paragraph 1", name, "Paragraph 2", "Paragraph 3"]


@given("a presentation or a text file whose slides, objects and paragraphs have no names")
def _unnamed_files(scene):
    scene.files["slides.pptx"] = pptx_file(["", "Logo", "Logo"])
    scene.files["text.docx"] = docx_file([f"Paragraph number {i} of an imported text." for i in range(1, 8)])


@when("I import it")
def _import(world, scene, tmp_path):
    for filename, data in scene.files.items():
        app = "creates" if filename.endswith(".pptx") else "composes"
        import_file(world, scene, app, filename, data, tmp_path=tmp_path)


@then(parsers.parse('every slide, object and paragraph has a name like "Slide 1", "Picture 2", "Paragraph 7"'))
def _imported_named(scene):
    slides = scene.desks["creates"]
    assert tab_names(slides) == ["Slide 1", "Slide 2"], tab_names(slides)
    pictures = object_names(slides)
    scene.names["pictures"] = ", ".join(pictures)
    assert any(re.fullmatch(r"Picture \d+", n) for n in pictures), pictures
    text = scene.desks["composes"]
    caret_in(text, 6)
    assert name_in_dialog(text) == "Paragraph 7"


@then(parsers.parse('what the file does name keeps its name; a name that occurs twice gets "(2)" on the later one'))
def _named_kept(scene):
    pictures = scene.names["pictures"].split(", ")
    assert pictures.count("Logo") == 1 and "Logo (2)" in pictures, pictures


@given(parsers.parse('a Word file with a bookmark "{name}" around exactly one paragraph'))
def _bookmarked(scene, name):
    scene.files["terms.docx"] = docx_file(["Before the terms.", "These are the terms.", "After them."], (1, name))


@then(parsers.parse('that paragraph is called "{name}"'))
def _called(scene, name):
    text = scene.desks["composes"]
    caret_in(text, 1)
    assert name_in_dialog(text) == name


@given(parsers.parse('a text with {count:d} paragraphs of which one was renamed "{name}" by a person'))
def _long_renamed(world, scene, tmp_path, count, name):
    data = docx_file([f"Paragraph {i} says something of its own." for i in range(1, count + 1)])
    ann = import_file(world, scene, "composes", "long.docx", data, tmp_path=tmp_path)
    caret_in(ann, 2)
    rename(ann, name)


@when("I export it as a Word file")
def _export_word(scene):
    scene.files["export"] = export(scene.desks["composes"], "docx")


def _bookmarks(data: bytes) -> list[tuple[str, str]]:
    """The bookmarks of a Word file: (name, the words of the paragraph it starts in)."""
    return [
        (start.get(qn("w:name")), paragraph.text)
        for paragraph in Document(io.BytesIO(data)).paragraphs
        for start in paragraph._p.iter(qn("w:bookmarkStart"))
        if start.get(qn("w:name")) != "_GoBack"
    ]


@then(parsers.parse('the file holds one bookmark, "{name}", around that paragraph'))
def _one_bookmark(scene, name):
    assert _bookmarks(scene.files["export"]) == [(name, "Paragraph 3 says something of its own.")]


@then("no bookmark for the paragraphs that still have their generic names")
def _no_generic_bookmark(scene):
    assert all(not re.fullmatch(r"Paragraph \d+", name) for name, _ in _bookmarks(scene.files["export"]))


# ============================================================================================ the dialog
@given("a picture is selected")
def _picture_selected(world, scene, request):
    for app in apps_of(request):
        person = desk(world, scene, app)
        insert(person, "a picture")
        select_object(person)


@when("I choose Edit ▸ Name & describe…")
def _choose_dialog(scene):
    for app, person in scene.desks.items():
        scene.entries[app] = len(history(person))
        open_name_and_describe(person)


@then('the dialog shows the name, the description and "Decorative"')
def _dialog_fields(scene):
    for app, person in scene.desks.items():
        page = person.page
        assert re.fullmatch(r"Picture \d+", page.input_value(NAME)), f"{app}: {page.input_value(NAME)!r}"
        assert page.locator(DESCRIPTION).count() == 1 and page.locator(DECORATIVE).count() == 1, app


@when(parsers.parse('I change the name to "{name}" and save'))
def _change_name(scene, name):
    for person in scene.desks.values():
        save_name(person, name)
        person.page.wait_for_selector(DIALOG, state="detached")


@then(parsers.parse('the picture is called "{name}" in the # list of the chat'))
def _in_hash_list(scene, name):
    for person in scene.desks.values():
        eventually(lambda person=person: _has(names_offered(person, name), name))


@then(parsers.parse('the history shows one entry "{word}"'))
def _one_entry(scene, word):
    for app, person in scene.desks.items():
        new = history(person)[scene.entries[app] :]
        assert len(new) == 1 and word in new[0], f"{app}: {new}"


@given("a text box is on the page")
def _text_box(world, scene, request):
    for app in apps_of(request):
        if app in TEXT_BOX_APPS:
            add_text_box(desk(world, scene, app))


@when(parsers.parse('I press the right button on it and choose "{entry}"'))
def _right_button(scene, entry):
    for person in scene.desks.values():
        person.page.locator(OBJECTS[person.app]).first.click(button="right")
        person.page.locator(
            f'[role=menu] [role=menuitem]:has-text("{entry}"), [role=menu] button:has-text("{entry}")'
        ).first.click()


@then("I see the same dialog as from the Edit menu, with the name field")
def _same_dialog(scene):
    for app, person in scene.desks.items():
        page = person.page
        page.wait_for_selector(NAME)
        from_context = (page.get_attribute(DIALOG, "aria-label"), page.input_value(NAME))
        page.keyboard.press("Escape")
        select_object(person)
        open_name_and_describe(person)
        from_menu = (page.get_attribute(DIALOG, "aria-label"), page.input_value(NAME))
        page.keyboard.press("Escape")
        assert from_context == from_menu, f"{app}: {from_context} from the object's menu, {from_menu} from the menu bar"


@given(parsers.parse('a text called "{name}" and a picture'))
def _text_and_picture(world, scene, request, name):
    for app in apps_of(request):
        if app in TEXT_BOX_APPS:
            person = desk(world, scene, app)
            add_text_box(person)
            select_object(person)
            rename(person, name)
            insert(person, "a picture")


@when(parsers.parse('I give the picture the name "{name}" and save'))
def _give_taken_name(scene, name):
    for person in scene.desks.values():
        select_object(person, 1)
        open_name_and_describe(person)
        save_name(person, name)


@then(parsers.parse('the dialog stays open with my entry and says "{words}"'))
def _refused(scene, words):
    for app, person in scene.desks.items():
        page = person.page
        # the server's answer either closes the dialog or puts the refusal into it
        answered = "([d, p]) => !document.querySelector(d) || document.querySelector(p)?.textContent.trim()"
        page.wait_for_function(answered, arg=[DIALOG, NAME_PROBLEM], timeout=10000)
        assert page.locator(NAME).count() == 1, f"{app}: the dialog closed"
        assert page.locator(NAME_PROBLEM).inner_text().strip() == words, (
            f"{app}: {page.locator(NAME_PROBLEM).inner_text()!r}"
        )


@given(parsers.parse('I renamed a picture from "{old}" to "{new}"'))
def _renamed_picture(world, scene, request, old, new):
    for app in apps_of(request):
        person = desk(world, scene, app)
        insert(person, "a picture")
        select_object(person)
        assert name_in_dialog(person) == old, app
        select_object(person)
        rename(person, new)


@when("I undo")
def _undo(scene):
    for person in scene.desks.values():
        undo(person)


@then(parsers.parse('the picture is called "{name}" again'))
def _called_again(scene, name):
    for person in scene.desks.values():
        select_object(person)
        eventually(lambda person=person: _same(name_in_dialog(person), name))


def _holds(true: bool, otherwise: str) -> None:
    assert true, otherwise


def _same(seen, wanted) -> None:
    assert seen == wanted, f"{seen!r} instead of {wanted!r}"


@given("ann and ben have the document open")
def _ann_and_ben(world, scene, request):
    for app in apps_of(request):
        ann = desk(world, scene, app)
        insert(ann, "a picture")
        colleague(world, ann)


@when(parsers.parse('ann renames a picture to "{name}"'))
def _ann_renames(scene, name):
    for app, ann in scene.desks.items():
        scene.names[app] = names_offered(ann, "Picture")[0]
        tag_in_chat(ann, scene.names[app])
        select_object(ann)
        rename(ann, name)


@then(parsers.parse('ben sees "{name}" in his # list, and a tag ann wrote earlier now reads "{again}"'))
def _ben_sees(world, scene, name, again):
    for app in scene.desks:
        ben = world.people[f"Ben {app}"]
        eventually(lambda ben=ben: _has(names_offered(ben, name), name))
        eventually(lambda ben=ben: _has(tags(ben), f"#{again}"))


@given(parsers.parse('the caret is in a paragraph called "{name}"'))
def _caret_in_named(world, scene, name):
    ann = desk(world, scene, "composes")
    type_paragraphs(ann, ["The first.", "The second.", "The third paragraph, about terms."])
    caret_in(ann, 2)
    assert name_in_dialog(ann) == name
    caret_in(ann, 2)
    assert reference_in_chat(ann) == f"#{name}"
    caret_in(ann, 2)


@when(parsers.parse('I choose Edit ▸ Name & describe…, change the name to "{name}" and save'))
def _rename_paragraph(scene, name):
    ann = scene.desks["composes"]
    rename(ann, name)


@then(parsers.parse('the paragraph is called "{name}"'))
def _paragraph_called(scene, name):
    ann = scene.desks["composes"]
    caret_in(ann, 2)
    assert name_in_dialog(ann) == name


@then(parsers.parse('an older tag in the chat to that paragraph reads "{name}", and so does the history'))
def _tag_and_history(scene, name):
    ann = scene.desks["composes"]
    eventually(lambda: _has(tags(ann), f"#{name}"))
    entries = history(ann)
    assert any(name in e for e in entries), entries
    assert not any("Paragraph 3" in e for e in entries), f"the history still names the old name: {entries}"


@given("the caret is in a paragraph (or a range of cells is selected)")
def _caret_or_range(world, scene, request):
    for app in apps_of(request):
        if app == "composes":
            ann = desk(world, scene, app)
            type_paragraphs(ann, ["A paragraph that is described."])
            caret_in(ann, 0)
        elif app == "computes":
            select_range(desk(world, scene, app))


@then("the dialog has a name field and a description field")
def _name_and_description(scene):
    for app, person in scene.desks.items():
        assert person.page.locator(NAME).count() == 1 and person.page.locator(DESCRIPTION).count() == 1, app


@then(parsers.parse('it has no "Decorative" tick, which only a picture, chart, shape or text box has'))
def _no_decorative(scene):
    for app, person in scene.desks.items():
        assert person.page.locator(DECORATIVE).count() == 0, app


@when("I type a description and save")
def _type_description(scene):
    for app, person in scene.desks.items():
        if person.page.input_value(NAME) == "":  # a range without a name asks for one first
            person.page.fill(NAME, "DescribedCells")
        person.page.fill(DESCRIPTION, f"What this is about, in {app}.")
        person.page.click(f"{DIALOG} button[type=submit]")
        person.page.wait_for_selector(DIALOG, state="detached")


@then("the dialog shows it again the next time I open it")
def _shows_again(scene):
    for app, person in scene.desks.items():
        if app == "composes":
            caret_in(person, 0)
        else:
            select_range(person)
        open_name_and_describe(person)
        assert person.page.input_value(DESCRIPTION) == f"What this is about, in {app}.", app
        person.page.keyboard.press("Escape")


@given("a range of cells or a table that has no name yet")
def _unnamed_range(world, scene, request):
    for app in apps_of(request):
        if app == "computes":
            select_range(desk(world, scene, app))


@then("the name field is empty and marked as required")
def _required(scene):
    for app, person in scene.desks.items():
        assert person.page.input_value(NAME) == "" and person.page.get_attribute(NAME, "aria-required") == "true", app


@then("the OK button stays off until I have typed a name that is free")
def _ok_off(scene):
    for person in scene.desks.values():
        save = person.page.locator(f"{DIALOG} button[type=submit]")
        assert save.is_disabled(), "OK is on with no name"
        person.page.fill(NAME, "FreeName")
        eventually(lambda save=save: _holds(save.is_enabled(), "OK stays off for a name that is free"))
        person.page.fill(NAME, tab_names(person)[0])  # taken: the sheet is called so
        eventually(lambda save=save: _holds(save.is_disabled(), "a name that is taken was let through"))
        person.page.fill(NAME, "")


@when("I type a name and a description and save")
def _name_and_describe_range(scene):
    for person in scene.desks.values():
        scene.entries[person.app] = len(history(person))
        person.page.fill(NAME, "Costs")
        person.page.fill(DESCRIPTION, "What the project costs, by month.")
        person.page.click(f"{DIALOG} button[type=submit]")
        person.page.wait_for_selector(DIALOG, state="detached")


@then("both are saved as one history step")
def _one_step(scene):
    for person in scene.desks.values():
        eventually(lambda person=person: _same(len(history(person)) - scene.entries[person.app], 1))


@then("one Undo takes both back")
def _undo_both(scene):
    for person in scene.desks.values():
        undo(person)
        select_range(person)
        eventually(lambda person=person: _same(name_in_dialog(person), ""))


@given(parsers.parse('a paragraph with the description "{words}"'))
def _described_paragraph(world, scene, words):
    ann = desk(world, scene, "composes")
    type_paragraphs(ann, ["A date that legal has to look at: 1 March."])
    caret_in(ann, 0)
    describe(ann, words)
    scene.names["description"] = words


@when("another person opens the same document")
def _another_opens(world, scene):
    colleague(world, scene.desks["composes"])


@then("she sees the same description in Name & describe…")
def _she_sees(world, scene):
    ben = world.people["Ben composes"]
    caret_in(ben, 0)
    open_name_and_describe(ben)
    assert ben.page.input_value(DESCRIPTION) == scene.names["description"]
    ben.page.keyboard.press("Escape")


@then("Undo takes my description back, as it does for a picture's")
def _undo_description(scene):
    ann = scene.desks["composes"]
    undo(ann)
    caret_in(ann, 0)
    open_name_and_describe(ann)
    assert ann.page.input_value(DESCRIPTION) == ""
    ann.page.keyboard.press("Escape")


@given("two paragraphs have a description and the rest have none")
def _two_described(world, scene):
    ann = desk(world, scene, "composes")
    type_paragraphs(ann, ["One.", "Two, described.", "Three.", "Four, described."])
    for i in (1, 3):
        caret_in(ann, i)
        describe(ann, f"Note on paragraph {i + 1}")


@when("I export to Word, or to OpenDocument")
def _open_export_dialog(scene):
    open_export(scene.desks["composes"], "docx")


@then(parsers.parse('the export dialog offers "{words}", off by default'))
def _offers(scene, words):
    page = scene.desks["composes"].page
    for extension in ("docx", "odt"):
        page.select_option("[data-testid=export-format]", extension)
        option = page.locator("[data-testid=export-description-comments]")
        assert option.inner_text().strip() == words and not option.locator("input").is_checked(), extension
    page.keyboard.press("Escape")


@when("I tick it")
def _tick(scene):
    ann = scene.desks["composes"]
    days = {date.today().isoformat()}
    scene.files = {extension: export(ann, extension, comments=True) for extension in ("docx", "odt")}
    scene.view["days"] = days | {date.today().isoformat()}  # "today" on either side of a midnight


def _comments(extension: str, data: bytes) -> list[tuple[str, str, str, str]]:
    """The comments of a Word or OpenDocument file: (author, date, words, the paragraph they are on)."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if extension == "docx":
            if "word/comments.xml" not in archive.namelist():
                return []
            return _docx_comments(data)
        return _odt_comments(archive.read("content.xml"))


def _docx_comments(data: bytes) -> list[tuple[str, str, str, str]]:
    """The comments of a Word file: (author, day, words, the paragraph they are on)."""
    document = Document(io.BytesIO(data))
    part = next(p for p in document.part.package.parts if p.partname.endswith("/comments.xml"))
    root = etree.fromstring(part.blob)
    on = {}
    for paragraph in document.paragraphs:
        for start in paragraph._p.iter(qn("w:commentRangeStart")):
            on[start.get(qn("w:id"))] = paragraph.text
    return [
        (c.get(qn("w:author")), c.get(qn("w:date"))[:10], "".join(c.itertext()).strip(), on.get(c.get(qn("w:id")), ""))
        for c in root.iter(qn("w:comment"))
    ]


def _odt_comments(content: bytes) -> list[tuple[str, str, str, str]]:
    """The annotations of an OpenDocument text's content.xml: (author, day, words, the paragraph they are on)."""
    ns = {"office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0", "dc": "http://purl.org/dc/elements/1.1/"}
    found = []
    for note in etree.fromstring(content).iter(f"{{{ns['office']}}}annotation"):
        paragraph = note.getparent()
        words = "".join(
            t for t in note.itertext() if t not in note.xpath("dc:creator/text()|dc:date/text()", namespaces=ns)
        )
        rest = "".join(t for t in paragraph.itertext() if t not in note.itertext())
        found.append(
            (
                note.findtext("dc:creator", namespaces=ns),
                (note.findtext("dc:date", namespaces=ns) or "")[:10],
                words.strip(),
                rest.strip(),
            )
        )
    return found


@then("the file has two comments, each on its paragraph, saying the description")
def _two_comments(scene):
    for extension, data in scene.files.items():
        found = sorted((words, on) for _, _, words, on in _comments(extension, data))
        assert found == [("Note on paragraph 2", "Two, described."), ("Note on paragraph 4", "Four, described.")], (
            extension,
            found,
        )


@then("the comments are by me and dated today")
def _by_me(scene):
    # The spec's "today" is the wall clock's: the day is taken just before and just after the export.
    for extension, data in scene.files.items():
        for author, day, _, _ in _comments(extension, data):
            assert author == "ann" and day in scene.view["days"], (extension, author, day)


@when("I leave it off")
def _leave_off(scene):
    ann = scene.desks["composes"]
    scene.files = {extension: export(ann, extension, comments=False) for extension in ("docx", "odt")}


@then("the file has no comment from Claudia")
def _no_comments(scene):
    for extension, data in scene.files.items():
        assert _comments(extension, data) == [], extension


@given("no paragraph has a description")
def _none_described(world, scene):
    type_paragraphs(desk(world, scene, "composes"), ["A paragraph.", "Another one."])


@when("I open the export dialog for Word")
def _export_dialog_word(scene):
    open_export(scene.desks["composes"], "docx")


@then("the option about comments is not there")
def _no_option(scene):
    ann = scene.desks["composes"]
    page = ann.page
    # The dialog asks the server how many descriptions there are; the option can only be judged after its answer.
    eventually(lambda: _holds(any("descriptions" in a for a in ann.answers), "the dialog got no answer"), page=page)
    page.evaluate("() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))")
    assert page.locator("[data-testid=export-description-comments]").count() == 0
    page.keyboard.press("Escape")


@given(parsers.parse('a heading "{title}"'))
def _a_heading(world, scene, title):
    ann = desk(world, scene, "composes")
    type_paragraphs(ann, [title, "The words below the heading."])
    make_heading(ann, 0)


@when("I open Name & describe… on it")
def _open_on_heading(scene):
    ann = scene.desks["composes"]
    caret_in(ann, 0)
    open_name_and_describe(ann)


@then(parsers.parse('the name is "{name}" and cannot be changed there'))
def _locked(scene, name):
    page = scene.desks["composes"].page
    assert page.input_value(NAME) == name and page.get_attribute(NAME, "readonly") is not None


@then("the description can")
def _description_can(scene):
    ann = scene.desks["composes"]
    ann.page.fill(DESCRIPTION, "Where the text begins.")
    ann.page.click(f"{DIALOG} button[type=submit]")
    ann.page.wait_for_selector(DIALOG, state="detached")
    caret_in(ann, 0)
    open_name_and_describe(ann)
    assert ann.page.input_value(DESCRIPTION) == "Where the text begins."
    ann.page.keyboard.press("Escape")


@given(parsers.parse('two headings that both read "{title}"'))
def _two_headings(world, scene, title):
    scene.names["title"] = title
    ann = desk(world, scene, "composes")
    type_paragraphs(ann, [title, "Words.", title, "More words."])
    make_heading(ann, 0)
    make_heading(ann, 2)


@then(parsers.parse('the second is shown as "{shown}" in the # list'))
def _second_shown(scene, shown):
    ann = scene.desks["composes"]
    title = scene.names["title"]
    eventually(lambda: _same(sorted(names_offered(ann, title)), sorted([title, shown])))
    caret_in(ann, 0)
    assert name_in_dialog(ann) == title, "the first heading is not called by its title"
    caret_in(ann, 2)
    assert name_in_dialog(ann) == shown, f"the later heading is not {shown!r}"


@then("the text of the heading is unchanged")
def _heading_unchanged(scene):
    assert scene.desks["composes"].paragraphs()[2] == scene.names["title"]


@given(parsers.parse('a paragraph called "{name}"'))
def _called_paragraph(world, scene, name):
    ann = desk(world, scene, "composes")
    type_paragraphs(ann, ["First.", "Second.", "The third paragraph, long enough to split."])
    caret_in(ann, 2)
    assert name_in_dialog(ann) == name


@when("I split it in the middle")
def _split(scene):
    ann = scene.desks["composes"]
    caret_in(ann, 2, "middle")
    ann.page.keyboard.press("Enter")
    eventually(lambda: _same(len(ann.paragraphs()), 4))


@then(parsers.parse('the first part is still "{name}" and the second has a new name'))
def _split_names(scene, name):
    ann = scene.desks["composes"]
    caret_in(ann, 2)
    assert name_in_dialog(ann) == name
    caret_in(ann, 3)
    scene.names["second"] = name_in_dialog(ann)
    assert scene.names["second"] not in ("", name)


@when("I join them again")
def _join(scene):
    ann = scene.desks["composes"]
    caret_in(ann, 3)
    ann.page.keyboard.press("Home")
    ann.page.keyboard.press("Backspace")
    eventually(lambda: _same(len(ann.paragraphs()), 3))


@then(parsers.parse('the paragraph is "{name}", and Undo brings the second name back'))
def _joined(scene, name):
    ann = scene.desks["composes"]
    caret_in(ann, 2)
    assert name_in_dialog(ann) == name
    undo(ann)
    eventually(lambda: _same(len(ann.paragraphs()), 4))
    caret_in(ann, 3)
    assert name_in_dialog(ann) == scene.names["second"]


# ============================================================================================== pointing
def long_text(world: World, scene: Scene, tmp_path: Path, count: int, heading_at: int | None = None) -> Person:
    """A text of ``count`` paragraphs, imported from a Word file, with a heading "Introduction" at ``heading_at``."""
    words = [f"Paragraph {i} says something of its own." for i in range(1, count + 1)]
    if heading_at is not None:
        words[heading_at] = "Introduction"
    ann = import_file(world, scene, "composes", "long.docx", docx_file(words), tmp_path=tmp_path)
    if heading_at is not None:
        make_heading(ann, heading_at)
    return ann


@given(parsers.parse('a text of {count:d} paragraphs of which one is renamed "{name}", and a heading "{title}"'))
def _long_text(world, scene, tmp_path, count, name):
    ann = long_text(world, scene, tmp_path, count, heading_at=count - 10)
    caret_in(ann, count - 50)
    rename(ann, name)
    caret_in(ann, 0)


@when("I type # in the chat")
def _type_hash(scene):
    scene.view["offered"] = hash_list(scene.desks["composes"])


@then(parsers.parse('the list offers the paragraphs in my view as "{form}"'))
def _in_view(scene, form):
    ann = scene.desks["composes"]
    visible = ann.page.eval_on_selector_all(
        PARAGRAPHS,
        "els => els.filter(e => { const r = e.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight })"
        ".map(e => e.textContent.trim())",
    )
    offered = scene.view["offered"]
    for words in visible[:3]:
        number = re.match(r"Paragraph (\d+)", words)
        assert number and any(
            re.fullmatch(rf"Paragraph {number[1]} · {re.escape(words[:12])}.*", o) for o in offered
        ), f"{words!r} is not offered as {form!r}: {offered}"


@then(parsers.parse('always "{name}" and "{title}", wherever they are'))
def _always(scene, name, title):
    names = [o.split(" · ")[0] for o in scene.view["offered"]]
    assert name in names and title in names, names


@when(parsers.parse('I type "{typed}"'))
def _type_filter(scene, typed):
    scene.view["filtered"] = names_offered(scene.desks["composes"], typed)


@then("the list is filtered across the whole document")
def _filtered(scene):
    assert scene.view["filtered"] == ["Terms"], scene.view["filtered"]


@given("a tag in the chat to a paragraph that a colleague has since deleted")
def _tag_to_deleted(world, scene):
    ann = desk(world, scene, "composes")
    type_paragraphs(ann, ["The first.", "A paragraph that will go.", "The last."])
    caret_in(ann, 1)
    rename(ann, "Doomed")
    tag_in_chat(ann, "Doomed")
    caret_in(ann, 0)  # her caret away from it: the place around a person's caret is hers while she is there
    ben = colleague(world, ann)
    caret_in(ben, 0)  # from the end of the first paragraph to the end of the second: the second goes, the first stays
    ben.page.keyboard.press("Shift+ArrowDown")
    ben.page.keyboard.press("Shift+End")
    ben.page.keyboard.press("Backspace")
    eventually(lambda: _same(len(ann.paragraphs()), 2))


@when("I click the tag")
def _click_tag(scene):
    for person in scene.desks.values():
        scene.view.setdefault("before", {})[person.app] = where(person)
        person.page.locator(TAGS).last.click()


@then("I see the text as it was when the paragraph last existed, as a replay, with the paragraph marked")
def _replay(scene):
    page = scene.desks["composes"].page
    page.wait_for_selector("[data-testid=replay-bar]", timeout=10000)
    eventually(lambda: _has(scene.desks["composes"].paragraphs(), "A paragraph that will go."))
    page.wait_for_selector(f"{PARAGRAPHS}.pointed")


@then("nothing in the document has changed")
def _unchanged(world):
    ben = world.people["Ben composes"]
    assert len(ben.paragraphs()) == 2 and not any("will go" in words for words in ben.paragraphs()), ben.paragraphs()


# ============================================================================================ the way back
def where(person: Person) -> object:
    """Where the view is, once it has stopped moving, as the way back counts it (D1312): the text's top visible
    paragraph, the sheet's top left cell, or the slide shown."""
    return steady(person, lambda: _view_now(person))


def _view_now(person: Person) -> object:
    if person.app == "composes":
        return person.page.evaluate(
            """sel => { const top = document.querySelector('[data-testid=text-scroller]').getBoundingClientRect().top
              const p = [...document.querySelectorAll(sel)].find(e => e.getBoundingClientRect().bottom > top)
              return p ? p.textContent.trim() : null }""",
            PARAGRAPHS,
        )
    if person.app == "computes":
        return person.page.evaluate(_TOP_LEFT_CELL)
    return person.page.eval_on_selector(f"{SLIDE_TABS}[aria-selected=true]", "e => e.textContent.trim()")


# The cell at the top left of the sheet, as the way back counts it (D1312): the first row and column past the headers.
_TOP_LEFT_CELL = """() => {
  const corner = document.querySelector('.colhead').getBoundingClientRect().bottom
  const left = document.querySelector('.rowhead').getBoundingClientRect().right
  const row = [...document.querySelectorAll('.rowhead')].find(e => e.getBoundingClientRect().bottom > corner + 1)
  const col = [...document.querySelectorAll('.colhead')].find(e => e.getBoundingClientRect().right > left + 1)
  return (col ? col.textContent.trim() : '') + (row ? row.textContent.trim() : '')
}"""


def moved_from(person: Person, before: object) -> object:
    """Wait until the view has left ``before`` and stopped moving; where it is then."""
    eventually(lambda: _differs(where(person), before))
    return where(person)


def _differs(seen, before) -> None:
    assert seen != before, f"the view is still at {before!r}"


def back_at(person: Person, place: object) -> None:
    """Wait until the view is at ``place`` again."""
    eventually(lambda: _same(where(person), place))


def jump(person: Person, tag: str | None = None) -> None:
    """Click the last tag of the chat (or the last one that reads ``tag``) and wait until the view has moved."""
    before = where(person)
    found = person.page.locator(TAGS) if tag is None else person.page.locator(f'{TAGS}:text-is("{tag}")')
    found.last.click()
    person.page.locator(BACK).wait_for(timeout=5000)
    moved_from(person, before)


FAR = {"composes": "Far away", "computes": "FarAway", "creates": "Far away"}  # a range name has no spaces


def _far_tag(world: World, scene: Scene, tmp_path: Path, app: str) -> Person:
    """A document of ``app`` with something far from where Ann looks (and a third place, "Middle"), and a colleague's
    message with a tag to the far thing. Ann looks at page 2 of the text, the top of the sheet, slide 2."""
    if app == "composes":
        ann = long_text(world, scene, tmp_path, 400)
    else:
        ann = desk(world, scene, app)
        if app == "creates":
            for _ in range(8):
                ann.menu("Insert", "New Slide")
            add_text_box(ann)
            show_slide(ann, 4)
            add_text_box(ann)
    go_near(ann)  # she reads elsewhere: what she just made is not hers to hold any more
    ben = colleague(world, ann)
    for place, name in (("far", FAR[app]), ("middle", "Middle")):
        _point_at(ben, place)
        rename(ben, name)
        if app == "computes":  # the Name Box shows the new name once the server has it, and not before
            eventually(lambda name=name: _same(ben.page.input_value(NAME_BOX), name))
    _point_at(ben, "far")
    assert reference_in_chat(ben) == f"#{FAR[app]}"
    ann.page.wait_for_selector(f'{TAGS}:text-is("#{FAR[app]}")')
    return ann


def _point_at(person: Person, place: str) -> None:
    """The caret or the selection on the far thing (paragraph 361, the cell A300, the text box on slide 9) or on the
    middle one (paragraph 201, the cell A150, the text box on slide 5)."""
    far = place == "far"
    if person.app == "composes":
        caret_in(person, 360 if far else 200)
    elif person.app == "computes":
        person.page.fill(NAME_BOX, "A300" if far else "A150")
        person.page.press(NAME_BOX, "Enter")
    else:
        show_slide(person, 8 if far else 4)
        select_object(person)


def go_near(person: Person) -> None:
    """Where Ann reads: page 2 of the text, the top of the sheet, slide 2."""
    if person.app == "composes":
        person.page.locator(PARAGRAPHS).nth(20).scroll_into_view_if_needed()
    elif person.app == "computes":
        person.page.evaluate("() => { document.querySelector('.viewport').scrollTop = 0 }")
    else:
        show_slide(person, 1)
    where(person)


@given("I am reading page 2 of a long text")
def _reading_page_2(world, scene, tmp_path):
    _far_tag(world, scene, tmp_path, "composes")


@given("a colleague's chat message points at a paragraph on page 40")
def _colleague_points():
    """Made with the text: Ben's message tags the paragraph "Far away", 360 paragraphs further down."""


@then("the text shows that paragraph, marked for a moment")
def _shows_far(scene):
    page = scene.desks["composes"].page
    marked = page.locator(f"{PARAGRAPHS}.pointed")
    marked.wait_for(timeout=10000)
    assert "Paragraph 361" in marked.inner_text()
    scroller = page.locator("[data-testid=text-scroller]").bounding_box()
    eventually(lambda: _inside(marked.bounding_box(), scroller))
    marked.wait_for(state="detached", timeout=15000)  # "for a moment": the mark goes again


def _inside(box: dict | None, frame: dict | None) -> None:
    assert box and frame, "not on the page"
    top, bottom = box["y"], box["y"] + box["height"]
    assert top >= frame["y"] and bottom <= frame["y"] + frame["height"], f"{box} is not in {frame}"


@then(parsers.parse('a "{words}" is offered'))
def _back_offered(scene, words):
    for person in scene.desks.values():
        back = person.page.locator(BACK)
        back.wait_for(timeout=5000)
        assert back.inner_text().strip() == words


@when("I use it")
def _use_back(scene):
    for person in scene.desks.values():
        person.page.click(BACK)


@then("I am reading page 2 again, at the line where I was")
def _back_on_page_2(scene):
    back_at(scene.desks["composes"], scene.view["before"]["composes"])


@given("I am looking at the top of a long sheet")
def _top_of_sheet(world, scene, tmp_path):
    _far_tag(world, scene, tmp_path, "computes")
    assert where(scene.desks["computes"]) == "A1"


@given("a tag points at a named range far down in it")
def _range_far():
    """Made with the sheet: Ben's message tags the range "FarAway" at A300."""


@when(parsers.parse('I click the tag and then "{words}"'))
@when(parsers.parse('I click a tag that points at an object on slide 9, and then "{words}"'))
def _tag_and_back(scene, words):
    for person in scene.desks.values():
        scene.view.setdefault("before", {})[person.app] = where(person)
        jump(person)
        person.page.locator(BACK, has_text=words).click()


@then("I see the top of the sheet again")
def _top_again(scene):
    back_at(scene.desks["computes"], scene.view["before"]["computes"])


@given("I am on slide 2")
def _on_slide_2(world, scene, tmp_path):
    _far_tag(world, scene, tmp_path, "creates")


@then("I am on slide 2 again")
def _slide_2_again(scene):
    back_at(scene.desks["creates"], "Slide 2")


@given("a tag took the view away")
def _taken_away(world, scene, tmp_path, request):
    for app in apps_of(request):
        ann = _far_tag(world, scene, tmp_path, app)
        ann.page.clock.install()  # the minute to wait is the page's, not the test's
        jump(ann)


@when("I wait a minute")
def _wait_a_minute(scene):
    for person in scene.desks.values():
        person.page.clock.fast_forward("01:00")


@then(parsers.parse('"{words}" is still offered'))
def _still_offered(scene, words):
    for app, person in scene.desks.items():
        back = person.page.locator(BACK)
        assert back.count() == 1 and back.inner_text().strip() == words, f"{app}: the way back is gone"


# Where typing goes once the keyboard is back in the document (focused as Tab would, without a pointer): the text, the
# grid. Typing on a slide needs a text box open for writing, and that takes a click, so creates checks the click only.
TYPING_PLACE = {"composes": "[data-testid=text]", "computes": ".viewport"}


@when("I type, or click into the document")
def _type_or_click(scene):
    """Each of the two on its own: a click into the document; then, after the same jump again, typing."""
    for app, person in scene.desks.items():
        person.page.locator(READY[app]).click()
        scene.view.setdefault("gone after a click", {})[app] = _gone_soon(person)
        if app in TYPING_PLACE:
            go_near(person)
            jump(person)
            person.page.locator(TYPING_PLACE[app]).focus()
            person.page.keyboard.type("x")


def _gone_soon(person: Person) -> bool:
    try:
        person.page.locator(BACK).wait_for(state="detached", timeout=3000)
    except PlaywrightTimeoutError:
        return False
    return True


@then("it is gone")
def _gone(scene):
    for app, person in scene.desks.items():
        assert scene.view["gone after a click"][app], f"{app}: a click into the document left the way back"
        if app in TYPING_PLACE:
            assert _gone_soon(person), f"{app}: typing left the way back"


@given("a tag took the view from place A to place B, and I have not used the way back")
def _a_to_b(world, scene, tmp_path, request):
    for app in apps_of(request):
        ann = _far_tag(world, scene, tmp_path, app)
        jump(ann)
        scene.view.setdefault("B", {})[app] = where(ann)


@when("I click a second tag that takes me to place C")
def _to_c(world, scene):
    for app, ann in scene.desks.items():
        ben = world.people[f"Ben {app}"]
        _point_at(ben, "middle")
        target = reference_in_chat(ben)
        ann.page.wait_for_selector(f'{TAGS}:text-is("{target}")')
        jump(ann, target)


@then(parsers.parse('"{words}" leads to place B, not to A'))
def _leads_to_b(scene, words):
    for app, ann in scene.desks.items():
        ann.page.locator(BACK, has_text=words).click()
        back_at(ann, scene.view["B"][app])


def _fold_panel(person: Person) -> None:
    """The top bar's History & chat: folds the panel away, or unfolds it."""
    hidden = person.page.locator(CHAT).is_hidden()
    person.page.click(".btn.panel")
    person.page.wait_for_selector(CHAT, state="visible" if hidden else "hidden")


@given("the panel is hidden and a tag has taken the view away")
def _panel_hidden(world, scene, tmp_path, request):
    for app in apps_of(request):
        ann = _far_tag(world, scene, tmp_path, app)
        scene.view.setdefault("before", {})[app] = where(ann)
        jump(ann)
        _fold_panel(ann)


@when("I choose View ▸ Back where I was, or press Ctrl+Shift+B")
def _view_back(scene):
    """Each of the two on its own: the menu entry; then, after the same jump again (the panel unfolded for it and
    folded again), the keys."""
    for app, ann in scene.desks.items():
        ann.menu("View", "Back Where I Was")
        back_at(ann, scene.view["before"][app])
        _fold_panel(ann)
        jump(ann)
        _fold_panel(ann)
        ann.page.keyboard.press("Control+Shift+B")


@then("the view returns to where I was")
def _returned(scene):
    for app, ann in scene.desks.items():
        back_at(ann, scene.view["before"][app])
