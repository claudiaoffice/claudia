"""The server's administrators: the steps of ``claudiaoffice-log/specs/server/administrators.feature`` (SEC-12,
D1370–D1376, UX-61).

Unlike the other features, every scenario here needs a server of its own (one with no administrator, one behind a
proxy, one started with extra options, one restarted), so the steps start it themselves with ``live.server`` and read
what it printed. "A server behind a proxy" is one on 127.0.0.1 with ``--behind-proxy``: the browser reaches it directly
and it counts as exposed (D1374). The link of the log names the proxy's address; "opening" it opens its path and its
fragment at the server itself, which is what the proxy would forward.

"A desktop app that hands it the code" is played by the page's own shell bridge: the test puts a
``window.webkit.messageHandlers.claudia`` in the page, as the GTK app does, and answers its ``hello`` with a
``welcome`` that carries ``setup_code``. The apps' own part is checked by their unit tests.

The browser may say "403", "409" and "429" in its console here: those are the refusals the scenarios ask for.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import stat
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import BROWSER, SHOTS
from live import server
from pytest_bdd import given, parsers, scenarios, then, when
from test_greeting import BUILT, SKIP

scenarios("../../../claudiaoffice-log/specs/server/administrators.feature")

PASSWORD = "Anna has a password 1"
CODE_LINE = re.compile(r"^  setup code   (\S+)$", re.M)
LINK_LINE = re.compile(r"^  or open      (\S+)$", re.M)
EXPECTED_REFUSALS = re.compile(r"status of (401|403|409|429)")


class Site:
    """One server of its own: its folder, how it was started, what it printed, and an HTTP client for it."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.state = folder / "state"
        self.extra: tuple[str, ...] = ()
        self._running: contextlib.ExitStack | None = None
        self.live = None
        self.codes: list[str] = []  # every setup code it printed, oldest first

    def start(self, *extra: str) -> None:
        self.stop()
        self.extra = extra
        stack = contextlib.ExitStack()
        self.live = stack.enter_context(server(self.folder, "--web", str(BUILT), *extra))
        self._running = stack
        if code := self.code():
            self.codes.append(code)

    def restart(self, *extra: str) -> None:
        self.start(*(extra or self.extra))

    def stop(self) -> None:
        if self._running is not None:
            self._running.close()
            self._running = None

    @property
    def url(self) -> str:
        return self.live.url

    def log(self) -> str:
        return (self.folder / "server.log").read_text(errors="replace")

    def code(self) -> str | None:
        found = CODE_LINE.findall(self.log())
        return found[-1] if found else None

    def link(self) -> str | None:
        found = LINK_LINE.findall(self.log())
        return found[-1] if found else None

    def call(self, method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, object]:
        import urllib.error
        import urllib.request

        headers = {"content-type": "application/json"} if body is not None else {}
        if token:
            headers["authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as answer:
                status, raw = answer.status, answer.read()
        except urllib.error.HTTPError as refused:
            status, raw = refused.code, refused.read()
        return status, json.loads(raw) if raw else None

    def status(self) -> dict:
        return self.call("GET", "/api/admin/status")[1]

    def sign_in(self, name: str, password: str) -> str | None:
        status, answer = self.call("POST", "/api/admin/login", {"name": name, "password": password})
        return answer["token"] if status == 200 else None


def put_administrators(state: Path, *names: str, password: str = PASSWORD) -> None:
    """Administrators saved in ``state`` as a server would have saved them (cheap hashing: these are test fixtures)."""
    from claudia_server.admin import AdminDirectory
    from claudia_server.server_settings import save_admins

    admins = AdminDirectory(cost=2**10)
    for name in names:
        admins.add(name, password, added="2026-11-01T00:00:00Z")
    save_admins(state, admins)


class Visit:
    """The browser on the server's settings pages."""

    def __init__(self, browser, site: Site):
        self.site = site
        self.context = browser.new_context(viewport={"width": 1100, "height": 900})
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on(
            "console",
            lambda m: m.type == "error" and not EXPECTED_REFUSALS.search(m.text) and self.errors.append(m.text),
        )

    def as_desktop_app(self, code: str) -> None:
        """Answer the page's hello as the GTK app does, with ``code`` in the welcome (D1373)."""
        welcome = {
            "type": "welcome",
            "contract": 1,
            "shell": {"name": "gtk", "platform": "linux", "version": "test"},
            "capabilities": ["native-menu", "actions"],
            "setup_code": code,
        }
        self.page.add_init_script(
            "window.webkit = { messageHandlers: { claudia: { postMessage(raw) {"
            "  if (JSON.parse(raw).type === 'hello')"
            f"    setTimeout(() => window.__claudiaShell.receive({json.dumps(json.dumps(welcome))}), 50)"
            "} } } }"
        )

    def open(self, path: str = "/admin/") -> None:
        self.page.goto(self.site.url + path)
        self.page.wait_for_selector("form, .admin-app p", timeout=15000)

    def fill_and_create(self, code: str | None, name: str, password: str = PASSWORD) -> None:
        if code is not None:
            self.page.fill("#setup-code", code)
        self.page.fill("input[autocomplete=username]", name)
        for field in self.page.locator("input[type=password]").all():
            field.fill(password)
        self.page.click("button:text-is('Create administrator')")

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.context.close()


@pytest.fixture
def site(request) -> Iterator[Site]:
    if SKIP:
        pytest.skip(SKIP)
    if BROWSER == "firefox":
        pytest.skip("these scenarios are not tagged @firefox")
    with tempfile.TemporaryDirectory(prefix="claudia-admins-") as folder:
        made = Site(Path(folder))
        try:
            yield made
        finally:
            made.stop()


@pytest.fixture
def visit(browser, site, request) -> Iterator[Visit]:
    made = Visit(browser, site)
    yield made
    SHOTS.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"\W+", "-", request.node.name)[:80]
    with contextlib.suppress(Exception):
        made.page.screenshot(path=str(SHOTS / f"{slug}.png"))
    errors = list(made.errors)
    made.close()
    assert not errors, "the browser reported errors:\n" + "\n".join(errors)


def eventually(check, seconds: float = 8.0) -> None:
    end = time.monotonic() + seconds
    while True:
        try:
            check()
            return
        except AssertionError:
            if time.monotonic() > end:
                raise
            time.sleep(0.1)


# ------------------------------------------------------------------------------------------------------------ given
@given("a server behind a proxy that has no administrator")
def proxied_server(site):
    site.start("--behind-proxy")


@given("a server on 127.0.0.1 that has no administrator")
def local_server(site):
    site.start()


@given("its page is shown by a desktop app that hands it the server's setup code")
def desktop_app(visit, site):
    visit.as_desktop_app(site.code())


@given("its page is shown by a desktop app that hands it a setup code the server does not have")
def desktop_app_with_old_code(visit):
    visit.as_desktop_app("0000-0000-0000")


@given(
    parsers.parse(
        'a server with the administrators "{first}" and "{second}", an access secret and an AI model folder set'
    )
)
def configured_server(site, first, second):
    from claudia_server.server_settings import AiSettings, ServerSettings, save_settings

    put_administrators(site.state, first, second)
    settings = ServerSettings(max_documents=40, access_secret="the access secret of the server")
    settings.ai = AiSettings(model_dir=str(site.folder / "no-such-model"))
    save_settings(site.state, settings)
    site.before = json.loads((site.state / "admin" / "settings.json").read_text())


@given(parsers.parse('a server whose administrators "{first}" and "{second}" were reset and "{named}" was named'))
def reset_and_named(site, first, second, named):
    put_administrators(site.state, first, second)
    password_file = site.folder / "password"
    password_file.write_text(PASSWORD + "\n", encoding="utf-8")
    site.start("--reset-administrators", "--admin", named, "--admin-password-file", str(password_file))


@given(parsers.parse('a server with the administrator "{name}" and a composes document "{document}" of Ann'))
def server_with_a_document(site, name, document):
    put_administrators(site.state, name)
    site.start()
    with site.live.socket("composes", document) as session:
        session.hello(create=True)
    site.document = document


@given(parsers.parse('a password file with the password "{password}"'))
def password_file(site, password):
    path = site.folder / "password"
    path.write_text(password + "\n", encoding="utf-8")
    site.password_file = path


@given(parsers.parse('a server with the administrator "{name}" and the password "{password}"'))
def one_administrator(site, name, password):
    put_administrators(site.state, name, password=password)


@given(parsers.parse('a server with the administrators "{first}" and "{second}"'))
def two_administrators(site, first, second):
    put_administrators(site.state, first, second)


# ------------------------------------------------------------------------------------------------------------- when
@when("I open its server settings")
def open_settings(visit):
    visit.open()


@when(
    parsers.parse(
        'I type the setup code from the server\'s log, the name "{name}" and a password, and press Create administrator'
    )
)
def type_the_code(visit, site, name):
    visit.fill_and_create(site.code(), name)


@when(parsers.parse('I type the setup code "{code}", the name "{name}" and a password, and press Create administrator'))
def type_a_code(visit, code, name):
    visit.fill_and_create(code, name)


@when(
    parsers.parse(
        "I type the server's setup code in lower case with spaces, "
        'the name "{name}" and a password, and press Create administrator'
    )
)
def type_the_code_loosely(visit, site, name):
    visit.fill_and_create(" " + site.code().lower().replace("-", " ") + " ", name)


@when(parsers.parse("I try {count:d} wrong setup codes"))
def try_wrong_codes(visit, count):
    for n in range(count):
        visit.fill_and_create(f"0000-0000-000{n}", "mallory")
        visit.page.wait_for_function(
            "() => !document.querySelector('button.primary').disabled && document.querySelector('.code-error')"
        )


@when("I open the link from the server's log")
def open_the_link(visit, site):
    link = site.link()
    assert link, "the log gives no link"
    path = link.split("/", 3)[3]  # admin#setup=…: what the proxy would forward to the server
    visit.open("/" + path)


@when(parsers.parse('somebody else names "{name}" the first administrator with the server\'s setup code'))
def somebody_faster(site, name):
    status, _ = site.call("POST", "/api/admin/setup", {"name": name, "password": PASSWORD, "code": site.code()})
    assert status == 200


@when("the server is restarted")
def restart(site):
    site.restart()


@when("the server is started with --reset-administrators")
def start_with_reset(site):
    site.start("--reset-administrators")


@when(parsers.parse('I name "{name}" the first administrator with the new setup code'))
def name_with_new_code(site, name):
    status, _ = site.call("POST", "/api/admin/setup", {"name": name, "password": PASSWORD, "code": site.code()})
    assert status == 200


@when(parsers.parse('"{name}" opens Access & documents'))
def opens_access(visit, name):
    visit.open()
    visit.page.fill("input[autocomplete=username]", name)
    visit.page.fill("input[type=password]", PASSWORD)
    visit.page.click("button:text-is('Sign in')")
    visit.page.click("nav >> text=Access & documents")
    visit.page.wait_for_selector("h1:text-is('Access & documents')")


@when("she presses Dismiss")
def dismiss(visit):
    visit.page.click("[data-testid=reset-note] button:text-is('Dismiss')")


@when(parsers.parse('a server with no administrator is started with --admin "{name}" and that password file'))
def start_with_admin(site, name):
    site.start("--admin", name, "--admin-password-file", str(site.password_file))


@when(parsers.parse('it is started with --admin "{name}" and a password file with "{password}"'))
def start_with_admin_again(site, name, password):
    path = site.folder / "password"
    path.write_text(password + "\n", encoding="utf-8")
    site.start("--admin", name, "--admin-password-file", str(path))


@when(parsers.parse('it is started with --reset-administrators, --admin "{name}" and a password file'))
def start_with_reset_and_admin(site, name):
    path = site.folder / "password"
    path.write_text(PASSWORD + "\n", encoding="utf-8")
    site.start("--reset-administrators", "--admin", name, "--admin-password-file", str(path))


# ------------------------------------------------------------------------------------------------------------- then
@then("the server's log gives a setup code and a link to the server settings with the code")
def log_gives_code_and_link(site):
    code = site.code()
    assert code and re.fullmatch(r"[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}", code)
    assert site.link().endswith(f"/admin#setup={code}")


@then("the server's log gives a setup code")
def log_gives_code(site):
    assert site.code()


@then("the server's state folder has the setup code in a file only the server's account can read")
def code_file(site):
    path = site.state / "admin" / "setup-code"
    assert path.read_text().strip() == site.code()
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


@then("the server's status does not contain the setup code")
def status_without_code(site):
    status = site.status()
    assert status["setup_code"] is True
    assert site.code() not in json.dumps(status)


@then("I am asked for a setup code, my name and a password")
def asked_for_code(visit):
    visit.page.wait_for_selector("#setup-code:not([readonly])")
    assert visit.page.locator("input[autocomplete=username]").count() == 1
    assert visit.page.locator("input[type=password]").count() == 2


@then(parsers.parse('I am signed in as "{name}"'))
def signed_in(visit, name):
    visit.page.wait_for_selector(f"text=Signed in as {name}", timeout=15000)


@then("the server's state folder no longer has a setup code")
@then("the server's state folder has no setup code")
def no_code_file(site):
    assert not (site.state / "admin" / "setup-code").exists()


@then("I am told that this is not the server's setup code")
def told_wrong(visit):
    visit.page.wait_for_selector(".code-error")
    assert "not this server's setup code" in visit.page.inner_text(".code-error")


@then("the server still has no administrator")
@then("the server has no administrator")
def still_none(site):
    assert site.status()["administrator"] is None


@then(parsers.parse('the setup code is filled in and marked "{words}"'))
def filled_from_link(visit, site, words):
    field = visit.page.locator("#setup-code")
    eventually(lambda: assert_equal(field.input_value(), site.code()))
    assert field.get_attribute("readonly") is not None
    assert words in visit.page.inner_text("#setup-code-hint")
    visit.page.wait_for_selector("svg.checked")


def assert_equal(a, b):
    assert a == b, f"{a!r} != {b!r}"


@then("the address bar shows no setup code")
def address_without_code(visit):
    assert "setup=" not in visit.page.url


@then(parsers.parse('the page offers "{label}"'))
def offers(visit, label):
    assert visit.page.locator(f'button:text-is("{label}")').count() == 1


@then("I am told to try again in some seconds")
def told_to_wait(visit):
    assert re.search(r"Try again in \d+ seconds", visit.page.inner_text(".code-error"))


@then(parsers.parse('I see the sign-in form with the line "{line}"'))
def sign_in_with_line(visit, line):
    visit.page.wait_for_selector("[data-testid=login-notice]")
    assert line in visit.page.inner_text("[data-testid=login-notice]")
    assert visit.page.locator("button:text-is('Sign in')").count() == 1


@then("the server's log gives a setup code that is not the one before")
def new_code(site):
    assert len(site.codes) == 2 and site.codes[0] != site.codes[1] and site.code() == site.codes[1]


@then("the setup code from before is refused")
def old_code_refused(site):
    assert site.call("POST", "/api/admin/setup-code", {"code": site.codes[0]})[0] == 403


@then("the page says the server can be reached from other computers")
def says_exposed(visit):
    assert "can be reached from other computers" in visit.page.inner_text(".lead")


@then("I see no setup code field")
def no_field(visit):
    visit.page.wait_for_selector("text=Create administrator")
    time.sleep(0.5)  # the welcome and the check of its code have come by now
    assert visit.page.locator("[data-testid=setup-code]").count() == 0


@then(parsers.parse('I can name myself "{name}" with a password and am signed in'))
def name_myself(visit, name):
    visit.fill_and_create(None, name)
    signed_in(visit, name)


@then(parsers.parse('the server\'s log says that "{first}" and "{second}" were removed'))
def log_says_removed(site, first, second):
    assert f"administrators reset: {first}, {second} removed" in site.log()


@then("the old administrators are kept aside in the server's state folder")
def kept_aside(site):
    kept = list((site.state / "admin").glob("admins-before-reset-*.json"))
    assert len(kept) == 1


@then("the access secret and the AI model folder are as before")
def settings_unchanged(site):
    now = json.loads((site.state / "admin" / "settings.json").read_text())
    assert now["access_secret"] == site.before["access_secret"]
    assert now["ai"]["model_dir"] == site.before["ai"]["model_dir"]


@then(
    parsers.parse(
        'she reads that the administrators were reset from the server\'s console, with the date and "{names}"'
    )
)
def reads_note(visit, names):
    note = visit.page.inner_text("[data-testid=reset-note]")
    assert "reset from the server's console on" in note and names in note
    assert re.search(r"\d{4}", note)


@then("she is told to rotate the access secret if they should no longer know it")
def told_to_rotate(visit):
    assert "rotate it below" in visit.page.inner_text("[data-testid=reset-note]")


@then("the note is gone, also after the page is opened again")
def note_gone(visit):
    visit.page.wait_for_selector("[data-testid=reset-note]", state="detached")
    visit.page.reload()
    visit.page.click("nav >> text=Access & documents")
    visit.page.wait_for_selector("h1:text-is('Access & documents')")
    assert visit.page.locator("[data-testid=reset-note]").count() == 0


@then(parsers.parse('Ann opens "{document}" with her name and password as before'))
def ann_opens(site, document):
    with site.live.socket("composes", document) as session:
        assert session.hello(create=False)


@then(parsers.parse('the server\'s log says "{name}" was named at start'))
def named_at_start(site, name):
    assert f"administrators: {name} (named at start with --admin)" in site.log()


@then(parsers.parse('"{name}" signs in to the server settings with "{password}"'))
@then(parsers.parse('"{name}" signs in with "{password}"'))
def signs_in(site, name, password):
    assert site.sign_in(name, password)


@then("the server's log says that the server has administrators and --admin changed nothing")
def admin_ignored(site):
    assert "changed nothing: this server has administrators" in site.log()


@then(parsers.parse('the server\'s administrators are "{name}" only'))
def only(site, name):
    token = site.sign_in(name, PASSWORD)
    assert token
    status, admins = site.call("GET", "/api/admin/admins", token=token)
    assert status == 200 and [a["name"] for a in admins] == [name]
