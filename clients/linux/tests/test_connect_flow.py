"""Connecting a window to another server, from the page's start page to the shell and back (E5.8).

The real web frontend in a real (headless Chromium) browser, three real servers — two plain http on this computer
(a spreadsheet server and a text server) and one spreadsheet server over TLS with a self-signed certificate — and the
**real shell logic**: ``Bridge``, ``Connector``, ``connection.check``, the server list and the trust store. What is
not real is the part that needs GTK: the browser stands in for the web view, and a certificate that the person has
trusted is accepted by the browser's own switch (``ignore_https_errors``) where WebKit would be told to accept
exactly that certificate (``webpage.WebPage._load_failed_with_tls_errors``).

Needs the checkout's ``.venv`` (``uv sync``), the built frontend (``npm run build`` in ``web``), ``openssl`` and
Playwright with its browser; skipped when one is missing. Run: ``pytest -m e2e tests/test_connect_flow.py``.
"""

from __future__ import annotations

import json
import socket
import ssl
import subprocess
import time
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from certs import needs_openssl, self_signed

from claudia_shell_gtk import identity, manifest, settings
from claudia_shell_gtk.bridge import Bridge
from claudia_shell_gtk.connection import NeedsTrust
from claudia_shell_gtk.connector import Connector, ServerBook
from claudia_shell_gtk.launch import find_frontend, find_server_python
from claudia_shell_gtk.trust import TrustStore

pytestmark = [pytest.mark.e2e, needs_openssl]

STUB = """
window.__outbox = []
window.webkit = {messageHandlers: {claudia: {postMessage: (m) => window.__outbox.push(m)}}}
"""


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_healthy(url: str) -> None:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    end = time.monotonic() + 40
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=2, context=context):  # noqa: S310
                return
        except OSError:
            time.sleep(0.3)
    raise AssertionError(f"{url} did not come up")


@pytest.fixture(scope="module")
def servers(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, str]]:
    python, web = find_server_python(), find_frontend()
    if python is None or web is None:
        pytest.skip("needs the repository's .venv (uv sync) and a built frontend (npm run build in web)")
    folder = tmp_path_factory.mktemp("servers")
    cert = self_signed(folder, "tls", cn="localhost", san="DNS:localhost,IP:127.0.0.1")
    plan = {
        "local": (identity.get("computes").model, []),  # "this computer": plain http
        "texts": (identity.get("composes").model, []),
        "remote": (identity.get("computes").model, ["--tls-cert", str(cert.cert), "--tls-key", str(cert.key)]),
    }
    processes: list[subprocess.Popen[bytes]] = []
    origins: dict[str, str] = {}
    try:
        for name, (model, tls) in plan.items():
            port = free_port()
            command = [
                str(python),
                "-m",
                "claudia_server",
                "--model",
                model,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--web",
                str(web),
                "--plain-dir",
                str(folder / name),
                "--max-documents",
                "5",
                *(tls or ["--no-tls"]),
            ]
            processes.append(subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))  # noqa: S603
            origins[name] = f"{'https' if tls else 'http'}://127.0.0.1:{port}"
        for origin in origins.values():
            wait_healthy(origin)
        yield origins
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=10)


class Shell:
    """What ``window.py`` wires together, around a browser page instead of a web view."""

    def __init__(self, page: Any, config: Path, local_origin: str) -> None:
        self.page = page
        self.book = ServerBook("computes", local_origin=local_origin, local_label="This computer", path=config)
        self.trust = TrustStore(config)
        self.switch_to: str | None = None
        self.failures: list[tuple[str, str]] = []
        self.connector = Connector(
            "computes",
            book=self.book,
            trust=self.trust,
            switch=self._switch,
            fail=self._fail,
            work=lambda job, done: done(job()),
        )
        self.bridge = Bridge(
            manifest.for_app("computes"),
            lambda raw: page.evaluate("(raw) => window.__claudiaShell && window.__claudiaShell.receive(raw)", raw),
            shell_version="test",
            on_connect=self.connector.connect,
            on_servers=self.book.replace,
            server_list=self.book.entries,
        )

    def _switch(self, origin: str) -> None:
        self.switch_to = origin

    def _fail(self, code: str, message: str) -> None:
        self.failures.append((code, message))
        self.bridge.send_connect_failed(code, message)

    def pump(self, seconds: float = 1.5) -> None:
        """Hand the shell what the page posted until it is quiet, and load the server it switched to."""
        quiet_since = time.monotonic()
        while time.monotonic() - quiet_since < seconds:
            posted = self.page.evaluate("() => window.__outbox ? window.__outbox.splice(0) : []")
            for raw in posted:
                quiet_since = time.monotonic()
                self.bridge.receive(raw)
            if self.switch_to is not None:
                origin, self.switch_to = self.switch_to, None
                self.bridge.reset()
                self.page.goto(f"{origin}/")
                quiet_since = time.monotonic()
            time.sleep(0.05)

    def server_names(self) -> list[str]:
        self.page.wait_for_selector("nav.servers .server")
        return [e.inner_text().replace("\n", " ") for e in self.page.query_selector_all("nav.servers .server")]


@pytest.fixture
def shell(servers: dict[str, str], tmp_path: Path) -> Iterator[Shell]:
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as driver:
        try:
            browser = driver.chromium.launch()
        except Exception as problem:  # noqa: BLE001
            pytest.skip(f"no browser for Playwright: {problem}")
        context = browser.new_context(ignore_https_errors=True)
        context.add_init_script(STUB)
        page = context.new_page()
        result = Shell(page, tmp_path / "shell.json", servers["local"])
        page.goto(f"{servers['local']}/")
        result.pump()
        yield result
        browser.close()


def connect(shell: Shell, address: str) -> None:
    page = shell.page
    if page.query_selector("nav.servers .connect-start"):
        page.click("nav.servers .connect-start")
    page.fill("nav.servers input[aria-label='Server address']", address)
    page.click("nav.servers .connect-form button[type=submit]")
    shell.pump()


def test_the_start_page_lists_this_computer_first(shell: Shell) -> None:
    names = shell.server_names()
    assert names[0].startswith("This computer")
    assert len(names) == 1


def test_plain_http_to_another_computer_is_refused_in_the_page(shell: Shell) -> None:
    connect(shell, "http://192.0.2.7:8420")
    shell.page.wait_for_selector("nav.servers p.error")
    assert "https" in shell.page.inner_text("nav.servers p.error")
    assert shell.page.url.startswith(shell.book.local_origin or "")


def test_a_text_server_is_refused_by_a_spreadsheet_window(shell: Shell, servers: dict[str, str]) -> None:
    connect(shell, servers["texts"])
    shell.page.wait_for_selector("nav.servers p.error")
    message = shell.page.inner_text("nav.servers p.error")
    assert "Claudia Composes" in message
    assert "Claudia Computes" in message
    assert shell.page.url.startswith(servers["local"])  # still on the server it was on


def test_a_server_with_an_unknown_certificate_connects_only_once_the_person_trusts_it(
    shell: Shell, servers: dict[str, str], tmp_path: Path
) -> None:
    remote = servers["remote"]
    connect(shell, remote)
    shell.page.wait_for_selector("nav.servers p.error")
    assert "trusts" in shell.page.inner_text("nav.servers p.error")
    assert shell.trust.pinned(remote) is None

    asked: list[Any] = []

    def say_yes(needs: NeedsTrust, answer: Callable[[bool], None]) -> None:
        asked.append(needs)
        answer(True)

    shell.connector.ask_trust = say_yes
    connect(shell, remote)
    shell.page.wait_for_url(f"{remote}/**")
    assert asked[0].reason == "unknown_issuer"
    assert shell.trust.pinned(remote) == asked[0].certificate.sha256
    # the shell has remembered it, for this app only, and the page there shows both servers
    config = tmp_path / "shell.json"
    assert [e["origin"] for e in settings.load_servers("computes", config)] == [remote]
    assert settings.load_servers("composes", config) == []
    names = shell.server_names()
    assert names[0].startswith("This computer")
    assert any("127.0.0.1" in n for n in names[1:])

    # ... and back to this computer, from the list on that server's page
    shell.page.click("nav.servers .server >> nth=0")
    shell.pump()
    shell.page.wait_for_url(f"{servers['local']}/**")
    shell.pump()
    assert shell.server_names()[0].startswith("This computer")


def test_declining_the_certificate_connects_nowhere(shell: Shell, servers: dict[str, str]) -> None:
    shell.connector.ask_trust = lambda needs, answer: answer(False)
    connect(shell, servers["remote"])
    shell.page.wait_for_selector("nav.servers p.error")
    assert "did not trust" in shell.page.inner_text("nav.servers p.error")
    assert shell.page.url.startswith(servers["local"])
    assert shell.trust.pinned(servers["remote"]) is None


def test_the_hello_of_the_start_page_names_the_app_of_its_server(shell: Shell) -> None:
    assert shell.bridge.ready
    assert json.loads(json.dumps(shell.book.entries()))[0]["local"] is True
