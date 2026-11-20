"""File ▸ Manage ▸ Share… as the place where an owner lowers a role or removes a person, and what the other window
shows: steps of ``claudiaoffice-log/specs/container/keys-and-people.feature`` (D1263, D1274, E2.3).

Scenarios tagged ``@unit`` are run by the unit tests they name, not here."""

from __future__ import annotations

import re

from playwright.sync_api import expect
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/container/keys-and-people.feature")

DIALOG = ".modal"


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


@given("Ben is an editor of the document")
def _ben_is_an_editor(world):
    ann = world.ann
    _open_share(ann)
    dialog = ann.page.locator(DIALOG)
    dialog.get_by_label("Name", exact=True).fill("ben")
    dialog.locator("input[name=share-password]").fill(world.join("Ben").password)
    dialog.locator("select").last.select_option("editor")
    dialog.get_by_role("button", name="Add person").click()
    ann.page.wait_for_selector('.added li:has-text("ben (editor)")')
    dialog.get_by_role("button", name="Done").click()


@given("Ben has the document open")
def _ben_has_it_open(world):
    world.people["Ben"].open()
    world.people["Ben"].wait_until_open()


# -- the Share dialog ----------------------------------------------------------------------------------------------
def _open_share(person) -> None:
    person.menu("File", "Manage")
    person.page.click('.menus [role=menuitem]:has-text("Share…")')
    person.page.wait_for_selector(f'{DIALOG} :text("Share this document")')


def _row(person, name: str):
    """The line of one person in the list; her own line says "· you" after the name."""
    who = person.page.locator(".who", has_text=re.compile(rf"^{re.escape(name)}\b"))
    return person.page.locator(".roster li", has=who)


@when("I choose File ▸ Manage ▸ Share…")
def _share(world):
    _open_share(world.ann)


@when(parsers.parse('I choose File ▸ Manage ▸ Share… and change what {name} may do to "{role}"'))
def _lower(world, name, role):
    _open_share(world.ann)
    value = "viewer" if role == "only look" else "editor"
    _row(world.ann, name).locator("select").select_option(value)


@when(parsers.parse("I choose File ▸ Manage ▸ Share… and press Remove for {name}"))
def _remove(world, name):
    _open_share(world.ann)
    _row(world.ann, name).get_by_role("button", name="Remove").click()


@when("Ann removes Ben")
def _ann_removes_ben(world):
    _remove(world, "ben")
    world.ann.page.locator(DIALOG).get_by_role("button", name="Remove ben").click()
    expect(world.ann.page.locator(".roster li", has_text="ben")).to_have_count(0, timeout=20000)
    world.ann.page.locator(DIALOG).get_by_role("button", name="Done").click()


@when("I press Change to only look")
def _confirm_lower(world):
    world.ann.page.locator(DIALOG).get_by_role("button", name="Change to only look").click()


@when(parsers.parse("I press Remove {name}"))
def _confirm_remove(world, name):
    world.ann.page.locator(DIALOG).get_by_role("button", name=f"Remove {name}").click()


@when("I press Cancel at the question")
def _cancel(world):
    world.ann.page.locator(DIALOG).get_by_role("button", name="Cancel").click()


@when("Ben opens the document")
def _ben_opens(world):
    world.people["Ben"].open()
    world.people["Ben"].wait_until_open()


# -- what is asked -------------------------------------------------------------------------------------------------
@then(parsers.parse('I am asked "{question}" and told that ben cannot read what is written from now on'))
def _asked_lower(world, question):
    box = world.ann.page.locator(DIALOG)
    expect(box).to_contain_text(question)
    expect(box).to_contain_text("cannot read what is written to the history or the chat")


@then(parsers.parse('I am asked "{question}" and told that private notes of this person are deleted'))
def _asked_remove(world, question):
    box = world.ann.page.locator(DIALOG)
    expect(box).to_contain_text(question.replace("“plan”", f"“{world.ann.document}”"))  # the spec's "plan" is any name
    expect(box).to_contain_text("Any private notes of this person are deleted.")


# -- what the dialog shows ------------------------------------------------------------------------------------------
@then(parsers.parse('the dialog lists "{name}" as "{role}"'))
def _lists(world, name, role):
    row = _row(world.ann, name)
    expect(row).to_have_count(1, timeout=20000)
    if role == "owner":
        expect(row.locator(".role")).to_have_text("owner")
    else:
        expect(row.locator("select option:checked")).to_have_text(role)


@then("only Ben has a way to be removed")
def _only_ben_removable(world):
    buttons = world.ann.page.locator(f'{DIALOG} .roster li button:text-is("Remove")')
    expect(buttons).to_have_count(1)
    expect(_row(world.ann, "ben").get_by_role("button", name="Remove")).to_have_count(1)


@then(parsers.parse('the dialog does not list "{name}" any more'))
def _not_listed(world, name):
    expect(world.ann.page.locator(".roster li", has_text=name)).to_have_count(0, timeout=20000)


@then("Ben's File ▸ Manage ▸ Share… entry cannot be chosen")
def _ben_has_no_share(world):
    ben = world.people["Ben"]
    ben.page.click('.menus .title:text-is("File")')
    ben.page.click('.menus .drop [role=menuitem]:has-text("Manage")')
    expect(ben.page.locator('.menus [role=menuitem]:has-text("Share…")')).to_be_disabled()


# -- Ben's window ------------------------------------------------------------------------------------------------------
@then(parsers.parse('Ben\'s window says "{sentence}"'))
def _ben_is_told(world, sentence):
    expect(world.people["Ben"].page.locator(".toast", has_text=sentence)).to_be_visible(timeout=20000)


@then("Ben's side panel says that history and chat are for the document's editors")
def _ben_viewer_note(world):
    note = world.people["Ben"].page.locator("[data-testid=viewer-note]")
    note.wait_for(timeout=20000)
    assert "History and chat are for the document's editors" in note.inner_text()


@then("Ben cannot open the document with his password")
def _ben_refused(world):
    ben = world.people["Ben"]
    ben.open()
    ben.page.wait_for_selector(".error[role=alert]", state="visible", timeout=20000)
    assert ben.page.locator("[data-testid=text]").count() == 0


# -- Ann carries on ----------------------------------------------------------------------------------------------
@then(parsers.parse('Ann\'s window shows the paragraph "{words}"'))
def _ann_sees(world, words):
    world.ann.page.locator("[data-testid=text] [data-block]", has_text=words).first.wait_for(timeout=10000)


@then("Ann can keep typing and the paragraph she types is saved")
def _ann_types(world):
    page = world.ann.page
    page.click("[data-testid=text]")
    page.keyboard.press("Control+End")
    page.keyboard.press("Enter")
    page.keyboard.type("After the renewal")
    page.wait_for_function("document.querySelector('.health.open')", timeout=20000)
    page.wait_for_timeout(2000)  # typing is sent in small batches; give the last one the time to reach the server
    world.ann.leave()
    world.ann.open()
    world.ann.wait_until_open()
    assert any("After the renewal" in line for line in world.ann.paragraphs())
