"""``./start.sh all``, end to end: three servers side by side, each greeting a visitor with its own app (UX-10).

This is the one test that drives a real browser. Everything else about the web app is checked by vitest against
``web/app/lib``, which is why UX-10 went unnoticed: the server said which app it served, the page threw that away
and worked the app out from the first document it listed instead, and on a fresh machine there are no documents.
Three servers then greeted everybody as computes. Nothing below that line could see it — the launcher was right,
the servers were right, ``/api/docs`` was right, and only the rendered page was wrong.

So the test starts the launcher exactly as a person does, opens each port in Chromium, and reads what is on the
screen. It is deliberately not in the main suite: it needs the web app built and a browser installed, and it starts
three servers. ``scripts/check_debt.py`` runs it as its own step and skips it, saying why, when either is missing.

What it asserts, and what it does not: ``data-app`` on the document element, which is the page's own statement of
which app it thinks it is, and that the three headlines differ from one another. It does **not** hardcode the
wording — that is copy, it will be translated, and a test that pins it would have to be edited every time somebody
improves a sentence.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
BUILT = ROOT / "web" / ".output" / "public"
LAUNCHER = ROOT / "scripts" / "start.py"

#: The apps ``all`` starts, in the order it gives them consecutive ports.
APPS = ("computes", "composes", "creates")
START_SECONDS = 90.0


def chromium_at() -> str | None:
    """``$CLAUDIA_CHROMIUM``, for a machine that already has a browser and will not download another.

    The same idea as ``$CLAUDIA_CLIENT_PYTHON`` for the Linux client's tests: a packager, an air-gapped build or a
    sandbox that cannot reach Playwright's download host points this at a Chromium it already has.
    """
    return os.environ.get("CLAUDIA_CHROMIUM") or None


def _launch(play):
    """Start Chromium, from ``$CLAUDIA_CHROMIUM`` if it is set and from Playwright's own copy otherwise."""
    where = chromium_at()
    return play.chromium.launch(executable_path=where) if where else play.chromium.launch()


def _why_not() -> str:
    """Why this test cannot run here, or ``""`` if it can. The same words ``check_debt.py`` prints."""
    if not (BUILT / "index.html").is_file():
        return "the web app is not built (run `npm install && npm run build` in web/)"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "playwright is not installed (`uv sync`)"
    try:
        with sync_playwright() as play:
            _launch(play).close()
    except Exception:  # noqa: BLE001 - any failure to start the browser is the same answer: it is not usable here
        return "no chromium for playwright (`uv run playwright install chromium`, or set $CLAUDIA_CHROMIUM)"
    return ""


SKIP = _why_not()
pytestmark = pytest.mark.skipif(bool(SKIP), reason=SKIP)


def _free_port_block(count: int) -> int:
    """The first of ``count`` consecutive free ports, which is what ``all`` wants."""
    for _ in range(50):
        with closing(socket.socket()) as probe:
            probe.bind(("127.0.0.1", 0))
            first = probe.getsockname()[1]
        if first + count > 65535:
            continue
        if all(_is_free(first + offset) for offset in range(count)):
            return first
    raise RuntimeError(f"no block of {count} free ports")


def _is_free(port: int) -> bool:
    with closing(socket.socket()) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _wait_for(ports: list[int], process: subprocess.Popen) -> None:
    """Wait until every port answers, or say what the launcher printed instead."""
    deadline = time.monotonic() + START_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"the launcher stopped early:\n{process.communicate()[0]}")
        if all(not _is_free(port) for port in ports):
            return
        time.sleep(0.25)
    process.kill()
    raise AssertionError(f"the servers did not come up in {START_SECONDS:.0f}s:\n{process.communicate()[0]}")


@pytest.fixture(scope="module")
def servers(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, int]]:
    """``./start.sh all`` with its own documents folder and its own ports: app name to port."""
    first = _free_port_block(len(APPS))
    ports = [first + offset for offset in range(len(APPS))]
    command = [
        sys.executable,
        str(LAUNCHER),
        "all",
        "--no-browser",
        "--port",
        str(first),
        "--dir",
        str(tmp_path_factory.mktemp("documents")),
    ]
    process = subprocess.Popen(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True
    )
    try:
        _wait_for(ports, process)
        yield dict(zip(APPS, ports, strict=True))
    finally:
        process.kill()
        process.wait(timeout=30)


@pytest.fixture(scope="module")
def greetings(servers: dict[str, int]) -> dict[str, dict[str, str]]:
    """What each server's landing page says about itself, with no document anywhere: the state UX-10 was about."""
    from playwright.sync_api import sync_playwright

    seen: dict[str, dict[str, str]] = {}
    with sync_playwright() as play:
        browser = _launch(play)
        try:
            for app, port in servers.items():
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
                page.wait_for_selector("h1")
                seen[app] = {
                    "app": page.evaluate("document.documentElement.dataset.app || ''"),
                    "headline": page.locator("h1").first.inner_text().strip(),
                }
                page.close()
        finally:
            browser.close()
    return seen


def test_every_server_says_which_app_it_serves(greetings: dict[str, dict[str, str]]) -> None:
    said = {app: seen["app"] for app, seen in greetings.items()}
    assert said == {app: app for app in APPS}, (
        "a server greeted a visitor as another app. Before UX-10 the page worked this out from the first document "
        f"it listed, so an empty server fell back to computes whatever it served. Saw: {said}"
    )


def test_each_greeting_is_that_app_s_own(greetings: dict[str, dict[str, str]]) -> None:
    headlines = {app: seen["headline"] for app, seen in greetings.items()}
    assert all(headlines.values()), f"a landing page greeted nobody at all: {headlines}"
    assert len(set(headlines.values())) == len(APPS), (
        f"two apps greet a visitor with the same words, so one of them is wearing the other's face: {headlines}"
    )


def test_the_launcher_gives_the_apps_consecutive_ports(servers: dict[str, int]) -> None:
    # The order matters to the test above: `all` hands out ports in the order of `APPS`, and a visitor on the second
    # port is promised composes by what the launcher printed.
    ports = list(servers.values())
    assert ports == [ports[0] + offset for offset in range(len(APPS))]
