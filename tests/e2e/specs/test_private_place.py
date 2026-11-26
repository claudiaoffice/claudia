"""The steps of ``desktop/private-place.feature`` that a browser checks (E8.5, D1623): a claudia server on this
computer, opened in a plain browser tab, is "Shared on this computer" -- the tab cannot tell whose it is, and "This
computer" is a name of the past. The file's other scenarios are checked by the unit tests their tags name.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest
from conftest import SHOTS, eventually, shot_name
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/desktop/private-place.feature")

PLACE_NAMES = "nav.servers .server-name"
LIST_HEADING = ".list .list-head h2"


@pytest.fixture
def tab(browser, request) -> Iterator[dict]:
    """A browser tab of its own; afterwards a screenshot, and no errors in its console."""
    context = browser.new_context(viewport={"width": 1360, "height": 900})
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
    yield {"page": page}
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"{shot_name(request.node.name)}.png"))
    context.close()
    assert not errors, "the browser reported errors:\n" + "\n".join(errors)


@given("a claudia server runs on this computer", target_fixture="address")
def a_server_on_this_computer(suite: str) -> str:
    assert urlsplit(suite).hostname in ("127.0.0.1", "localhost")
    return suite


@when("I open its address in a browser tab")
def open_it(tab: dict, address: str) -> None:
    tab["page"].goto(address)


@then(parsers.parse('its place is called "{name}"'))
def place_called(tab: dict, name: str) -> None:
    page = tab["page"]

    def shown() -> None:
        assert name in page.locator(PLACE_NAMES).all_inner_texts()

    eventually(shown, page=page)


@then(parsers.parse('no place is called "{name}"'))
def no_place_called(tab: dict, name: str) -> None:
    assert name not in tab["page"].locator(PLACE_NAMES).all_inner_texts()


@then(parsers.parse('the list of its documents is headed "{name}", with how many there are'))
def list_headed(tab: dict, name: str) -> None:
    page = tab["page"]

    def headed() -> None:
        assert re.fullmatch(rf"{re.escape(name)} · \d+", (page.locator(LIST_HEADING).text_content() or "").strip())

    eventually(headed, page=page)
