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
import itertools
import os
import re
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest_bdd.scenario import get_step_function

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tests/e2e: live.py and test_greeting.py

from live import ROOT, server  # noqa: E402
from test_greeting import BUILT, SKIP, chromium_at  # noqa: E402

BROWSER = os.environ.get("CLAUDIA_E2E_BROWSER", "chromium")
SHOTS = Path(os.environ.get("CLAUDIA_E2E_SHOTS", ROOT / ".claudia" / "e2e" / "shots"))
HEADED = bool(os.environ.get("CLAUDIA_E2E_HEADED"))
PASSWORD = "Ann has a password 1"
PASSWORDS = {"Ann": PASSWORD, "Vera": "Vera has a password 1"}
TAGS_FOR_MARKERS = ("core", "extended", "firefox", "two-users", "desktop", "needs-decision")


_config: pytest.Config | None = None


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


@pytest.fixture(scope="session")
def stack() -> Iterator[str]:
    """One server of composes with the built web app, for the whole run; its URL."""
    if SKIP:
        pytest.skip(SKIP)
    with (
        tempfile.TemporaryDirectory(prefix="claudia-specs-") as folder,
        server(Path(folder), "--model", "claudia_composes:TextModel", "--web", str(BUILT)) as running,
    ):
        yield running.url


@pytest.fixture(scope="module")
def browser() -> Iterator[object]:
    """One browser per file of scenarios, shut down when the last of them is done. Not for the whole run (PROC-35): a
    Playwright that is still open keeps an event loop running in this thread, and the other end-to-end tests start their
    own Playwright, which refuses to start inside it."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as play:
        if BROWSER == "firefox":
            opened = play.firefox.launch(headless=not HEADED)
        elif chromium_at():
            opened = play.chromium.launch(executable_path=chromium_at(), headless=not HEADED)
        else:
            opened = play.chromium.launch(headless=not HEADED)
        try:
            yield opened
        finally:
            opened.close()


_counter = itertools.count(1)


class Person:
    """One person with one page in one document: what the steps drive."""

    def __init__(self, browser, url: str, document: str, name: str):
        self.name = name
        self.password = PASSWORDS.get(name, PASSWORD)
        self.document = document
        self.context = browser.new_context(viewport={"width": 1360, "height": 900})
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("console", lambda m: m.type == "error" and self.errors.append(f"console: {m.text}"))
        self.url = url

    def create(self) -> None:
        page = self.page
        page.goto(self.url + "/", wait_until="domcontentloaded")
        page.fill("input[name=document]", self.document)
        page.fill("input[name=user]", self.name.lower())
        page.fill("input[name=password]", self.password)
        page.click("text=Create document")
        page.wait_for_selector("[data-testid=recovery-key]")
        page.check(".modal input[type=checkbox]")
        page.click('.modal button:text-is("Continue")')
        page.wait_for_selector("[data-testid=text]")
        page.wait_for_function("document.querySelector('.health.open')")

    def type_login(self, password: str | None = None) -> None:
        """The Open dialog of this person's document, filled in and not yet sent."""
        page = self.page
        page.goto(self.url + "/", wait_until="domcontentloaded")
        page.fill("input[name=document]", self.document)
        page.fill("input[name=user]", self.name.lower())
        page.fill("input[name=password]", self.password if password is None else password)

    def press_open(self) -> None:
        self.page.click('button[type=submit]:text-is("Open")')

    def open(self, password: str | None = None) -> None:
        """Open the document that exists, as a person who has a name and a password in it."""
        self.type_login(password)
        self.press_open()

    def wait_until_open(self, timeout: float = 15000) -> None:
        self.page.wait_for_selector("[data-testid=text]", timeout=timeout)
        self.page.wait_for_function("document.querySelector('.health.open')", timeout=timeout)

    def leave(self) -> None:
        """Close the window of the document, as a person who is done with it."""
        self.page.goto("about:blank")

    def menu(self, title: str, entry: str) -> None:
        self.page.click(f'.menus .title:text-is("{title}")')
        self.page.click(f'.menus .drop [role=menuitem]:has-text("{entry}")')

    def paragraphs(self) -> list[str]:
        return self.page.eval_on_selector_all(
            "[data-testid=text] [data-block]", "els => els.map(e => e.textContent.trim())"
        )

    def order(self) -> list[str]:
        """The paragraphs and tables of the text in the order they are on the page; a table is ``TABLE``."""
        return self.page.evaluate(
            """() => [...document.querySelectorAll('[data-testid=text] [data-block], [data-testid=table]')]
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
              const block = node.closest('[data-block]')
              if (!block) return null
              const r = document.createRange(); r.setStart(block, 0); r.setEnd(s.focusNode, s.focusOffset)
              return [block.textContent.trim(), r.toString().length]
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

    def join(self, name: str) -> Person:
        """A person with a page of their own; the second person and later share the first one's document."""
        document = self.me.document if self.me is not None else f"spec-{next(_counter)}-{os.getpid()}"
        person = Person(self.browser, self.url, document, name)
        self.people[name] = person
        self.me = self.me or person
        return person

    @property
    def ann(self) -> Person:
        assert self.me is not None, "no document yet"
        return self.me


@pytest.fixture
def world(browser, stack, request) -> Iterator[World]:
    made = World(browser, stack)
    yield made
    SHOTS.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"\W+", "-", request.node.name)[:80]
    for name, person in made.people.items():
        with contextlib.suppress(Exception):  # a page that is gone has no picture; the test result is what matters
            person.page.screenshot(path=str(SHOTS / f"{slug}-{name.lower()}.png"))
    errors = [e for person in made.people.values() for e in person.errors]
    for person in made.people.values():
        person.close()
    assert not errors, "the browser reported errors:\n" + "\n".join(errors)
