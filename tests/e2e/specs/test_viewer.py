"""The steps of ``claudiaoffice-log/specs/document-file/viewer.feature`` (D1261, D1262, E2.11) and of
``login-wait.feature`` (D1266, E2.7): two windows of one real server, a person who may only look, and wrong passwords.
"""

from __future__ import annotations

from conftest import PASSWORD
from playwright.sync_api import expect
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/document-file/viewer.feature")
scenarios("../../../claudiaoffice-log/specs/document-file/login-wait.feature")


# -- the document and its people ---------------------------------------------------------------------------------
@given('a new composes document "plan" in which I am Ann, an owner')
def _new_document(world):
    world.join("Ann").create()


@given(parsers.parse('the text has the paragraph "{words}"'))
def _paragraph(world, words):
    page = world.ann.page
    page.click("[data-testid=text]")
    page.keyboard.type(words)
    page.wait_for_function("document.querySelector('.health.open')")


@given("Vera is a viewer of the document")
def _vera_is_a_viewer(world):
    ann = world.ann
    ann.page.click('.menus .title:text-is("File")')
    ann.page.click('.menus .drop [role=menuitem]:has-text("Manage")')
    ann.page.click('.menus [role=menuitem]:has-text("Share…")')
    dialog = ann.page.locator(".modal")
    dialog.get_by_label("Name", exact=True).fill("vera")
    dialog.locator("input[name=share-password]").fill(world.join("Vera").password)
    dialog.locator("select").select_option("viewer")
    dialog.get_by_role("button", name="Add person").click()
    ann.page.wait_for_selector('.added li:has-text("vera (viewer)")')
    dialog.get_by_role("button", name="Done").click()


@given("Vera has the document open")
def _vera_has_it_open(world):
    world.people["Vera"].open()
    world.people["Vera"].wait_until_open()


@given("Ann has closed the document")
def _ann_closed(world):
    world.ann.leave()


# -- looking -------------------------------------------------------------------------------------------------------
@when("Vera opens the document")
def _vera_opens(world):
    world.people["Vera"].open()


@when("Ann opens the document again")
def _ann_opens_again(world):
    world.ann.open()
    world.ann.wait_until_open()


@when(parsers.parse('Ann adds the paragraph "{words}"'))
def _ann_adds(world, words):
    page = world.ann.page
    page.click("[data-testid=text]")
    page.keyboard.press("Control+End")
    page.keyboard.press("Enter")
    page.keyboard.type(words)


@then(parsers.parse('Vera sees the paragraph "{words}"'))
def _vera_sees(world, words):
    vera = world.people["Vera"]
    vera.wait_until_open()
    vera.page.locator("[data-testid=text] [data-paragraph]", has_text=words).first.wait_for(timeout=10000)


@then("Vera's side panel says that history and chat are for the document's editors")
def _viewer_note(world):
    note = world.people["Vera"].page.locator("[data-testid=viewer-note]")
    note.wait_for(timeout=5000)
    assert "History and chat are for the document's editors" in note.inner_text()


@then("Vera's side panel lists no history")
def _no_history(world):
    vera = world.people["Vera"].page
    assert vera.locator("[data-testid=viewer-note]").count() == 1
    assert vera.locator("section.history").count() == 0, "a viewer's panel has no history section"
    assert vera.locator("[data-testid=replay-bar]").count() == 0


@then("Vera is told that an editor or owner has to open it first")
def _told_to_wait(world):
    dialog = world.people["Vera"].page.locator("[data-testid=waiting-for-an-editor]")
    dialog.wait_for(timeout=10000)
    assert "An editor or owner has to open this document first" in dialog.inner_text()


@then("Vera's window does not give up")
def _does_not_give_up(world):
    vera = world.people["Vera"].page
    vera.wait_for_timeout(4000)
    assert vera.locator("[data-testid=waiting-for-an-editor]").count() == 1
    assert vera.locator("[data-testid=text]").count() == 0


@then(parsers.parse('Vera\'s window opens it by itself and shows "{words}"'))
def _vera_gets_in(world, words):
    vera = world.people["Vera"]
    vera.wait_until_open(timeout=60000)
    assert any(words in line for line in vera.paragraphs())


# -- wrong passwords -----------------------------------------------------------------------------------------------
def _wrong(world, times: int) -> None:
    person = world.ann
    person.type_login("Wrong-Pass-1")
    for _ in range(times):
        person.press_open()
        person.page.wait_for_selector(".error[role=alert]", state="visible")
        person.page.wait_for_timeout(300)


@when("I try to open the document with a wrong password four times")
@given("I tried a wrong password four times")
def _four_wrong(world):
    _wrong(world, 4)


@when("I try once more")
def _once_more(world):
    world.ann.press_open()


@when("I try once more with my own password")
def _once_more_right(world):
    page = world.ann.page
    page.fill("input[name=password]", PASSWORD)
    world.ann.press_open()


@then(parsers.parse('I am told "{sentence}"'))
def _told(world, sentence):
    note = world.ann.page.locator("[data-testid=login-wait]")
    note.wait_for(timeout=5000)
    assert sentence in note.inner_text()


@then("I am told to wait, and the document stays closed")
def _told_to_wait_closed(world):
    world.ann.page.locator("[data-testid=login-wait]").wait_for(timeout=5000)
    assert world.ann.page.locator("[data-testid=text]").count() == 0


@then("the Open button cannot be pressed")
def _button_waits(world):
    assert world.ann.page.locator('button[type=submit]:text-is("Open")').is_disabled()


@when("the wait is over")
def _wait_over(world):
    expect(world.ann.page.locator('button[type=submit]:text-is("Open")')).to_be_enabled(timeout=8000)


@when("I open the document with my own password")
def _open_with_mine(world):
    page = world.ann.page
    page.fill("input[name=password]", PASSWORD)
    world.ann.press_open()


@then("the document is open")
def _is_open(world):
    world.ann.wait_until_open()
