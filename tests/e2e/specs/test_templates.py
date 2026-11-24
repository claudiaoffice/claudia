"""Templates: the steps of ``claudiaoffice-log/specs/creates/templates.feature`` (E10.4, E10.5, E10.22–E10.25).

What a person does is done in the browser: the administrator's Templates page, the New presentation cards of the front
page, Format ▸ Template ▸ Change theme…, Change template… and Save as template…. What a person cannot see (which layouts
and styles a presentation holds, who may open it) is read from the server with ``snapshot`` and ``hello``, as any client
does. The setup of a scenario (the templates the server already has) is put there over the administrator's HTTP routes.

Every scenario has a server of its own with one administrator, "anna", so that what one adds or removes cannot reach
another. Scenarios whose steps have no code yet skip, and say which step it was; two of the approved @core scenarios are
among them because the product cannot do what their steps say yet: no menu changes a layout of a presentation or puts a
slide on another layout (the layout editor is a later story), so "I change a layout…" and "slides on 'Two lists'…"
cannot be driven from the outside.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import BROWSER, PASSWORD, SHOTS, eventually
from live import server
from pytest_bdd import given, parsers, scenarios, then, when
from test_administrators import put_administrators
from test_greeting import BUILT, SKIP

from claudia_core import ChangeStyle, CreateStyle, Document, MemoryStore, SetRole, StyleDef
from claudia_creates import DefineLayout, HideLayout, SlideModel, TemplateInfo
from claudia_server.template_library import SUFFIX, slug, template_file

scenarios("../../../claudiaoffice-log/specs/creates/templates.feature")

ADMIN, ADMIN_PASSWORD = "anna", "Anna has a password 1"
THREE_LAYOUTS = ("Title", "Two lists", "Title only")


# -- the files of templates --------------------------------------------------------------------------------------------


def make_template(
    name: str, layouts: tuple[str, ...] = THREE_LAYOUTS, purpose: str = "", language: str = "en"
) -> bytes:
    """The file of a template: ``layouts`` and, so that a theme has something to give, a bigger body text, a style of
    its own and a red accent."""
    doc = Document(SlideModel.empty(), store=MemoryStore())
    doc.execute(
        HideLayout("basic", True), author="spec"
    )  # a template with layouts of its own does not offer Basic first
    for index, layout in enumerate(layouts):
        doc.execute(DefineLayout(f"l{index}", layout), author="spec")
    doc.execute(ChangeStyle("body-text", {"font-size": "30px"}), author="spec")
    doc.execute(SetRole("accent", "#aa0000"), author="spec")
    doc.execute(
        CreateStyle(StyleDef("big-number", "Big number", "one number", "body-text", {"font-size": "120px"})),
        author="spec",
    )
    info = TemplateInfo(name, purpose or f"For {name.lower()}s", language)
    return template_file(doc.model, info, exporter="spec", exported_at="2026-11-24T10:00:00Z")


# -- one server, one administrator, one browser ------------------------------------------------------------------------


class Lab:
    """A server of its own with one administrator, a browser page, and what the steps remember."""

    def __init__(self, browser, folder: Path):
        self.folder = folder
        self.live = None
        self._stack = contextlib.ExitStack()
        put_administrators(folder / "state", ADMIN, password=ADMIN_PASSWORD)
        self.live = self._stack.enter_context(server(folder, "--web", str(BUILT)))
        self.context = browser.new_context(viewport={"width": 1360, "height": 900}, accept_downloads=True)
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on(
            "console",
            lambda m: m.type == "error" and "status of 40" not in m.text and self.errors.append(f"console: {m.text}"),
        )
        # every notice the page shows, kept: a notice goes away by itself after a few seconds
        self.context.add_init_script(
            "window.__notices = []; new MutationObserver(() => document.querySelectorAll('.toast').forEach(e => {"
            " if (!e.dataset.kept) { e.dataset.kept = '1'; window.__notices.push(e.textContent.trim()) } }))"
            ".observe(document, {childList: true, subtree: true})"
        )
        self.document = "talk"
        self.user = "ann"
        self.template_files: dict[str, bytes] = {}

    @property
    def url(self) -> str:
        return self.live.url

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.context.close()
        self._stack.close()

    # -- the administrator's routes: the setup of a scenario --

    def admin_token(self) -> str:
        import urllib.request

        request = urllib.request.Request(
            self.url + "/api/admin/login",
            data=json.dumps({"name": ADMIN, "password": ADMIN_PASSWORD}).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as answer:
            return json.loads(answer.read())["token"]

    def server_has(self, *names: str) -> None:
        """Add the templates called ``names`` to the server's library, as the administrator does."""
        import urllib.request

        token = self.admin_token()
        for name in names:
            data = make_template(name)
            self.template_files[name] = data
            request = urllib.request.Request(
                self.url + "/api/admin/templates",
                data=data,
                headers={"authorization": f"Bearer {token}", "content-type": "application/octet-stream"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as answer:
                assert answer.status == 201

    def templates_of_server(self) -> list[str]:
        import urllib.request

        with urllib.request.urlopen(self.url + "/api/templates?locale=en", timeout=30) as answer:
            return [t["name"] for t in json.loads(answer.read())["templates"]]

    # -- the front page and the presentation --

    def front_page(self) -> None:
        page = self.page
        page.goto(self.url + "/", wait_until="domcontentloaded")
        page.fill("input[name=document]", self.document)
        page.fill("input[name=user]", self.user)
        page.fill("input[name=password]", PASSWORD)
        kinds = page.locator(".kinds")
        if kinds.count():
            kinds.get_by_role("radio", name="Slides").click()

    def choose_new(self) -> None:
        """Create document: with templates on the server, a presentation asks which one to start from."""
        self.front_page()
        self.page.click("text=Create document")
        self.page.wait_for_selector('.modal :text("New presentation")')

    def start_from(self, name: str) -> None:
        """From the cards: the template called ``name``, and into the presentation."""
        self.choose_new()
        self.page.locator(".modal .card").filter(
            has=self.page.locator(".name", has_text=re.compile(f"^{name}$"))
        ).click()
        chosen = self.page.locator(".modal .card.on .name").inner_text()
        assert chosen == name, f"the card of “{name}” was not chosen, “{chosen}” is"
        self.page.locator(".modal button.primary").click()
        self.page.wait_for_selector("[data-testid=recovery-key]")
        self.page.check(".modal input[type=checkbox]")
        self.page.click('.modal button:text-is("Continue")')
        self.page.wait_for_selector("[data-testid=slide]")
        self.page.wait_for_function("document.querySelector('.health.open')")

    def shot(self, what: str) -> None:
        """A picture of the page as it is, for a person to look at later (the end of a scenario is only the end)."""
        SHOTS.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(SHOTS / f"templates-{what}.png"))

    def menu(self, title: str, *path: str) -> None:
        self.page.click(f'.menus .title:text-is("{title}")')
        *submenus, entry = path
        for submenu in submenus:
            self.page.locator(f'.menus .drop [role=menuitem]:has-text("{submenu}")').first.hover()
        self.page.locator(f'.menus .drop [role=menuitem]:has-text("{entry}")').first.click()

    # -- what a person cannot see --

    def state(self) -> dict:
        """The presentation as the server holds it: slides, layouts, slide_layouts, styles, palette."""
        with self.live.socket("creates", self.document) as session:
            session.hello(user=self.user, password=PASSWORD)
            return session.ok("snapshot")["state"]

    def refused_for(self, user: str) -> bool:
        """Is ``user`` refused when she opens the document?"""
        with self.live.socket("creates", self.document) as session:
            return not session.call("hello", user=user, password=PASSWORD).get("ok")

    def add_slides(self, count: int) -> None:
        with self.live.socket("creates", self.document) as session:
            session.hello(user=self.user, password=PASSWORD)
            for _ in range(count):
                session.ok("add_slide")
            for slide in session.ok("slides"):
                session.ok("set_slide_notes", slide=slide["id"], notes=f"Secret words of {slide['id']}")


@pytest.fixture
def lab(browser, request) -> Iterator[Lab]:
    if SKIP:
        pytest.skip(SKIP)
    if BROWSER == "firefox":
        pytest.skip("these scenarios are not tagged @firefox")
    with tempfile.TemporaryDirectory(prefix="claudia-templates-") as folder:
        made = Lab(browser, Path(folder))
        try:
            yield made
        finally:
            SHOTS.mkdir(parents=True, exist_ok=True)
            slug_ = re.sub(r"\W+", "-", request.node.name)[:80]
            with contextlib.suppress(Exception):
                made.page.screenshot(path=str(SHOTS / f"{slug_}.png"))
            errors = list(made.errors)
            made.close()
            assert not errors, "the browser reported errors:\n" + "\n".join(errors)


def colours(state: dict) -> dict[str, str]:
    return {colour["id"]: colour["colour"].lower() for colour in state["palette"]}


def layout_names(state: dict) -> list[str]:
    return [layout["name"] for layout in state["layouts"]]


# -- given -------------------------------------------------------------------------------------------------------------


@given(parsers.parse('the server has the templates "{first}" and "{second}"'))
def server_has_two(lab, first, second):
    lab.server_has(first, second)


@given(parsers.parse('the template "{name}" has three layouts and its own styles and colours'))
def template_with_layouts(lab, name):
    lab.server_has(name)


@given(parsers.parse('I am the administrator and have the file of "{name}"'))
def administrator_with_a_file(lab, name):
    lab.template_files[name] = make_template(name, purpose="Talks of twenty minutes")


@given(parsers.parse('the server has the template "{name}"'))
def server_has_one(lab, name):
    lab.server_has(name)


@given(parsers.parse('a presentation with twelve slides and the server\'s template "{name}"'))
def twelve_slides_and_a_template(lab, name):
    lab.server_has(name)
    lab.start_from("Basic")
    lab.add_slides(11)


@given("a presentation with eight layouts, its own styles and colours, and twelve slides with text")
def eight_layouts_twelve_slides(lab):
    eight = tuple(f"Layout {n}" for n in range(1, 9))
    lab.template_files["Eight"] = make_template("Eight", eight)
    import urllib.request

    request = urllib.request.Request(
        lab.url + "/api/admin/templates",
        data=lab.template_files["Eight"],
        headers={"authorization": f"Bearer {lab.admin_token()}", "content-type": "application/octet-stream"},
        method="POST",
    )
    urllib.request.urlopen(request, timeout=60).close()
    lab.start_from("Eight")
    lab.add_slides(11)
    assert len(lab.state()["slides"]) == 12
    assert len([layout for layout in lab.state()["layouts"] if layout["name"].startswith("Layout ")]) == 8


# -- when --------------------------------------------------------------------------------------------------------------


@when("I choose File ▸ New in creates")
def choose_new(lab):
    lab.choose_new()


@when("I start a new presentation from it")
def start_from_the_template(lab):
    lab.start_from("Conference talk")
    said = lab.page.evaluate("window.__notices")  # a notice about a file comes with the slide, which is shown by now
    assert not said, f"the page said something about a file nobody gave: {said}"


@when(
    parsers.parse(
        'I choose Format ▸ Template ▸ Save as template…, name it "{name}", say what it is for and choose English'
    )
)
def save_as_template(lab, name):
    lab.menu("Format", "Template", "Save as Template…")
    dialog = lab.page.locator(".modal")
    dialog.get_by_label("Name", exact=True).fill(name)
    dialog.get_by_label("What it is for").fill("Talks of twenty minutes")
    dialog.get_by_label("Language").select_option("en")
    lab.shot("save-as-template")
    with lab.page.expect_download() as download:
        dialog.get_by_role("button", name="Save file…").click()
    lab.saved = (download.value.suggested_filename, Path(download.value.path()).read_bytes())


@when("I choose Server settings ▸ Templates ▸ Add template… and the check passes")
def add_in_settings(lab):
    page = lab.page
    page.goto(lab.url + "/admin/")
    page.fill("input[autocomplete=username]", ADMIN)
    page.fill("input[type=password]", ADMIN_PASSWORD)
    page.click('button:text-is("Sign in")')
    page.click("nav >> text=Templates")
    page.wait_for_selector('h1:text-is("Templates")')
    name = "Conference talk"
    page.set_input_files(
        "input[type=file]",
        {"name": f"{slug(name)}{SUFFIX}", "mimeType": "application/zip", "buffer": lab.template_files[name]},
    )
    page.wait_for_selector(f'.modal :text("{name}")')
    page.locator(".modal button.primary").click()
    page.wait_for_selector(f'tbody th:text-is("{name}")')


@when(parsers.parse("I remove it in Server settings ▸ Templates"))
def remove_in_settings(lab):
    page = lab.page
    page.goto(lab.url + "/admin/")
    page.fill("input[autocomplete=username]", ADMIN)
    page.fill("input[type=password]", ADMIN_PASSWORD)
    page.click('button:text-is("Sign in")')
    page.click("nav >> text=Templates")
    page.wait_for_selector('h1:text-is("Templates")')
    page.get_by_role("button", name="Remove Weekly report").click()
    page.locator(".modal button.danger").click()
    page.wait_for_selector('tbody th:text-is("Weekly report")', state="detached")


@when("I choose Format ▸ Template ▸ Change theme…, choose its theme and confirm after the preview")
def change_theme(lab):
    lab.before = lab.state()
    lab.menu("Format", "Template", "Change Theme…")
    dialog = lab.page.locator(".modal")
    dialog.locator("select").select_option(label="Conference talk")
    dialog.get_by_text(
        "stay as they are"
    ).first.wait_for()  # the preview says the layouts and the slides are left alone
    lab.shot("change-theme")
    dialog.get_by_role("button", name="Change theme").click()
    lab.page.wait_for_selector(".modal", state="detached")


# -- then --------------------------------------------------------------------------------------------------------------


@then('I see a card for "Basic" first, then one for each template, each with what it is for')
def cards_in_order(lab):
    names = lab.page.locator(".modal .card .name").all_text_contents()
    assert names == ["Basic", "Conference talk", "Weekly report"], names
    for card in lab.page.locator(".modal .card").all():
        assert card.locator(".purpose").inner_text().strip(), "a card says nothing of what its template is for"


@then("I have one slide, on the first layout of the template")
def one_slide_on_the_first_layout(lab):
    state = lab.state()
    assert [s["name"] for s in state["slides"]] == ["Slide 1"]
    first = state["slide_layouts"][state["slides"][0]["id"]]
    assert next(layout["name"] for layout in state["layouts"] if layout["id"] == first) == THREE_LAYOUTS[0], state


@then("the presentation has those three layouts, those styles and those colours")
def has_the_content_of_the_template(lab):
    state = lab.state()
    assert set(THREE_LAYOUTS) <= set(layout_names(state)), layout_names(state)
    styles = {style["id"]: style for style in state["styles"]}
    assert styles["body-text"]["css"]["font-size"] == "30px"
    assert styles["big-number"]["name"] == "Big number"
    assert colours(state)["accent"] == "#aa0000"


@then("I am the only one who can open it")
def only_me(lab):
    assert lab.refused_for("vera"), "somebody who was never added could open the presentation"


@then("I get a file with the eight layouts, the styles and the colours")
def file_has_the_layouts(lab):
    filename, data = lab.saved
    assert filename == "conference-talk.claudia-export.zip", filename
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        names = sorted(bundle.namelist())
        assert names == ["content.json", "export.json", "format"], names
        content = json.loads(bundle.read("content.json"))
    text = json.dumps(content)
    for n in range(1, 9):
        assert f"Layout {n}" in text, f"Layout {n} is not in the file"
    assert "big-number" in text and "#aa0000" in text.lower()
    assert "Talks of twenty minutes" in text, "what it is for is not in the file"


@then("it holds nothing of the twelve slides: not their text, their notes, their pictures, their history or the chat")
def file_has_no_slides(lab):
    _, data = lab.saved
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        everything = b"".join(bundle.read(name) for name in bundle.namelist()).decode(errors="replace")
        assert sorted(bundle.namelist()) == ["content.json", "export.json", "format"], (
            "history, chat or pictures came along"
        )
    assert "Secret words" not in everything, "the notes of the slides are in the file"
    assert not json.loads(zipfile.ZipFile(io.BytesIO(data)).read("content.json")).get("slides"), "slides came along"


@then('"Conference talk" is in the list of templates, and anyone who chooses File ▸ New sees it')
def listed_and_offered(lab):
    assert "Conference talk" in lab.templates_of_server()
    lab.choose_new()
    assert "Conference talk" in lab.page.locator(".modal .card .name").all_text_contents()


@then("it is no longer in File ▸ New, and presentations started from it are not touched")
def gone_from_new(lab):
    assert "Weekly report" not in lab.templates_of_server()
    # only Basic is left, so there is nothing to choose from: a new presentation is made without asking
    lab.front_page()
    lab.page.click("text=Create document")
    lab.page.wait_for_selector("[data-testid=recovery-key]")
    assert lab.page.locator(".modal .card").count() == 0


@then("the styles and the colours are those of the theme, matched by what they are for")
def theme_taken(lab):
    state = lab.state()
    styles = {style["id"]: style for style in state["styles"]}
    assert styles["body-text"]["css"]["font-size"] == "30px"
    assert "big-number" in styles
    assert colours(state)["accent"] == "#aa0000"


@then("the layouts and every slide's layout are as before")
def layouts_as_before(lab):
    state = lab.state()
    assert state["layouts"] == lab.before["layouts"]
    assert state["slide_layouts"] == lab.before["slide_layouts"]
    assert len(state["slides"]) == 12


@then("one Undo takes it all back")
def one_undo(lab):
    lab.page.keyboard.press("Control+z")
    eventually(lambda: _assert_equal(lab.state()["palette"], lab.before["palette"]))
    assert {s["id"]: s["css"] for s in lab.state()["styles"]} == {s["id"]: s["css"] for s in lab.before["styles"]}


def _assert_equal(left, right) -> None:
    assert left == right
