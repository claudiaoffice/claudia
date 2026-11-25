"""The steps of ``desktop/shared-place.feature`` that a browser checks (E8.5, D1622, D1624).

The computer's shared service is a claudia server on this computer like any other; what makes it the service -- its
installer's marker, which the apps read -- is checked by the unit tests the other scenarios' tags name. Here a server
on 127.0.0.1 stands in for it: the suite's server for two people who work on one document, and a server of its own
with no administrator for its setup page. "Whether I am an administrator of this computer" is said by the desktop app
in its ``welcome``, which the test plays as ``test_administrators.py`` does: the setup code for an administrator,
``ask_administrator`` for anyone else (the apps' part is checked by core.test.ts).
"""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from test_administrators import Visit, site, visit  # noqa: F401  (the fixtures of a server of its own and its page)

scenarios("../../../claudiaoffice-log/specs/desktop/shared-place.feature")

PASSWORD_OF_ANNA = "correct horse battery staple"


@pytest.fixture
def two(suite_world, suite) -> Iterator:
    assert urlsplit(suite).hostname in ("127.0.0.1", "localhost"), "the service listens on this computer only"
    yield suite_world


# -- two people work on one shared document ----------------------------------------------------------------------
@given("the claudia service is installed on this computer")
def service_installed() -> None:
    """The browser scenarios open a server on 127.0.0.1 (``two``, ``site``); the listing is the apps' (unit tests)."""


@given(parsers.parse('Anna made "{title}" in "Shared on this computer" and gave Ben the role editor'))
def anna_shares(two, title) -> None:  # noqa: ARG001  (the document's name is the world's own)
    two.join("Anna").create()
    two.ann.share(two.join("Ben"), "editor")


@when(parsers.parse('Ben opens "{title}" from "Shared on this computer" with his own password'))
def ben_opens(two, title) -> None:  # noqa: ARG001
    ben = two.people["Ben"]
    ben.open()
    ben.wait_until_open()


@then("Ben can change it")
def ben_changes(two) -> None:
    page = two.people["Ben"].page
    page.click("[data-testid=text]")
    page.keyboard.type("Rent 900 from Ben")
    page.locator(".health.open").wait_for(state="attached", timeout=20000)


@then("Anna sees his change")
def anna_sees(two) -> None:
    two.ann.page.locator("[data-testid=text] [data-paragraph]", has_text="Rent 900 from Ben").first.wait_for(
        timeout=10000
    )


# -- its first administrator -------------------------------------------------------------------------------------
@given("the claudia service has no administrator yet")
def no_administrator(site) -> None:  # noqa: F811
    site.start()


@given("I am an administrator of this computer")
def computer_administrator(visit: Visit, site) -> None:  # noqa: F811
    visit.as_desktop_app(site.code())


@given("I am not an administrator of this computer")
def not_computer_administrator(visit: Visit) -> None:  # noqa: F811
    visit.as_desktop_app(ask_administrator=True)


@when('I open the settings of "Shared on this computer"')
def open_settings(visit: Visit) -> None:  # noqa: F811
    visit.open()


@then("its setup code is filled in for me")
def code_filled_in(visit: Visit) -> None:  # noqa: F811
    visit.page.wait_for_timeout(500)  # the welcome and the check of its code have come by now
    assert visit.page.locator("#setup-code").count() == 0, "the app gave the code: there is no field for it"


@then("I can make myself its first administrator")
def make_myself_administrator(visit: Visit, site) -> None:  # noqa: F811
    visit.fill_and_create(None, "anna", PASSWORD_OF_ANNA)
    visit.page.wait_for_selector("text=Signed in as anna", timeout=15000)
    assert site.status()["administrator"] is not None


@then(parsers.parse('I read "{sentence}"'))
def read(visit: Visit, sentence: str) -> None:  # noqa: F811
    visit.page.get_by_text(sentence, exact=True).wait_for(timeout=10000)
