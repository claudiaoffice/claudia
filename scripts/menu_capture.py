"""Write down the menus the web client really shows: every app, every role, in English and German (menu audit, phase 1).

``uv run python scripts/menu_capture.py [OUT]``  (default ``.claudia/menu-audit/web.json``)

Starts a real server of all three apps with the built web app (``./run-e2e.sh setup`` builds it), makes one document
per app as Ann (owner), shares it with Eddie (editor) and Vera (viewer), and opens every top menu and submenu for each
of them, then once more for Ann in German. It right-clicks the places that have a context menu, for each of them and
in German: a cell, a row and a column header (computes), a paragraph and a table (composes), the slide (creates) and an
object (all three: a Mermaid container, the one object every app can insert without a file or a dialog). Ann inserts
the table and the objects; the others right-click what she inserted.

What it writes is what a person sees: labels, the shortcut shown beside them, separators, greyed entries, ticks. The
ids of the actions are not in the page's markup; ``menu_audit.py`` finds them through the manifest. Chromium by default
(the browser the end-to-end tests use); ``$CLAUDIA_E2E_BROWSER=firefox`` for Firefox, where Playwright has one.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "tests" / "e2e"), str(ROOT / "tests" / "e2e" / "specs")]

import conftest as e2e  # noqa: E402 - the spec steps' Person: create, share, open, menu
from live import server  # noqa: E402
from playwright.sync_api import Error as PlaywrightError  # noqa: E402

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Locator, Page

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


def read_menu(page: Page, ul: str) -> list[dict[str, Any]]:
    """The entries of the open menu ``ul``; a submenu that is not greyed is opened by pointing at it and read too."""
    items = page.eval_on_selector(ul, _ITEMS_JS)
    for n, item in enumerate(items, start=1):
        if item.get("sub") and not item["disabled"]:
            page.locator(f"{ul} > li:nth-child({n}) > button").hover()
            sub = f"{ul} > li:nth-child({n}) ul[role=menu]"
            try:
                page.wait_for_selector(sub, timeout=2000)
                item["items"] = page.eval_on_selector(sub, _ITEMS_JS)
            except PlaywrightError:
                item["items"] = "did not open"
    return items


def titles(page: Page) -> list[str]:
    """The titles of the menu bar."""
    return page.eval_on_selector_all(".menus .title", "els => els.map(e => e.textContent.trim())")


def open_menu(page: Page, index: int) -> Locator:
    """Open the menu bar's menu number ``index``; its drop-down. Escape closes an open submenu first and then its menu;
    a title clicked while another menu is open may open on the pointer and close on the click, so a second click."""
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    drop = page.locator(f"#menu-drop-{index}")
    for _ in range(2):
        page.click(f".menus .title >> nth={index}")
        try:
            drop.wait_for(timeout=1500)
            return drop
        except PlaywrightError:
            continue
    drop.wait_for(timeout=5000)
    return drop


def top_menus(page: Page) -> dict[str, list[dict[str, Any]]]:
    """Every menu of the menu bar, by its title."""
    menus = {}
    for i, title in enumerate(titles(page)):
        open_menu(page, i)
        menus[title] = read_menu(page, f"#menu-drop-{i}")
    page.keyboard.press("Escape")
    return menus


def right_click(page: Page, target: Locator, position: dict[str, float] | None = None) -> None:
    """A right press of the mouse on ``target``: its middle, or ``position`` inside it."""
    target.scroll_into_view_if_needed(timeout=5000)
    box = target.bounding_box(timeout=5000)
    if box is None:
        raise PlaywrightError(f"{target} is not on the screen")
    x, y = (position["x"], position["y"]) if position else (box["width"] / 2, box["height"] / 2)
    page.mouse.click(box["x"] + x, box["y"] + y, button="right")


def context_menu(page: Page, target: Locator, position: dict[str, float] | None = None) -> dict[str, Any] | str:
    """The context menu a right press on ``target`` opens; when none opens, what opened instead, or that nothing did."""
    page.keyboard.press("Escape")
    right_click(page, target, position)
    try:
        page.wait_for_selector(MENU, timeout=2500)
    except PlaywrightError:  # no menu is an answer, not a failure
        other = page.evaluate(_OTHER_JS)
        page.keyboard.press("Escape")
        return f"no menu; opened instead: {other}" if other else "nothing opened"
    found = {"label": page.get_attribute(MENU, "aria-label"), "items": read_menu(page, MENU)}
    page.keyboard.press("Escape")
    return found


def choose_in_submenu(page: Page, label: str) -> str | None:
    """Click the first enabled submenu entry called ``label`` in any menu; where it was, or None."""
    for i, title in enumerate(titles(page)):
        drop = open_menu(page, i)
        for parent in drop.locator("button[aria-haspopup=menu]:not([disabled])").all():
            parent.hover()
            entry = drop.locator("ul.sub button:not([disabled])", has=page.locator(f'.label:text-is("{label}")'))
            try:
                entry.first.wait_for(timeout=500)
            except PlaywrightError:
                continue
            where = f"{title} ▸ {(parent.locator('.label').text_content() or '').strip()} ▸ {label}"
            entry.first.click()
            return where
    page.keyboard.press("Escape")
    return None


def insert_table(page: Page) -> str:
    """Insert ▸ Table… in composes, its dialog's defaults accepted."""
    open_menu(page, titles(page).index("Insert"))
    page.locator(".menus .drop button", has=page.locator('.label:text-is("Table…")')).click()
    page.locator("dialog[open]").locator('button[type=submit], button:text-is("Insert")').first.click()
    return "Insert ▸ Table…"


def inserted(page: Page, where: str | None, before: int) -> str | None:
    """Wait until there is one more object on the page than ``before``: None, or what went wrong."""
    if where is None:
        return "no enabled entry to insert it with"
    try:
        page.locator(OBJECTS).nth(before).wait_for(state="attached", timeout=5000)
    except PlaywrightError:
        return f"{where}: nothing appeared"
    page.keyboard.press("Escape")
    return None


def insert_things(person: e2e.Person) -> dict[str, str]:
    """As the owner: insert what everybody right-clicks later (a table in composes, a container everywhere)."""
    page, problems = person.page, {}
    if person.app == "composes":
        page.locator("[data-testid=text]").click()
        page.keyboard.type("Hello world")
        for _ in range(12):  # a paragraph well below where the table and the object go, for the paragraph's menu
            page.keyboard.press("Enter")
        page.keyboard.type("The last paragraph")
        page.keyboard.press("Control+Home")
        before = page.locator(OBJECTS).count()
        problem = inserted(page, insert_table(page), before)
        if problem:
            problems["table"] = problem
    before = page.locator(OBJECTS).count()
    problem = inserted(page, choose_in_submenu(page, "Mermaid"), before)
    if problem:
        problems["object"] = problem
    return problems


def uncovered(page: Page, selector: str) -> Locator:
    """The first element of ``selector`` whose middle is not covered by something else (a floating object)."""
    index = page.eval_on_selector_all(
        selector,
        """els => els.findIndex(e => { const r = e.getBoundingClientRect()
          const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)
          return r.height > 0 && hit !== null && e.contains(hit) })""",
    )
    if index < 0:
        raise PlaywrightError(f"every {selector} is covered")
    return page.locator(selector).nth(index)


def contexts(person: e2e.Person) -> dict[str, Any]:
    """The context menus of the places this app has one, for this person; objects by the menu they open."""
    page, found = person.page, {}
    if person.app == "computes":
        found["cell"] = context_menu(page, page.locator("[role=grid]"), {"x": 260, "y": 400})  # clear of objects
        found["column header"] = context_menu(page, page.locator(".colhead").nth(1))
        found["row header"] = context_menu(page, page.locator(".rowhead").nth(1))
    elif person.app == "composes":
        found["paragraph"] = context_menu(page, uncovered(page, "[data-testid=text] [data-paragraph]"))
    else:
        found["slide"] = context_menu(page, page.locator("[data-testid=slide]"), {"x": 30, "y": 300})
    for n in range(page.locator(OBJECTS).count()):
        menu = context_menu(page, page.locator(OBJECTS).nth(n))
        # "Table menu", "Tabellenmenü": the menu's own name says which it is
        place = "table" if isinstance(menu, dict) and "tab" in (menu["label"] or "").lower() else "object"
        found.setdefault(place, menu)
    return found


def switch_language(person: e2e.Person, autonym: str, file_menu: str) -> None:
    """Preferences ▸ App Language ▸ ``autonym`` (in whichever language the menus speak now), and wait until the menu
    bar's first menu is called ``file_menu``."""
    page = person.page
    names = titles(page)
    drop = open_menu(page, names.index("Preferences" if "Preferences" in names else "Einstellungen"))
    for parent in drop.locator("button[aria-haspopup=menu]").all():
        parent.hover()
        choice = drop.locator("ul.sub button", has_text=autonym)
        try:
            choice.first.wait_for(timeout=500)
        except PlaywrightError:
            continue
        choice.first.click()
        page.wait_for_selector(f'.menus .title:text-is("{file_menu}")')
        return
    raise PlaywrightError(f"no language {autonym} in Preferences")


def capture_app(browser: Browser, url: str, app: str) -> dict[str, Any]:
    """One app: menus and context menus for the three roles, and for the owner in German."""
    ann = e2e.Person(browser, url, f"audit-{app}", "Ann", app=app)
    eddie = e2e.Person(browser, url, f"audit-{app}", "Eddie", app=app)
    vera = e2e.Person(browser, url, f"audit-{app}", "Vera", app=app)
    people = {"owner": ann, "editor": eddie, "viewer": vera}
    try:
        ann.create()
        ann.share(eddie, "editor")
        ann.share(vera, "viewer")
        # The owner's menu bars first, in English and German: once she has inserted something, Undo names it
        found: dict[str, Any] = {"owner": top_menus(ann.page)}
        switch_language(ann, "Deutsch", "Datei")
        found["owner (de)"] = top_menus(ann.page)
        switch_language(ann, "English", "File")
        found["not inserted"] = insert_things(ann)
        for role, person in people.items():
            if person is not ann:
                person.open()
                person.wait_until_open()
                found[role] = top_menus(person.page)
            found[f"contexts ({role})"] = contexts(person)
        switch_language(ann, "Deutsch", "Datei")
        found["contexts (owner, de)"] = contexts(ann)
        found["console errors"] = [error for person in people.values() for error in person.errors]
        return found
    finally:
        for person in people.values():
            try:
                person.close()
            except PlaywrightError as error:  # a page that is already gone: said, the capture itself is done
                print(f"closing {person.name}'s page: {error}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Capture every app and write the JSON file."""
    from playwright.sync_api import sync_playwright

    out = Path((argv or sys.argv[1:] or [str(OUT)])[0])
    found: dict[str, Any] = {"browser": e2e.BROWSER}
    with (
        tempfile.TemporaryDirectory(prefix="claudia-menu-audit-") as folder,
        server(Path(folder), "--web", str(e2e.BUILT)) as running,
        sync_playwright() as play,
    ):
        browser = e2e._launch(play)  # noqa: SLF001 - the same browser choice as the specs, Firefox or Chromium
        for app in APPS:
            found[app] = capture_app(browser, running.url, app)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
