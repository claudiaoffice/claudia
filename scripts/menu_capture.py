"""Write down the menus the web client really shows: every app, every role, in English and German (menu audit, phase 1).

``uv run python scripts/menu_capture.py [OUT]``  (default ``.claudia/menu-audit/web.json``)

Starts a real server of all three apps with the built web app (``./run-e2e.sh setup`` builds it), makes one document
per app as Ann (owner), shares it with Eddie (editor) and Vera (viewer), and opens every top menu and submenu for each
of them, then once more for Ann in German. As Ann it also right-clicks the places that have a context menu: a cell, a
row and a column header (computes), a paragraph and a table (composes), the slide (creates) and an object (all three;
a Mermaid container, the one object every app can insert without a file or a dialog).

What it writes is what a person sees: labels, the key shown beside them, separators, greyed entries, ticks. The ids of
the actions are not in the page's markup; ``menu_audit.py`` finds them through the manifest. Chromium by default (the
browser the end-to-end tests use); ``$CLAUDIA_E2E_BROWSER=firefox`` for Firefox, where Playwright has one.
"""

from __future__ import annotations

import contextlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "tests" / "e2e"), str(ROOT / "tests" / "e2e" / "specs")]

import conftest as e2e  # noqa: E402 - the spec steps' Person: create, share, open, menu
from live import server  # noqa: E402

OUT = ROOT / ".claudia" / "menu-audit" / "web.json"
APPS = ("computes", "composes", "creates")
OBJECTS = "[data-object], [data-testid=slide] .obj"
MENU = "ul.menu[role=menu]"
#: One entry of a menu as the page draws it (MenuBar.vue, ContextMenu.vue): a separator, or a button.
_ITEMS_JS = """ul => [...ul.children].map(li => {
  if (li.matches('.sep, [role=separator]')) return {sep: true}
  const b = li.querySelector(':scope > button'); if (!b) return null
  const own = b.querySelector('.label') ?? b.querySelector('span')
  return {label: own.textContent.replace('▸', '').replace('✓', '').trim(), disabled: b.disabled,
          hint: b.querySelector(':scope > kbd')?.textContent.trim() || null,
          checked: b.getAttribute('aria-checked'), sub: b.getAttribute('aria-haspopup') === 'menu'}
}).filter(Boolean)"""
_OTHER_JS = """() => { const p = document.querySelector('[role=dialog]:not(dialog), dialog[open], .popover');
  return p ? (p.getAttribute('aria-label') || p.className) + ': '
    + p.innerText.slice(0, 160).split(String.fromCharCode(10)).filter(Boolean).join(' / ') : null }"""


def read_menu(page, ul: str) -> list[dict[str, Any]]:
    """The entries of the open menu ``ul``; a submenu is opened by pointing at it and read the same way."""
    items = page.eval_on_selector(ul, _ITEMS_JS)
    for n, item in enumerate(items, start=1):
        if item.get("sub") and not item["disabled"]:
            page.locator(f"{ul} > li:nth-child({n}) > button").hover()
            page.wait_for_timeout(120)
            sub = page.query_selector(f"{ul} > li:nth-child({n}) ul[role=menu]")
            item["items"] = sub.evaluate(_ITEMS_JS) if sub else "did not open"
    return items


def top_menus(page) -> dict[str, list[dict[str, Any]]]:
    """Every menu of the menu bar, by its title."""
    titles = page.eval_on_selector_all(".menus .title", "els => els.map(e => e.textContent.trim())")
    menus = {}
    for i, title in enumerate(titles):
        page.keyboard.press("Escape")
        page.click(f".menus .title >> nth={i}")
        page.wait_for_selector(f"#menu-drop-{i}")
        menus[title] = read_menu(page, f"#menu-drop-{i}")
        page.keyboard.press("Escape")
    return menus


def right_click(page, target, position: dict[str, float] | None = None) -> None:
    """A right press of the mouse on ``target``: its middle, or ``position`` inside it."""
    target.scroll_into_view_if_needed(timeout=5000)
    box = target.bounding_box(timeout=5000)
    x, y = (position["x"], position["y"]) if position else (box["width"] / 2, box["height"] / 2)
    page.mouse.click(box["x"] + x, box["y"] + y, button="right")


def context_menu(page, target, position: dict[str, float] | None = None) -> dict[str, Any] | str:
    """The context menu a right press on ``target`` opens; when none opens, what opened instead, or that nothing did."""
    page.keyboard.press("Escape")
    right_click(page, target, position)
    try:
        page.wait_for_selector(MENU, timeout=2500)
    except Exception:  # noqa: BLE001 - Playwright's timeout: no menu is an answer, not an error
        other = page.evaluate(_OTHER_JS)
        page.keyboard.press("Escape")
        return f"no menu; opened instead: {other}" if other else "nothing opened"
    found = {"label": page.get_attribute(MENU, "aria-label"), "items": read_menu(page, MENU)}
    page.keyboard.press("Escape")
    return found


def choose(page, label: str) -> str | None:
    """Click the first enabled entry called ``label`` in any menu or submenu; where it was, or None."""
    titles = page.eval_on_selector_all(".menus .title", "els => els.map(e => e.textContent.trim())")
    for i, title in enumerate(titles):
        page.keyboard.press("Escape")
        page.click(f".menus .title >> nth={i}")
        drop = page.locator(f"#menu-drop-{i}")
        for parent in drop.locator("button[aria-haspopup=menu]:not([disabled])").all():
            parent.hover()
            page.wait_for_timeout(100)
            entry = drop.locator("ul.sub button:not([disabled])", has=page.locator(f'.label:text-is("{label}")'))
            if entry.count():
                where = f"{title} ▸ {parent.locator('.label').text_content().strip()} ▸ {label}"
                entry.first.click()
                return where
    page.keyboard.press("Escape")
    return None


def object_menu(person, label: str, what: str) -> dict[str, Any] | str:
    """Insert something with the entry ``label`` (accepting a dialog's defaults) and right-click it."""
    page = person.page
    before = page.locator(OBJECTS).count()
    where = choose(page, label) if label != "Table…" else _insert_table(page)
    if where is None:
        return f"no enabled entry {label!r}"
    page.wait_for_timeout(600)
    if page.locator(OBJECTS).count() <= before:
        return f"{where}: no {what} appeared"
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    found = context_menu(page, page.locator(OBJECTS).last)
    if isinstance(found, dict):
        found["made with"] = where
    return found


def _insert_table(page) -> str:
    page.click('.menus .title:text-is("Insert")')
    page.locator(".menus .drop button", has=page.locator('.label:text-is("Table…")')).click()
    page.wait_for_timeout(400)
    page.locator("dialog[open]").locator('button[type=submit], button:text-is("Insert")').first.click()
    return "Insert ▸ Table…"


def contexts(person) -> dict[str, Any]:
    """The context menus of the places each app has one, as the owner."""
    page, found = person.page, {}
    if person.app == "computes":
        found["cell"] = context_menu(page, page.locator("[role=grid]"), {"x": 120, "y": 39})
        found["column header"] = context_menu(page, page.locator(".colhead").nth(1))
        found["row header"] = context_menu(page, page.locator(".rowhead").nth(1))
    elif person.app == "composes":
        page.locator("[data-testid=text]").click()
        page.keyboard.type("Hello world")
        found["paragraph"] = context_menu(page, page.locator("[data-testid=text] [data-paragraph]").first)
        found["table"] = object_menu(person, "Table…", "table")
    else:
        found["slide"] = context_menu(page, page.locator("[data-testid=slide]"), {"x": 30, "y": 300})
    found["object"] = object_menu(person, "Mermaid", "object")
    return found


def switch_to_german(person) -> None:
    page = person.page
    page.click('.menus .title:text-is("Preferences")')
    person.menu_item("App Language").hover()
    page.locator(".menus .drop.sub button", has_text="Deutsch").click()
    page.wait_for_timeout(500)


def capture_app(browser, url: str, app: str) -> dict[str, Any]:
    """One app: its menus for the three roles, in German for the owner, and its context menus."""
    ann = e2e.Person(browser, url, f"audit-{app}", "Ann", app=app)
    eddie = e2e.Person(browser, url, f"audit-{app}", "Eddie", app=app)
    vera = e2e.Person(browser, url, f"audit-{app}", "Vera", app=app)
    try:
        ann.create()
        ann.share(eddie, "editor")
        ann.share(vera, "viewer")
        found: dict[str, Any] = {"owner": top_menus(ann.page), "contexts": contexts(ann)}
        for person, role in ((eddie, "editor"), (vera, "viewer")):
            person.open()
            person.wait_until_open()
            found[role] = top_menus(person.page)
        switch_to_german(ann)
        found["owner (de)"] = top_menus(ann.page)
        found["console errors"] = ann.errors + eddie.errors + vera.errors
        return found
    finally:
        for person in (ann, eddie, vera):
            with contextlib.suppress(Exception):
                person.close()


def main(argv: list[str] | None = None) -> int:
    from playwright.sync_api import sync_playwright

    out = Path((argv or sys.argv[1:] or [str(OUT)])[0])
    found: dict[str, Any] = {"browser": e2e.BROWSER}
    with (
        tempfile.TemporaryDirectory(prefix="claudia-menu-audit-") as folder,
        server(Path(folder), "--web", str(e2e.BUILT)) as running,
        sync_playwright() as play,
    ):
        browser = e2e._launch(play)  # noqa: SLF001 - the same browser choice as the specs
        for app in APPS:
            found[app] = capture_app(browser, running.url, app)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
