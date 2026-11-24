"""The steps of ``claudiaoffice-log/specs/server/claude-as-ai-provider.feature`` (E7.11, D32, D264, D266, D154): the
administrator's AI page in a real browser, on a real server that is started with the address of the fake Anthropic
(never settable from the page). Nothing here reaches the real Anthropic.

A scenario that needs a step nobody has written (a saved key, a question asked in a document) skips with its words.
"""

from __future__ import annotations

import contextlib
import re
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import BROWSER, SHOTS
from live import server
from playwright.sync_api import expect
from pytest_bdd import given, parsers, scenarios, then, when
from test_administrators import PASSWORD, put_administrators
from test_greeting import BUILT, SKIP

from claudia_ai.testing import FakeAnthropic

scenarios("../../../claudiaoffice-log/specs/server/claude-as-ai-provider.feature")

FAILS = {
    "refuses every key": None,  # a key the fake does not know
    "says the credit balance is used up": "credit_used_up",
    "says the rate limit was reached": "rate_limited",
    "says it is overloaded": "overloaded",
}


class Admin:
    """One server, the fake Anthropic behind it, and the administrator's page."""

    def __init__(self, browser, url: str, fake: FakeAnthropic):
        self.fake = fake
        self.context = browser.new_context(viewport={"width": 1100, "height": 1000})
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        # a refused apply is a 400 the page shows in words: the browser logs it as a failed resource, not an error
        self.page.on(
            "console",
            lambda m: m.type == "error" and "status of 400" not in m.text and self.errors.append(m.text),
        )
        self.url = url

    def sign_in(self, name: str) -> None:
        self.page.goto(self.url + "/admin/")
        self.page.fill("input[autocomplete=username]", name)
        self.page.fill("input[type=password]", PASSWORD)
        self.page.click("button:text-is('Sign in')")
        self.page.wait_for_selector("nav")

    def ai(self):
        return self.page.locator("main, .admin-app")

    def provider(self, name: str) -> None:
        self.page.get_by_role("group", name="AI provider").get_by_role("button", name=name, exact=True).click()


@pytest.fixture
def admin(browser, request) -> Iterator[Admin]:
    if SKIP:
        pytest.skip(SKIP)
    if BROWSER == "firefox":
        pytest.skip("these scenarios are not tagged @firefox")
    with (
        FakeAnthropic("sk-ant-test-a7Q2", answer=lambda messages: "ok") as fake,
        tempfile.TemporaryDirectory(prefix="claudia-provider-") as folder,
    ):
        put_administrators(Path(folder) / "state", "anna")
        with server(Path(folder), "--web", str(BUILT), "--anthropic-base-url", fake.url) as live:
            made = Admin(browser, live.url, fake)
            yield made
            SHOTS.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"\W+", "-", request.node.name)[:80]
            with contextlib.suppress(Exception):
                made.page.screenshot(path=str(SHOTS / f"{slug}.png"))
            errors = list(made.errors)
            made.context.close()
            assert not errors, "the browser reported errors:\n" + "\n".join(errors)


@given(
    parsers.parse('a server with the administrator "anna" and a fake Anthropic that accepts the provider key "{key}"')
)
def _server(admin, key):
    assert key in admin.fake.keys


@given(parsers.parse('I am signed in to the server settings as "{name}"'))
def _signed_in(admin, name):
    admin.sign_in(name)


@given("the server has no model folder")
def _no_model_folder(admin):
    pass  # the server of these scenarios is started without one


@when("I open the AI page")
def _open_ai_page(admin):
    admin.page.get_by_role("navigation").get_by_text("AI", exact=True).click()
    admin.page.wait_for_selector("[data-testid=ai-now]")


@then(parsers.parse('it says "{label}" and "{name}"'))
def _it_says(admin, label, name):
    expect(admin.page.locator("[data-testid=ai-now]")).to_contain_text(label)
    expect(admin.page.locator("[data-testid=ai-now]")).to_contain_text(name)


@then('it shows no "remote" badge')
def _no_remote(admin):
    expect(admin.page.locator("[data-testid=ai-now] .remote")).to_have_count(0)


@then('it says "Last error: none"')
def _no_error(admin):
    expect(admin.page.locator("[data-testid=ai-last-error]")).to_have_text("Last error: none")


@then(parsers.parse('I can choose between "{a}", "{b}" and "{c}"'))
def _choices(admin, a, b, c):
    group = admin.page.get_by_role("group", name="AI provider")
    for name in (a, b, c):
        expect(group.get_by_role("button", name=name, exact=True)).to_be_visible()


@then('the chosen one is the one named after "Answering now:"')
def _chosen_is_named(admin):
    pressed = admin.page.get_by_role("group", name="AI provider").locator("[aria-pressed=true]").inner_text()
    expect(admin.page.locator("[data-testid=ai-now]")).to_contain_text(pressed)


@when(parsers.parse('I choose "{name}"'))
def _choose(admin, name):
    admin.provider(name)


@then("I am asked to paste the key of my Anthropic account")
def _asked_for_key(admin):
    expect(admin.page.get_by_placeholder("Paste the key of your Anthropic account")).to_be_visible()


@then(parsers.parse('the model is "{model}"'))
def _model(admin, model):
    expect(admin.page.locator("input[list=claude-models]")).to_have_value(model)


@then(parsers.re(r'I read "(?P<words>[^"]+)"$'))
def _read(admin, words):
    expect(admin.page.locator("main, body")).to_contain_text(words)


@then("I read that the owner of each document must also allow Claude there")
def _read_owners(admin):
    expect(admin.page.locator("[data-testid=ai-approval]")).to_contain_text(
        "the owner of each document must also allow Claude"
    )


@then('"Apply" is not available')
def _apply_unavailable(admin):
    expect(admin.page.locator("button:text-is('Apply')")).to_be_disabled()


@when(parsers.parse('I paste the key "{key}"'))
def _paste_key(admin, key):
    admin.page.get_by_placeholder("Paste the key of your Anthropic account").fill(key)


@when("I confirm that document content is sent to Anthropic")
def _confirm(admin):
    admin.page.locator("[data-testid=ai-approval] input[type=checkbox]").check()


@when("I press Apply")
def _apply(admin):
    admin.page.click("button:text-is('Apply')")


@then(parsers.parse('it says "Answering now:" and "{name}" with a "remote" badge'))
def _says_remote(admin, name):
    now = admin.page.locator("[data-testid=ai-now]")
    expect(now).to_contain_text("Answering now:")
    expect(now).to_contain_text(name)
    expect(now.locator(".remote")).to_have_text("remote")


@then("the fake Anthropic was asked one test question")
def _one_test_question(admin):
    assert len(admin.fake.requests) == 1, admin.fake.requests


@given(parsers.re("the fake Anthropic (?P<fails>" + "|".join(map(re.escape, FAILS)) + ")$"))
def _fake_fails(admin, fails):
    if FAILS[fails]:
        admin.fake.fail(FAILS[fails])
    else:
        admin.fake.keys.clear()


@then(parsers.parse('it says "Answering now:" and the local model, with no "remote" badge'))
def _says_local(admin):
    expect(admin.page.locator("[data-testid=ai-now]")).to_contain_text("Answering now:")
    expect(admin.page.locator("[data-testid=ai-now] .remote")).to_have_count(0)


@then("nothing was changed")
def _nothing_changed(admin):
    expect(admin.page.locator("[data-testid=ai-refused]")).to_contain_text("Nothing was changed")
