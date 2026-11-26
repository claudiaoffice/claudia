"""File ▸ Manage ▸ My Role… (hand over, accept, leave) and Delete in the list of documents of the front page: steps of
``claudiaoffice-log/specs/document-file/my-role-and-delete.feature`` (UX-95, D1608)."""

from __future__ import annotations

import re

from conftest import Person, World, eventually
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/document-file/my-role-and-delete.feature")

DIALOG = ".modal"
LIST = "[data-testid=server-documents]"


def _assert(ok: bool, what) -> None:
    assert ok, what


def my_role(person: Person, choice: str | None = None) -> None:
    """File ▸ Manage ▸ My Role…, and the choice ``choice`` in it."""
    person.menu("File", "Manage", "My Role")
    dialog = person.page.locator(DIALOG, has=person.page.locator("[data-testid=my-role]"))
    dialog.wait_for()
    if choice:
        dialog.get_by_role("button", name=choice).click()


def confirm_password(person: Person, button: str) -> None:
    dialog = person.page.locator(DIALOG)
    dialog.locator("input[type=password]").fill(person.password)
    dialog.get_by_role("button", name=button, exact=True).click()


def ben_opens(world: World) -> Person:
    ben = world.people["Ben"]
    ben.open()
    ben.wait_until_open()
    return ben


def to_the_list(person: Person) -> None:
    """The front page, as a person who just closed a document or opened the address."""
    person.page.goto(person.url + "/" + person.query, wait_until="domcontentloaded")
    person.page.wait_for_selector(LIST)


def row(person: Person):
    """The line of this person's document in the list on this server."""
    name = person.page.locator(".name", has_text=re.compile(f"^{re.escape(person.document)}$"))
    return person.page.locator(f"{LIST} li", has=name)


def press_delete(person: Person) -> None:
    row(person).get_by_role("button", name=f"Delete {person.document} from the server…").click()


def confirm_delete(person: Person) -> None:
    """The Delete dialog of the list, filled in with this person's name and password and confirmed."""
    dialog = person.page.locator(DIALOG, has=person.page.locator("[data-testid=delete-from-list]"))
    dialog.locator("input[name=delete-user]").fill(person.name.lower())
    dialog.locator("input[type=password]").fill(person.password)
    dialog.get_by_role("button", name="Delete for good").click()


def cannot_open(person: Person) -> None:
    person.open()
    person.page.wait_for_selector("form .error[role=alert]")


# -- the document and its people ---------------------------------------------------------------------------------
@given("a new composes document in which I am Ann, an owner")
def _new_document(world):
    world.join("Ann").create()


@given("a new composes document in which I am Ann, an owner, and Ben is an editor")
def _new_document_with_ben(world):
    world.join("Ann").create()
    world.ann.share(world.join("Ben"), "editor")


# -- My Role… ------------------------------------------------------------------------------------------------------
@when(parsers.parse('I choose File ▸ Manage ▸ My Role… and hand the document over to "{name}" with my password'))
def _hand_over(world, name):
    ann = world.ann
    my_role(ann, "Hand Over…")
    ann.page.locator(f"{DIALOG} select").select_option(name)
    confirm_password(ann, "Ask them to take over")


@then(parsers.parse("I am told that {name} has been asked to take over the document"))
def _told_asked(world, name):
    lead = world.ann.page.locator(f"{DIALOG} .lead")
    eventually(lambda: _assert(f"{name} has been asked to take over" in lead.inner_text(), lead.inner_text()))


@when("Ben opens the document, chooses File ▸ Manage ▸ My Role… and accepts with his password")
def _accept(world):
    ben = ben_opens(world)
    my_role(ben, "Accept Ownership…")
    confirm_password(ben, "Accept")
    ben.page.wait_for_selector(f'{DIALOG} :text("You are now the owner")')
    ben.page.locator(DIALOG).get_by_role("button", name="Done").click()


@then("Ben's My Role… says that he is an owner of the document")
def _ben_is_owner(world):
    ben = world.people["Ben"]
    ben.wait_until_open()
    eventually(
        lambda: (my_role(ben), _assert("an owner" in ben.page.inner_text("[data-testid=my-role]"), "not an owner"))
    )


@when("Ben opens the document, chooses File ▸ Manage ▸ My Role… and leaves it with his password")
def _leave(world):
    ben = ben_opens(world)
    my_role(ben, "Leave the Document…")
    confirm_password(ben, "Leave document")


@then("Ben is back at the list of documents")
def _ben_at_the_list(world):
    world.people["Ben"].page.wait_for_selector("input[name=document]")


@then("Ben cannot open the document any more")
def _ben_cannot_open(world):
    cannot_open(world.people["Ben"])


# -- Delete in the list ------------------------------------------------------------------------------------------
@when("I close the document and press Delete for it in the list on this server")
def _close_and_press_delete(world):
    ann = world.ann
    ann.menu("File", "Close")
    ann.page.wait_for_selector(LIST)
    press_delete(ann)


@when("I confirm with my name and password")
def _confirm(world):
    confirm_delete(world.ann)


@then("the document is no longer in the list on this server")
def _not_in_list(world):
    eventually(lambda: _assert(row(world.ann).count() == 0, "the document is still listed"))


@then("nobody can open it any more")
def _nobody_can_open(world):
    cannot_open(world.ann)


@when("Ben goes to the list of documents, presses Delete for the document and confirms with his name and password")
def _ben_deletes(world):
    ben = world.people["Ben"]
    to_the_list(ben)
    press_delete(ben)
    confirm_delete(ben)


@then("Ben is told that only an owner can delete it")
def _ben_told(world):
    error = world.people["Ben"].page.locator(f"{DIALOG} .error[role=alert]")
    eventually(lambda: _assert("only an owner" in error.inner_text(), error.inner_text()))


@then("the document is still in the list on this server")
def _still_listed(world):
    ben = world.people["Ben"]
    ben.page.locator(DIALOG).get_by_role("button", name="Cancel").click()
    assert row(ben).count() == 1
