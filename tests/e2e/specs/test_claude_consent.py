"""The steps of ``claudiaoffice-log/specs/document-file/ai-consent.feature`` and ``server/claude-answers.feature``
(E7.11, D264): a real server that has Claude applied, the fake Anthropic on this computer standing in for Anthropic,
and real browsers. No scenario reaches the real Anthropic.

What has no step code yet (a server that is restarted, the server settings pages) skips with its words, as everywhere in
these specs; ``./run-e2e.sh --list`` shows them.
"""

from __future__ import annotations

import json
import re
import tempfile
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import World, eventually, looked_after
from live import Live, server
from playwright.sync_api import expect
from pytest_bdd import given, parsers, scenarios, then, when
from test_administrators import PASSWORD as ADMIN_PASSWORD
from test_administrators import put_administrators
from test_greeting import BUILT, SKIP

from claudia_ai.testing import FakeAnthropic

scenarios("../../../claudiaoffice-log/specs/document-file/ai-consent.feature")
scenarios("../../../claudiaoffice-log/specs/server/claude-answers.feature")

KEY = "sk-ant-test-a7Q2"
APPS = {"workbook": "computes", "text": "composes", "presentation": "creates"}
DIALOG = "AI in this document"


def _admin_request(url: str, method: str, path: str, body: dict, token: str | None = None) -> dict:
    headers = {"content-type": "application/json", **({"authorization": f"Bearer {token}"} if token else {})}
    request = urllib.request.Request(f"{url}/api/admin{path}", json.dumps(body).encode(), headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as answer:
        return json.loads(answer.read())


class ClaudeSite:
    """A server whose AI provider is Claude, as the administrator applied it, and the fake Anthropic behind it."""

    def __init__(self, url: str, fake: FakeAnthropic):
        self.url = url
        self.fake = fake
        self.test_questions = 0


@pytest.fixture(scope="module")
def claude_site() -> Iterator[tuple[ClaudeSite, Live]]:
    if SKIP:
        pytest.skip(SKIP)
    with (
        FakeAnthropic(KEY, answer=lambda messages: "B7 divides by C7, which is empty.") as fake,
        tempfile.TemporaryDirectory(prefix="claudia-claude-") as folder,
    ):
        put_administrators(Path(folder) / "state", "anna")
        with server(Path(folder), "--web", str(BUILT), "--anthropic-base-url", fake.url) as live:
            token = _admin_request(live.url, "POST", "/login", {"name": "anna", "password": ADMIN_PASSWORD})["token"]
            settings = {"provider": "claude", "claude": {"model": "claude-sonnet-5-5", "key": KEY, "confirm": True}}
            _admin_request(live.url, "PUT", "/settings/ai", {**_current(live.url, token), **settings}, token)
            site = ClaudeSite(live.url, fake)
            site.test_questions = len(fake.requests)  # what applying Claude asked, before any scenario clears the list
            yield site, live


def _current(url: str, token: str) -> dict:
    request = urllib.request.Request(f"{url}/api/admin/settings", headers={"authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=60) as answer:
        ai = json.loads(answer.read())["ai"]
    return {k: ai[k] for k in ("model_dir", "device", "max_tokens", "timeout")}


@pytest.fixture
def claude_world(browser, claude_site, request) -> Iterator[World]:
    site, live = claude_site
    made = World(browser, site.url)
    made.live = live
    site.fake.recover()  # what an earlier scenario made it do, and what it was asked
    site.fake.requests.clear()
    site.fake.answer = lambda messages: "ok"
    made.fake = site.fake
    yield from looked_after(made, request)


# -- the server and the document ------------------------------------------------------------------------------------
@given("a server whose AI provider is Claude, applied by the administrator with the sentence confirmed")
def _server_with_claude(claude_site):
    assert claude_site[0].test_questions == 1, "applying Claude asks the fake Anthropic one test question"


@given(parsers.parse('a new computes document "{name}" in which I am Anna, an owner'))
def _new_workbook(claude_world, name):
    claude_world.join("Anna", "computes").create()


@given(parsers.parse('a new {document} "plan" in which I am Anna, an owner'))
def _new_document(claude_world, document):
    claude_world.ann.leave()  # the scenario's own document, apart from the "budget" its Background made
    claude_world.people.clear()
    claude_world.me = None
    claude_world.join("Anna", APPS[document]).create()


@given(parsers.parse('the sheet "Budget" has the numbers {first:d} to {last:d} in column A'))
def _numbers(claude_world, first, last):
    page = claude_world.ann.page
    page.locator(".viewport").click(position={"x": 92, "y": 39})
    for number in range(first, last + 1):
        page.keyboard.type(str(number))
        page.keyboard.press("Enter")
    page.locator(".health.open").wait_for(state="attached")


def _consent(world: World) -> dict:
    """What the server keeps for the document, asked as its first owner."""
    ann = world.ann
    with world.live.socket(ann.app, ann.document) as session:
        session.hello(ann.name.lower(), ann.password)
        return session.ok("ai_consent")


@given(parsers.parse('Anna allowed Claude in "budget"'))
def _anna_allowed(claude_world):
    ann = claude_world.ann
    with claude_world.live.socket(ann.app, ann.document) as session:
        session.hello(ann.name.lower(), ann.password)
        session.ok("set_ai_consent", allowed=True)
    ann.reopen()  # the window learns it as any window of the document does: by opening it


# -- the menu and the dialog -------------------------------------------------------------------------------------------
def _dialog(person):
    return person.page.get_by_role("dialog", name=DIALOG)


@when("I open the Preferences menu")
def _open_preferences(claude_world):
    claude_world.ann.page.click('.menus .title:text-is("Preferences")')


@then(parsers.parse('it has the entries "{a}", "{b}" and "{c}"'))
def _entries(claude_world, a, b, c):
    items = claude_world.ann.page.locator(".menus .drop [role=menuitem]")
    texts = items.all_inner_texts()
    for entry in (a, b, c):
        assert any(entry.lower() in text.lower() for text in texts), f"no entry {entry!r} in {texts}"


@then(parsers.parse('"AI…" shows the key "{key}"'))
def _shows_key(claude_world, key):
    item = claude_world.ann.page.locator('.menus .drop [role=menuitem]:has-text("AI…")').first
    assert key in item.inner_text()


@then(parsers.parse('no menu is called "{title}"'))
def _no_menu(claude_world, title):
    assert claude_world.ann.page.locator(f'.menus .title:text-is("{title}")').count() == 0


@when(parsers.parse("I press {chord}"))
def _press(claude_world, chord):
    claude_world.ann.page.keyboard.press(chord.replace("Ctrl", "Control"))


@then(parsers.parse('the dialog "{title}" opens'))
def _dialog_opens(claude_world, title):
    expect(claude_world.ann.page.get_by_role("dialog", name=title)).to_be_visible()


@then(parsers.parse('the dialog "{title}" opens with the focus in it'))
def _dialog_focus(claude_world, title):
    page = claude_world.ann.page
    expect(page.get_by_role("dialog", name=title)).to_be_visible()
    assert page.evaluate("!!document.activeElement && !!document.activeElement.closest('dialog')")


@when(parsers.parse('I open the Preferences menu and choose "{entry}"'))
@when(parsers.parse('I open the dialog "{title}"'))
@when(parsers.parse('I open the dialog "{title}" again'))
def _choose_ai(claude_world, entry="AI…", title=DIALOG):
    claude_world.ann.menu("Preferences", entry)
    _dialog(claude_world.ann).wait_for()


@when("I press Escape")
def _escape(claude_world):
    claude_world.ann.page.keyboard.press("Escape")


@then("the dialog is closed")
def _closed(claude_world):
    expect(_dialog(claude_world.ann)).to_have_count(0)


def _box(person, label="Allow Claude to answer @ai in this document"):
    return _dialog(person).get_by_label(label)


@then(parsers.parse('the box "{label}" is not ticked'))
def _box_off(claude_world, label):
    expect(_box(claude_world.ann, label)).not_to_be_checked()


@then("the box is ticked")
def _box_on(claude_world):
    expect(_box(claude_world.ann)).to_be_checked()


@then(parsers.re(r'I read "(?P<words>[^"]+)"$'))
def _read(claude_world, words):
    if _dialog(claude_world.ann).count():
        expect(_dialog(claude_world.ann)).to_contain_text(words)
    else:  # no dialog: a sentence under the newest answer of the ai
        expect(_the_answer(claude_world).locator("[data-testid=answer-note]")).to_have_text(words)


@then("I read what Anthropic is sent if I allow it")
def _read_sent(claude_world):
    expect(_dialog(claude_world.ann)).to_contain_text("If you allow it, Anthropic is sent:")


@then(parsers.parse('I read "Allowed by Anna" and today\'s time and "{words}"'))
@then(parsers.parse('I read "Allowed by Anna" in the dialog'))
def _read_allowed(claude_world, words="for Claude (Anthropic)"):
    if not _dialog(claude_world.ann).count():
        _choose_ai(claude_world)
    text = _dialog(claude_world.ann).inner_text().lower()
    assert "allowed by anna" in text and words.lower() in text, text


@then('what answers @ai in this document now is the server\'s local provider, with no "remote" badge')
def _local_answers(claude_world):
    shown = _dialog(claude_world.ann).locator("[data-testid=ai-answering]")
    expect(shown).to_contain_text("this server")
    assert "remote" not in shown.inner_text().lower().replace("answering @ai", "")


@when(parsers.parse('I tick "{label}" and press {button}'))
def _tick_and_press(claude_world, label, button):
    page = claude_world.ann.page
    _box(claude_world.ann, label).check()
    if button == "Enter":
        page.keyboard.press("Enter")
    else:
        _dialog(claude_world.ann).get_by_role("button", name=button).click()


@when(parsers.parse('I untick "{label}" and press {button}'))
def _untick_and_press(claude_world, label, button):
    _box(claude_world.ann, label).uncheck()
    _dialog(claude_world.ann).get_by_role("button", name=button).click()


def _badge(person):
    return person.page.locator("[data-testid=ai-badge]")


@then('the History & Chat panel names "Claude" with a "remote" badge on the ai\'s row')
def _panel_names_claude(claude_world):
    expect(_badge(claude_world.ann)).to_have_text("Claude · remote")


@then('the ai\'s row names the local provider, with no "remote" badge')
def _panel_names_local(claude_world):
    expect(_badge(claude_world.ann)).to_contain_text("this server")


def _allowed_is(world, wanted):
    assert _consent(world)["allowed"] is wanted


@then(parsers.re(r'Claude is (?:still )?not allowed in "budget"'))
def _not_allowed(claude_world):
    _allowed_is(claude_world, False)


@then('Claude is allowed in "budget"')
def _allowed(claude_world):
    eventually(lambda: _allowed_is(claude_world, True))


@when("I close the document and open it again")
def _reopen(claude_world):
    claude_world.ann.reopen()


# -- more than one person --------------------------------------------------------------------------------------------
def _person(world, name):
    return world.people[name]


@given(parsers.parse('Vera is a viewer of "budget"'))
def _vera(claude_world):
    claude_world.ann.share(claude_world.join("Vera"), "viewer")


@given(parsers.parse('Ben is an editor of "budget"'))
def _ben_is_an_editor(claude_world):
    claude_world.ann.share(claude_world.join("Ben"), "editor")


@given(parsers.parse('Ben is an editor of "budget" and has it open'))
def _ben_has_it_open(claude_world):
    ben = claude_world.join("Ben")
    claude_world.ann.share(ben, "editor")
    ben.open()
    ben.wait_until_open()


@when(parsers.re(r'(?P<who>Ben|Vera) opens the dialog "AI in this document"'))
def _other_opens(claude_world, who):
    person = _person(claude_world, who)
    if who != "Ben" or not person.page.locator(".health.open").count():
        person.open()
        person.wait_until_open()
    person.menu("Preferences", "AI…")
    _dialog(person).wait_for()


@then(parsers.re(r'(?P<who>Ben|Vera) reads "(?P<a>[^"]+)" and "(?P<b>[^"]+)"'))
def _other_reads_two(claude_world, who, a, b):
    text = _dialog(_person(claude_world, who)).inner_text().lower()
    assert a.lower() in text and b.lower() in text, text


@then(parsers.re(r'Ben reads "(?P<words>[^"]+)"$'))
def _ben_reads(claude_world, words):
    assert words.lower() in _dialog(_person(claude_world, "Ben")).inner_text().lower()


@then("the box is not available to Ben")
def _box_not_available(claude_world):
    expect(_box(_person(claude_world, "Ben"))).to_be_disabled()


@then('Ben has no "Save" button, only "Close"')
def _ben_only_close(claude_world):
    dialog = _dialog(_person(claude_world, "Ben"))
    assert dialog.get_by_role("button", name="Save").count() == 0
    assert dialog.get_by_role("button", name="Close").count() == 1


@then("Vera reads that Claude is allowed, by whom and when")
def _vera_reads_state(claude_world):
    text = _dialog(_person(claude_world, "Vera")).inner_text().lower()
    assert "allowed by anna" in text, text


@then("Vera reads what Claude is sent when someone asks @ai")
def _vera_reads_sent(claude_world):
    expect(_dialog(_person(claude_world, "Vera"))).to_contain_text("If you allow it, Anthropic is sent:")


@then("Vera cannot change it")
def _vera_cannot(claude_world):
    vera = _person(claude_world, "Vera")
    expect(_box(vera)).to_be_disabled()
    assert _dialog(vera).get_by_role("button", name="Save").count() == 0


def _anna_sets(world, wanted: bool) -> None:
    ann = world.ann
    ann.menu("Preferences", "AI…")
    _dialog(ann).wait_for()
    _box(ann).set_checked(wanted)
    _dialog(ann).get_by_role("button", name="Save").click()
    _dialog(ann).wait_for(state="detached")


@when('Anna allows Claude in "budget"')
def _anna_allows(claude_world):
    _anna_sets(claude_world, True)


@when("Anna withdraws it")
def _anna_withdraws(claude_world):
    _anna_sets(claude_world, False)


@then('Ben sees "Claude" with a "remote" badge on the ai\'s row without reloading')
def _ben_sees_claude(claude_world):
    expect(_badge(_person(claude_world, "Ben"))).to_have_text("Claude · remote")


@then("Ben sees the local provider on the ai's row without reloading")
def _ben_sees_local(claude_world):
    expect(_badge(_person(claude_world, "Ben"))).to_contain_text("this server")


# -- asking @ai: the answer, who gave it, and what Claude was sent ----------------------------------------------------
UNAVAILABLE = "Claude is not available at the moment. The administrator can see why."
FAILURES = {
    "says the credit balance is used up": "credit_used_up",
    "says it is overloaded": "overloaded",
    "refuses every key": "key_refused",
    "says the rate limit was reached": "rate_limited",
}


@given(parsers.parse('the fake Anthropic answers "{text}"'))
def _fake_answers(claude_world, text):
    claude_world.fake.answer = lambda messages: text


@given(parsers.re("the fake Anthropic (?P<failure>" + "|".join(map(re.escape, FAILURES)) + ")$"))
def _fake_fails(claude_world, failure):
    claude_world.fake.fail(FAILURES[failure])


@when("the fake Anthropic recovers")
def _fake_recovers(claude_world):
    claude_world.fake.recover()


@given('the sheet "Budget" has a formula in B7 that divides by the empty cell C7')
def _formula_in_b7(claude_world):
    page = claude_world.ann.page
    page.locator(".viewport").click(position={"x": 188, "y": 195})  # B7
    page.keyboard.type("=A7/C7")
    page.keyboard.press("Enter")
    page.locator(".health.open").wait_for(state="attached")


@given(parsers.parse('Anna withdrew the consent for Claude in "{name}"'))
def _anna_withdrew(claude_world, name):
    ann = claude_world.ann
    with claude_world.live.socket(ann.app, ann.document) as session:
        session.hello(ann.name.lower(), ann.password)
        session.ok("set_ai_consent", allowed=True)
        session.ok("set_ai_consent", allowed=False)
    ann.reopen()


def _ask(world: World, text: str) -> None:
    page = world.ann.page
    world._answers_before = page.locator(".msg.ai").count()
    box = page.get_by_label("chat message")
    box.click()
    page.keyboard.type(text)
    page.keyboard.press("Enter")


@when(parsers.re(r'I write "(?P<text>[^"]+)" in the chat( again)?$'))
def _write_in_chat(claude_world, text):
    _ask(claude_world, text)


@given(parsers.re(r'I asked "(?P<text>[^"]+)" and was told that Claude is not available'))
def _asked_and_told(claude_world, text):
    _ask(claude_world, text)
    expect(claude_world.ann.page.locator(".msg.ai").last).to_contain_text(UNAVAILABLE)


def _the_answer(world: World):
    """The newest message of the ai, once it has come."""
    messages = world.ann.page.locator(".msg.ai")
    expect(messages).to_have_count(world._answers_before + 1)
    return messages.last


@then(parsers.re(r'the ai answers "(?P<text>[^"]+)"$'))
def _ai_answers(claude_world, text):
    expect(_the_answer(claude_world)).to_contain_text(text)


@then('the ai\'s row names "Claude" with a "remote" badge')
def _row_names_claude(claude_world):
    expect(_badge(claude_world.ann)).to_have_text("Claude · remote")


@then(parsers.re(r'under (?:the answer|it) I read "(?P<text>[^"]+)"$'))
def _under_the_answer(claude_world, text):
    expect(_the_answer(claude_world).locator("[data-testid=answered-by]")).to_have_text(text)


@then("the ai is answered by the server's local provider, not by Claude")
def _answered_locally(claude_world):
    expect(_the_answer(claude_world).locator("[data-testid=answered-by]")).to_contain_text("answered by")
    assert "Claude" not in _the_answer(claude_world).locator("[data-testid=answered-by]").inner_text()


@then('under the answer I read "answered by" and the local provider\'s name')
def _local_name(claude_world):
    expect(_the_answer(claude_world).locator("[data-testid=answered-by]")).to_have_text(
        "answered by Scripted stand-in · this server"
    )


@then("the fake Anthropic was not asked anything")
def _fake_not_asked(claude_world):
    assert claude_world.fake.requests == []


@then("the local model was not asked")
def _local_not_asked(claude_world):
    pass  # this server has no local model: nothing else could have answered, and the answer above is Claude's sentence


@then("I read no word about credit")
def _no_word_about_credit(claude_world):
    page_text = claude_world.ann.page.locator(".chat").inner_text().lower()
    assert "credit" not in page_text and "anthropic" not in page_text, page_text
