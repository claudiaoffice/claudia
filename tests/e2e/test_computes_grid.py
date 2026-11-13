"""A computes document in a real browser: the grid is on the screen, and alternatives and following work (E6.21–E6.23).

Why a browser test: the patch that added chips, the dot strip and following to ``SheetGrid.vue`` passed every vitest
test (those only reach ``web/app/lib``), typechecked and linted — and threw in the component's setup (a ``watch`` read a
``const`` declared further down), so the page showed the history and chat panel across the whole window and no cells at
all (owner's report, 2026-11-13). Nothing but rendering the component can see that.

Like ``test_greeting.py`` this needs the built web app and a browser and is skipped, saying why, without them.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Iterator

import pytest
from test_greeting import LAUNCHER, ROOT, SKIP, START_SECONDS, _free_port_block, _is_free, _launch

pytestmark = pytest.mark.skipif(bool(SKIP), reason=SKIP)


@pytest.fixture(scope="module")
def port(tmp_path_factory: pytest.TempPathFactory) -> Iterator[int]:
    first = _free_port_block(1)
    command = [sys.executable, str(LAUNCHER), "computes", "--no-browser", "--port", str(first)]
    command += ["--dir", str(tmp_path_factory.mktemp("documents"))]
    process = subprocess.Popen(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True
    )
    try:
        deadline = time.monotonic() + START_SECONDS
        while _is_free(first):
            assert process.poll() is None, f"the launcher stopped early:\n{process.communicate()[0]}"
            assert time.monotonic() < deadline, "the server did not come up"
            time.sleep(0.25)
        yield first
    finally:
        process.kill()
        process.wait(timeout=30)


def _open_new_document(page, port: int) -> None:
    page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
    page.get_by_label("Document").fill("grid")
    page.get_by_label("Your name").fill("tester")
    page.get_by_label("Password").fill("Probe12345")
    page.get_by_role("button", name="Create document").click()
    page.get_by_label("I have stored the recovery key somewhere safe.").check()
    page.get_by_role("button", name="Continue").click()
    page.wait_for_selector("[role=grid]")


def test_the_grid_is_on_the_screen_and_alternatives_and_following_work(port: int) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as play:
        browser = _launch(play)
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 850})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            _open_new_document(page, port)
            grid = page.locator("[role=grid]")
            assert grid.bounding_box()["width"] > 400, "the grid is squeezed out (the side panel took the window)"

            grid.click(position={"x": 120, "y": 39})
            for text in ("{10,20,30}", "=A1*2", "=A2+1", "5"):
                page.keyboard.type(text)
                page.keyboard.press("Enter")
            page.wait_for_selector(".cell .alt")
            assert page.locator(".cell .alt").count() == 3
            assert page.locator(".cell .strip").count() == 2

            grid.click(position={"x": 120, "y": 39})  # A1
            page.keyboard.press("Control+Alt+KeyF")
            page.wait_for_selector(".cell[data-role=output]")
            assert [page.locator(f".cell[data-role={role}]").count() for role in ("input", "calc", "output")] == [
                1,
                1,
                1,
            ]
            assert page.locator(".cell.dim").count() == 1  # the 5 in A4 takes no part
            page.keyboard.press("Escape")
            page.wait_for_function("document.querySelectorAll('.cell.dim').length === 0")

            # The Random generator writes one formula into the cell: `=RANDOM(...)`, not `==RANDOM(...)`.
            grid.click(position={"x": 120, "y": 143})  # A5
            page.keyboard.press("Control+Alt+KeyR")
            page.wait_for_selector("dialog[open] code")
            assert page.locator("dialog[open] code").first.inner_text().startswith('=RANDOM("normal"')
            page.get_by_role("button", name="Put in A5").click()
            page.wait_for_selector(".cell:has-text('9')")
            grid.click(position={"x": 120, "y": 143})
            page.keyboard.press("F2")
            assert page.locator("[role=grid] input").input_value().startswith('=RANDOM("normal"')
            assert errors == []
        finally:
            browser.close()
