"""The steps of ``claudiaoffice-log/specs/server/refusals.feature`` (CODE-78, D1510): a document's refusal said in the
language the person chose. One server of all three apps; the tabs of a workbook's sheets and of a presentation's slides
are named the same way, by a double-click and the name dialog.

"I work in German" is what a person does who chose German: the choice is kept in the browser, and the document is opened
again with it. Steps after it find things by where they are, not by their English words.
"""

from __future__ import annotations

import pytest
from conftest import Person, World, eventually
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/server/refusals.feature")

TABS = ".foot [role=tab]"


@pytest.fixture
def world(suite_world: World) -> World:
    """Every scenario here runs on the server of all three apps."""
    return suite_world


def _name_tab(person: Person, index: int, name: str) -> None:
    """Double-click the tab at ``index`` and give it ``name`` in the dialog that opens."""
    person.page.locator(TABS).nth(index).dblclick()
    field = person.page.locator(".modal input")
    field.fill(name)
    field.press("Enter")
    person.page.locator(TABS).nth(index).filter(has_text=name).wait_for(timeout=5000)


def _tab_names(person: Person) -> list[str]:
    return [text.strip() for text in person.page.locator(TABS).all_inner_texts()]


@given(parsers.parse('a workbook with the sheets "{first}" and "{second}"'))
def _workbook(world: World, first: str, second: str) -> None:
    ann = world.join("Ann", app="computes")
    ann.create()
    _name_tab(ann, 0, first)
    ann.page.click(".foot .add")  # a new sheet is named as it is made
    field = ann.page.locator(".modal input")
    field.fill(second)
    field.press("Enter")
    ann.page.locator(TABS).filter(has_text=second).wait_for(timeout=5000)


@given(parsers.parse('a presentation with the slides "{first}" and "{second}"'))
def _presentation(world: World, first: str, second: str) -> None:
    ann = world.join("Ann", app="creates")
    ann.create()
    _name_tab(ann, 0, first)
    ann.page.click(".foot .add")
    ann.page.locator(TABS).nth(1).wait_for(timeout=5000)
    _name_tab(ann, 1, second)


@given("I work in German")
def _german(world: World) -> None:
    ann = world.ann
    ann.page.evaluate("localStorage.setItem('claudia:locale', 'de')")
    ann.type_login()  # the front page, now in German
    ann.page.press("input[name=password]", "Enter")
    ann.wait_until_open()


@when(parsers.parse('I rename the {kind} "{old}" to "{new}"'))
def _rename(world: World, kind: str, old: str, new: str) -> None:  # noqa: ARG001
    page = world.ann.page
    page.locator(TABS).filter(has_text=old).first.dblclick()
    field = page.locator(".modal input")
    field.fill(new)
    field.press("Enter")


@then(parsers.parse('I am told "{words}"'))
def _told(world: World, words: str) -> None:
    def shown() -> None:
        assert words in world.ann.notices(), world.ann.notices()

    eventually(shown)


@then(parsers.parse('the {kind} are still called "{first}" and "{second}"'))
def _still_called(world: World, kind: str, first: str, second: str) -> None:  # noqa: ARG001
    assert _tab_names(world.ann) == [first, second]
