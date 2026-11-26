"""The step code of the scenarios in ``claudiaoffice-log/specs``: one real server, one real browser, no mocks.

How a scenario becomes a test, and what is on purpose:

* A ``.feature`` file is bound by ``scenarios(...)`` in a ``test_*.py`` here. Its tags become pytest markers, so the
  runner picks ``-m core`` or ``-m "core or extended"`` (``./run-e2e.sh core``).
* A step nobody wrote code for yet **skips** the scenario and says which step it was ("not automated yet"), so the
  list of skips is the honest list of what the specs promise and the tests do not yet check.
* ``@needs-decision`` scenarios are skipped (the owner has not decided what they should do). ``@pending:<id>`` scenarios
  are written and *expected to fail* until the work behind ``<id>`` is done; they are strict, so the day they pass
  the run fails and the tag has to be taken off.
* After every scenario, whatever it did: no error in the browser's console, and a screenshot of the end state in
  ``$CLAUDIA_E2E_SHOTS`` for a person to look at (the "obvious to a human" check that a table drawn twice would fail).
* ``$CLAUDIA_E2E_BROWSER`` is ``chromium`` (default) or ``firefox``; with ``firefox`` only ``@firefox`` scenarios run.
  ``$CLAUDIA_CHROMIUM`` points at a Chromium that is already there; ``$CLAUDIA_E2E_HEADED`` shows the window.
"""

from __future__ import annotations

import contextlib
import hashlib
import itertools
import json
import os
import re
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest_bdd.scenario import get_step_function

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tests/e2e: live.py and test_greeting.py

from live import ROOT, server  # noqa: E402
from test_greeting import BUILT, NOT_BUILT, chromium_at  # noqa: E402

BROWSER = os.environ.get("CLAUDIA_E2E_BROWSER", "chromium")
SHOTS = Path(os.environ.get("CLAUDIA_E2E_SHOTS", ROOT / ".claudia" / "e2e" / "shots"))
HEADED = bool(os.environ.get("CLAUDIA_E2E_HEADED"))
PASSWORD = "Ann has a password 1"
PASSWORDS = {"Ann": PASSWORD, "Vera": "Vera has a password 1"}
TAGS_FOR_MARKERS = ("core", "extended", "firefox", "two-users", "desktop", "needs-decision")
#: What shows that a document of an app is open, and what a new document of it is called on the front page.
READY = {"composes": "[data-testid=text]", "computes": "[role=grid]", "creates": "[data-testid=slide]"}
KIND_WORDS = {"composes": "Text", "computes": "Table", "creates": "Slides"}


_config: pytest.Config | None = None


def eventually(check, seconds: float = 10.0, *, page=None) -> None:
    """Run ``check`` (it asserts) until it holds, for at most ``seconds``; the last failure is the answer.

    A check that reads what a page heard on the wire (``Person.events``, ``Person.answers``) passes its ``page``: the
    sync Playwright API hands a page's websocket frames to Python only while a Playwright call runs, so between tries
    this waits on the page, not in ``time.sleep``, which would leave the frames undelivered."""
    end = time.monotonic() + seconds
    while True:
        try:
            check()
            return
        except AssertionError:
            if time.monotonic() > end:
                raise
            if page is None:
                time.sleep(0.1)
            else:
                page.wait_for_timeout(100)


def steady(person: Person, read, tries: int = 40):
    """What ``read()`` gives once two reads a quarter of a second apart agree: a view that has stopped moving, an
    object the server has put in its place, a list that has stopped filling."""
    last = read()
    for _ in range(tries):
        person.page.wait_for_timeout(250)
        now = read()
        if now == last:
            return now
        last = now
    return last


def pytest_configure(config: pytest.Config) -> None:
    global _config  # noqa: PLW0603 - the tag hook below gets no config, and a tag like @pending:N2 must be registered
    _config = config
    config.addinivalue_line("filterwarnings", "ignore::pytest.PytestUnknownMarkWarning")  # @pending:N2 and the like
    for tag in TAGS_FOR_MARKERS:
        config.addinivalue_line("markers", f"{tag}: scenario tag, see claudiaoffice-log/specs/README.md")


def _tags(item: pytest.Item) -> list[str]:
    return [mark.name for mark in item.iter_markers()]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    keep = []
    for item in items:
        tags = _tags(item)
        if BROWSER == "firefox" and "firefox" not in tags:
            continue
        elsewhere = [t for t in tags if t.startswith(("unit:", "io:", "e2e:"))]
        if elsewhere:  # a scenario that no browser is needed for: its test is the file the tag names
            item.add_marker(pytest.mark.skip(reason=f"checked by {elsewhere[0]}"))
        if "needs-decision" in tags:
            item.add_marker(pytest.mark.skip(reason="waits for the owner's decision (@needs-decision)"))
        pending = [t for t in tags if t.startswith("pending:")]
        if pending:
            item.add_marker(pytest.mark.xfail(reason=f"written first, not built yet ({pending[0]})", strict=True))
        keep.append(item)
    items[:] = keep


def pytest_bdd_before_scenario(request, feature, scenario) -> None:  # noqa: ARG001
    """Skip a scenario with a step nobody wrote code for *before* its first step runs: its Background would otherwise
    make a document and open a browser page only to find that out."""
    for step in scenario.steps:
        if get_step_function(request=request, step=step) is None:
            pytest.skip(f"not automated yet: {step.keyword} {step.name}")


def pytest_bdd_apply_tag(tag: str, function) -> bool | None:
    """Tags like ``@pending:N2`` or ``@app:composes`` are not valid Python names; give them a mark of their own."""
    if ":" in tag or "-" in tag:
        if _config is not None:
            _config.addinivalue_line("markers", f"{tag}: scenario tag, see claudiaoffice-log/specs/README.md")
        getattr(pytest.mark, tag)(function)
        return True
    return None


def _web_server(*options: str) -> Iterator[str]:
    """A real server with the built web app, for the whole run; its URL."""
    if NOT_BUILT:
        pytest.skip(NOT_BUILT)
    with (
        tempfile.TemporaryDirectory(prefix="claudia-specs-") as folder,
        server(Path(folder), *options, "--web", str(BUILT)) as running,
    ):
        yield running.url


@pytest.fixture(scope="session")
def stack() -> Iterator[str]:
    """One server of composes."""
    yield from _web_server("--model", "claudia_composes:TextModel")


@pytest.fixture(scope="session")
def suite() -> Iterator[str]:
    """One server of all three apps (D430)."""
    yield from _web_server()


def _launch(play):
    """The browser the run asked for: Firefox, or Chromium from ``$CLAUDIA_CHROMIUM`` or from Playwright's own copy."""
    if BROWSER == "firefox":
        return play.firefox.launch(headless=not HEADED)
    return play.chromium.launch(executable_path=chromium_at(), headless=not HEADED)


@pytest.fixture(scope="module")
def browser() -> Iterator[object]:
    """One browser per file of scenarios, shut down when the last of them is done. Not for the whole run (PROC-35): a
    Playwright that is still open keeps an event loop running in this thread, and the other end-to-end tests start their
    own Playwright, which refuses to start inside it."""
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as play:
        try:
            opened = _launch(play)
        except Error:
            # Skipped with a reason, like test_greeting.py, not failed: a computer without the browser is not a broken
            # app (PROC-48).
            hint = ", or set $CLAUDIA_CHROMIUM" if BROWSER == "chromium" else ""
            pytest.skip(f"no {BROWSER} for playwright (`uv run playwright install {BROWSER}`{hint})")
        try:
            yield opened
        finally:
            opened.close()


_counter = itertools.count(1)


class Person:
    """One person with one page in one document: what the steps drive."""

    def __init__(self, browser, url: str, document: str, name: str, app: str = "composes", query: str = ""):
        self.name = name
        self.query = query  # the page's address after its path: the menus' trial setting (D1647), say
        self.app = app
        self.password = PASSWORDS.get(name, PASSWORD)
        self.document = document
        self.context = browser.new_context(viewport={"width": 1360, "height": 900})
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("console", lambda m: m.type == "error" and self.errors.append(f"console: {m.text}"))
        self.sent: list[str] = []  # the methods of the requests this page sent, in order
        self.events: list[dict] = []  # what the server pushed to this page: {"event": ..., "data": ...}
        self.answers: list[dict] = []  # the results of this page's requests that are objects, in order
        self.page.on("websocket", self._listen)
        # every notice the page shows, kept: a notice goes away by itself after a few seconds
        self.context.add_init_script(
            "window.__notices = []; new MutationObserver(() => document.querySelectorAll('.toast').forEach(e => {"
            " if (!e.dataset.kept) { e.dataset.kept = '1'; window.__notices.push(e.textContent.trim()) } }))"
            ".observe(document, {childList: true, subtree: true})"
        )
        self.url = url

    def _listen(self, socket) -> None:
        def sent(frame: str) -> None:
            with contextlib.suppress(ValueError, TypeError, AttributeError):
                self.sent.append(json.loads(frame)["method"])

        def pushed(frame: str) -> None:
            with contextlib.suppress(ValueError, TypeError):
                message = json.loads(frame)
                if isinstance(message, dict) and "event" in message:
                    self.events.append(message)
                elif isinstance(message, dict) and isinstance(message.get("result"), dict):
                    self.answers.append(message["result"])

        socket.on("framesent", sent)
        socket.on("framereceived", pushed)

    def create(self) -> None:
        page = self.page
        with page.expect_response(lambda answer: answer.url.endswith("/api/docs")) as listing:
            page.goto(self.url + "/" + self.query, wait_until="domcontentloaded")
        page.fill("input[name=document]", self.document)
        page.fill("input[name=user]", self.name.lower())
        page.fill("input[name=password]", self.password)
        # A server of several apps asks which kind of document (D430). Whether it does is in its list, not in what the
        # page shows so far: the choice appears once the list has come, which on a busy machine was after the form had
        # been filled, and Create then asked for a kind instead of making the document (PROC-55).
        if len(listing.value.json().get("apps", [])) > 1:
            page.locator(".kinds").get_by_role("radio", name=KIND_WORDS[self.app]).click()
        page.click("text=Create document")
        page.wait_for_selector("[data-testid=recovery-key]")
        page.check(".modal input[type=checkbox]")
        page.click('.modal button:text-is("Continue")')
        self.wait_until_open()

    def type_login(self, password: str | None = None) -> None:
        """The Open dialog of this person's document, filled in and not yet sent."""
        page = self.page
        page.goto(self.url + "/" + self.query, wait_until="domcontentloaded")
        page.fill("input[name=document]", self.document)
        page.fill("input[name=user]", self.name.lower())
        page.fill("input[name=password]", self.password if password is None else password)

    def press_open(self) -> None:
        self.page.click('button[type=submit]:text-is("Open")')

    def open(self, password: str | None = None) -> None:
        """Open the document that exists, as a person who has a name and a password in it."""
        self.type_login(password)
        self.press_open()

    def finish_import(self, document: str | None = None) -> None:
        """The import dialog that a file given to the front page opens: the new document's name (``document``, else
        this person's), this person's login, Open, and the new document's recovery key put away."""
        dialog = self.page.locator(".modal")
        dialog.locator("input[name=import-name]").fill(document or self.document)
        dialog.locator("input[name=import-user]").fill(self.name.lower())
        dialog.locator("input[name=import-password]").fill(self.password)
        dialog.locator("button[type=submit]").click()
        self.page.wait_for_selector("[data-testid=recovery-key]", timeout=30000)  # a new document: its key first
        self.page.check(".modal input[type=checkbox]")
        self.page.click('.modal button:text-is("Continue")')

    def wait_until_open(self, timeout: float = 15000) -> None:
        self.page.wait_for_selector(READY[self.app], timeout=timeout)
        self.page.locator(".health.open").wait_for(state="attached", timeout=timeout)

    def notices(self) -> list[str]:
        """Every notice this page has shown since it was loaded, in order."""
        return self.page.evaluate("window.__notices || []")

    def share(self, person: Person, role: str) -> None:
        """Add ``person`` with ``role`` (File ▸ Manage ▸ Share…), with the password that person will use."""
        self.menu("File", "Manage", "Share…")
        dialog = self.page.locator(".modal")
        dialog.get_by_label("Name", exact=True).fill(person.name.lower())
        dialog.locator("input[name=share-password]").fill(person.password)
        dialog.locator("select").last.select_option(role)  # the last: the role of the person being added
        dialog.get_by_role("button", name="Add person").click()
        self.page.wait_for_selector(f'.added li:has-text("{person.name.lower()} ({role})")')
        dialog.get_by_role("button", name="Done").click()

    def reopen(self) -> None:
        """Reload the page and open the document again: a reload leaves a person at the front page."""
        self.page.reload()
        self.open()
        self.wait_until_open()

    def leave(self) -> None:
        """Close the window of the document, as a person who is done with it."""
        self.page.goto("about:blank")

    def menu(self, title: str, *path: str) -> None:
        """Choose ``title`` ▸ ``path``: each entry but the last opens a submenu."""
        self.page.click(f'.menus .title:text-is("{title}")')
        *submenus, entry = path
        for submenu in submenus:
            self.menu_item(submenu).hover()
        self.menu_item(entry).click()

    def menu_item(self, label: str):
        """The open menu's entry whose label starts with ``label``: "Text Box", not "Undo · Added a text box"."""
        return self.page.locator(".menus .drop [role=menuitem]", has_text=re.compile("^" + re.escape(label))).first

    def paragraphs(self) -> list[str]:
        return self.page.eval_on_selector_all(
            "[data-testid=text] [data-paragraph]", "els => els.map(e => e.textContent.trim())"
        )

    def order(self) -> list[str]:
        """The paragraphs and tables of the text in the order they are on the page; a table is ``TABLE``."""
        return self.page.evaluate(
            """() => [...document.querySelectorAll('[data-testid=text] [data-paragraph], [data-testid=table]')]
                .map(e => e.getAttribute('data-testid') === 'table' ? 'TABLE' : e.textContent.trim())"""
        )

    def caret(self) -> tuple[str, int] | None:
        """The words of the paragraph the caret is in, and how far into them it is; ``None`` when it is not in the
        words of the text (in a box of a table, in the chat, nowhere)."""
        found = self.page.evaluate(
            """() => {
              const s = getSelection(), text = document.querySelector('[data-testid=text]')
              if (!s || !s.focusNode || !text.contains(s.focusNode) || document.activeElement !== text) return null
              const node = s.focusNode.nodeType === 1 ? s.focusNode : s.focusNode.parentElement
              const paragraph = node.closest('[data-paragraph]')
              if (!paragraph) return null
              const r = document.createRange(); r.setStart(paragraph, 0); r.setEnd(s.focusNode, s.focusOffset)
              return [paragraph.textContent.trim(), r.toString().length]
            }"""
        )
        return (found[0], found[1]) if found else None

    def boxes(self) -> list[str]:
        return self.page.eval_on_selector_all("[data-box]", "els => els.map(e => e.value)")

    def focused_box(self) -> str | None:
        return self.page.evaluate("document.activeElement && document.activeElement.getAttribute('data-box')")

    def close(self) -> None:
        self.context.close()


class World:
    """What a scenario has: the people in it, by name, and what it remembers between steps."""

    def __init__(self, browser, url: str):
        self.browser = browser
        self.url = url
        self.people: dict[str, Person] = {}
        self.me: Person | None = None
        self.last_error: str | None = None
        self.query = ""  # what every page of the scenario adds to its address (the menus' trial setting, D1647)

    def join(self, name: str, app: str | None = None) -> Person:
        """A person with a page of their own; the second person and later share the first one's document (and app)."""
        if self.me is not None:
            assert app in (None, self.me.app), f"{name} joins a {self.me.app} document, not a {app} one"
        document = self.me.document if self.me is not None else f"spec-{next(_counter)}-{os.getpid()}"
        app = self.me.app if self.me is not None else (app or "composes")
        person = Person(self.browser, self.url, document, name, app, self.query)
        self.people[name] = person
        self.me = self.me or person
        return person

    @property
    def ann(self) -> Person:
        assert self.me is not None, "no document yet"
        return self.me


@pytest.fixture
def world(browser, stack, request) -> Iterator[World]:
    """The people of a scenario on the composes server."""
    yield from looked_after(World(browser, stack), request)


@pytest.fixture
def suite_world(browser, suite, request) -> Iterator[World]:
    """The people of a scenario on the server of all three apps."""
    yield from looked_after(World(browser, suite), request)


def shot_name(test: str) -> str:
    """The file name (without the person and extension) of a test's screenshots: the test's name, and for a long one
    the start of the test's name, its example (``[...]``, which says the app) and a short digest of the whole, so that
    no two tests share a file (PROC-56). Plain ASCII, so any file system takes it."""

    def slug(text: str) -> str:
        return re.sub(r"\W+", "-", text, flags=re.ASCII).strip("-")

    if len(slug(test)) <= 80:
        return slug(test)
    name, _, example = test.partition("[")
    example = slug(example)[:50]
    digest = hashlib.sha256(test.encode()).hexdigest()[:8]
    return "-".join(part for part in (slug(name)[: 70 - len(example)], example, digest) if part)


def looked_after(made: World, request) -> Iterator[World]:
    """Hand the world to the scenario; afterwards a screenshot of every page, and no errors in any browser console."""
    yield made
    SHOTS.mkdir(parents=True, exist_ok=True)
    slug = shot_name(request.node.name)
    for name, person in made.people.items():
        with contextlib.suppress(Exception):  # a page that is gone has no picture; the test result is what matters
            person.page.screenshot(path=str(SHOTS / f"{slug}-{name.lower()}.png"))
    errors = [e for person in made.people.values() for e in person.errors]
    for person in made.people.values():
        person.close()
    assert not errors, "the browser reported errors:\n" + "\n".join(errors)
