"""The real WebKit page against a stub site whose menu is built like the web app's (``MenuBar.vue``).

These tests pin the rules of ``webpage.py`` and the behaviour of the page adapter ``shim.js``: hello and welcome, the
menu actions carried out through the page's own menu, states read back, links that stay inside the application, and
downloads that stay inside the Downloads folder.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path

import pytest
from support import pump, pump_for

from claudia_shell_gtk import manifest
from claudia_shell_gtk.bridge import Bridge

pytestmark = pytest.mark.gtk

# The markup and behaviour of MenuBar.vue: titles open a list that exists only while it is open, items are buttons with
# role=menuitem, a tick span and aria-checked/disabled; choosing an item closes the list.
SITE = """<!doctype html><meta charset=utf-8><title>stub</title>
<style>nav.menus{display:flex;height:32px;background:#eee}</style>
<nav class="menus" aria-label="menu"></nav>
<main id="doc">text</main>
<a id="out" href="https://example.org/page">out</a>
<a id="file" href="/file.md" download="../../evil.md">file</a>
<script>
const state = {view: 'flow', authors: false, canUndo: false}
window.clicked = []
let open = null
const menus = () => [
  {label: 'File', items: [{label: 'Save', hint: 'Ctrl+S'}, {label: 'Save as Markdown…'}]},
  {label: 'Edit', items: [
    {label: state.canUndo ? 'Undo typing' : 'Undo', disabled: !state.canUndo},
    {label: 'Redo', disabled: true}]},
  {label: 'View', items: [
    {label: 'Flow', checked: state.view === 'flow', run() { state.view = 'flow' }},
    {label: 'Page', checked: state.view === 'page', run() { state.view = 'page' }},
    {label: 'Show who wrote what', checked: state.authors, run() { state.authors = !state.authors }}]},
]
function render() {
  const nav = document.querySelector('nav.menus')
  nav.innerHTML = ''
  menus().forEach((menu, i) => {
    const wrap = document.createElement('div'); wrap.className = 'menu'
    const title = document.createElement('button'); title.className = 'title' + (open === i ? ' open' : '')
    title.textContent = menu.label
    title.onclick = () => { open = open === i ? null : i; render() }
    wrap.appendChild(title)
    if (open === i) {
      const ul = document.createElement('ul'); ul.className = 'drop'; ul.setAttribute('role', 'menu')
      menu.items.forEach((item) => {
        const li = document.createElement('li'); const b = document.createElement('button')
        b.setAttribute('role', 'menuitem'); b.disabled = !!item.disabled
        if (item.checked !== undefined) b.setAttribute('aria-checked', String(item.checked))
        const tick = item.checked === undefined ? '' : '<i class="tick">' + (item.checked ? '✓' : '') + '</i>'
        b.innerHTML = '<span>' + tick + item.label + '</span>'
        b.onclick = () => {
          if (item.disabled) return
          open = null; window.clicked.push(item.label); item.run && item.run(); render()
        }
        li.appendChild(b); ul.appendChild(li)
      })
      wrap.appendChild(ul)
    }
    nav.appendChild(wrap)
  })
}
render()
</script>"""


class Site(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (name fixed by http.server)
        if self.path == "/file.md":
            body, kind = b"# a file\n", "text/markdown"
        else:
            body, kind = SITE.encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def site() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


class Rig:
    """A web page wired to a real bridge, as the window wires it, and a record of what happened."""

    def __init__(self, origin: str, tmp_path: Path, *, shim_origin: str | None = None) -> None:
        from claudia_shell_gtk._gi import Gtk
        from claudia_shell_gtk.webpage import WebPage

        self.states: dict[str, dict] = {}
        self.messages: list[str] = []
        self.opened: list[str] = []
        self.downloaded: list[Path] = []
        self.problems: list[tuple[str, str]] = []
        self.downloads = tmp_path / "Downloads"
        self.bridge = Bridge(
            manifest.composes(),
            lambda raw: self.page.send(raw),  # noqa: PLW0108 (self.page exists only after the bridge)
            shell_version="test",
            on_states=self.states.update,
        )

        def on_message(raw: str) -> None:
            self.messages.append(raw)
            self.bridge.receive(raw)

        self.page = WebPage(
            origin=shim_origin or origin,
            shim=resources.files("claudia_shell_gtk").joinpath("data/shim.js").read_text(encoding="utf-8"),
            routes=resources.files("claudia_shell_gtk").joinpath("data/webroutes.json").read_text(encoding="utf-8"),
            downloads_dir=self.downloads,
            on_message=on_message,
            on_reset=self.bridge.reset,
            on_problem=lambda title, details: self.problems.append((title, details)),
            on_download=self.downloaded.append,
            open_external=self.opened.append,
        )
        self.window = Gtk.Window()
        self.window.set_default_size(900, 600)
        self.window.set_child(self.page.widget)
        self.window.present()
        self.page.load(origin + "/")

    def run_js(self, source: str) -> None:
        self.page.widget.evaluate_javascript(source, -1, None, None, None, None)

    def clicked(self) -> list[str]:
        """What the stub page's menu items recorded (read through the page, in its own world)."""
        result: list[list[str]] = []

        def got(view, task) -> None:
            value = view.evaluate_javascript_finish(task)
            result.append(json.loads(value.to_string()))

        self.page.widget.evaluate_javascript("JSON.stringify(window.clicked)", -1, None, None, None, got)
        pump(lambda: result, what="the page's answer")
        return result[0]

    def close(self) -> None:
        self.page.close()
        self.window.destroy()


@pytest.fixture
def rig(site: str, tmp_path: Path) -> Iterator[Rig]:
    try:
        import claudia_shell_gtk.webpage  # noqa: F401
    except (ImportError, ValueError) as problem:
        pytest.skip(f"WebKitGTK 6.0 is not available ({problem})")
    rig = Rig(site, tmp_path)
    yield rig
    rig.close()


def test_the_page_says_hello_and_is_welcomed(rig: Rig) -> None:
    pump(lambda: rig.bridge.ready, what="hello")
    assert json.loads(rig.messages[0]) == {"type": "hello", "contract": 1, "app": "composes"}


def test_the_states_of_the_web_menu_reach_the_shell(rig: Rig) -> None:
    pump(lambda: "view.page" in rig.states and "edit.undo" in rig.states, what="the first states")
    assert rig.states["file.save"] == {"enabled": True}
    assert rig.states["edit.undo"] == {"enabled": False}
    assert rig.states["view.page"] == {"enabled": True, "checked": False}
    assert rig.states["view.authors"] == {"enabled": True, "checked": False}


def test_the_states_change_when_the_page_changes(rig: Rig) -> None:
    pump(lambda: "edit.undo" in rig.states)
    rig.run_js("state.canUndo = true")
    pump(lambda: rig.states["edit.undo"]["enabled"], what="Undo to become enabled")


def test_an_action_is_carried_out_through_the_pages_own_menu(rig: Rig) -> None:
    pump(lambda: rig.bridge.ready)
    rig.bridge.send_action("file.save")
    pump(lambda: rig.clicked() == ["Save"], what="the click")


def test_a_prefixed_item_like_undo_typing_is_found(rig: Rig) -> None:
    pump(lambda: "edit.undo" in rig.states)
    rig.run_js("state.canUndo = true")
    pump(lambda: rig.states["edit.undo"]["enabled"])
    rig.bridge.send_action("edit.undo")
    pump(lambda: rig.clicked() == ["Undo typing"])


def test_an_action_with_a_target_is_idempotent(rig: Rig) -> None:
    pump(lambda: rig.bridge.ready)
    rig.bridge.send_action("view.page", "on")
    pump(lambda: rig.states.get("view.page", {}).get("checked") is True, what="Page to be on")
    rig.bridge.send_action("view.page", "on")
    pump_for(0.6)
    assert rig.clicked() == ["Page"]  # the second request found it on already
    rig.bridge.send_action("view.page", "off")  # off is the other item of the pair
    pump(lambda: rig.states["view.page"]["checked"] is False)
    assert rig.clicked() == ["Page", "Flow"]


def test_an_action_without_a_target_toggles(rig: Rig) -> None:
    pump(lambda: rig.bridge.ready)
    rig.bridge.send_action("view.authors")
    pump(lambda: rig.states.get("view.authors", {}).get("checked") is True)
    rig.bridge.send_action("view.authors")
    pump(lambda: rig.states["view.authors"]["checked"] is False)


def test_a_disabled_item_is_not_clicked(rig: Rig) -> None:
    pump(lambda: "edit.redo" in rig.states)
    rig.bridge.send_action("edit.redo")
    pump_for(0.6)
    assert rig.clicked() == []


def test_the_web_menu_bar_is_hidden_but_keeps_its_place(rig: Rig) -> None:
    pump(lambda: rig.bridge.ready)
    result: list[str] = []

    def got(view, task) -> None:
        result.append(view.evaluate_javascript_finish(task).to_string())

    rig.page.widget.evaluate_javascript(
        "(() => { const s = getComputedStyle(document.querySelector('nav.menus'));"
        " return s.visibility + '/' + s.height })()",
        -1,
        None,
        None,
        None,
        got,
    )
    pump(lambda: result)
    assert result == ["hidden/0px"]


def test_a_link_to_another_site_opens_in_the_default_browser_and_the_window_stays(rig: Rig, site: str) -> None:
    pump(lambda: rig.bridge.ready and not rig.page.widget.is_loading(), what="the page to be loaded")
    rig.run_js("document.getElementById('out').click()")
    pump(lambda: rig.opened, what="the link to be handed on")
    assert rig.opened == ["https://example.org/page"]
    assert rig.page.widget.get_uri().startswith(site)


def test_a_download_is_saved_in_the_downloads_folder_under_a_safe_name(rig: Rig, tmp_path: Path) -> None:
    pump(lambda: rig.bridge.ready and not rig.page.widget.is_loading(), what="the page to be loaded")
    rig.run_js("document.getElementById('file').click()")
    pump(lambda: rig.downloaded, what="the download")
    assert rig.downloaded == [tmp_path / "Downloads" / "evil.md"]
    assert (tmp_path / "Downloads" / "evil.md").read_text() == "# a file\n"
    assert not (tmp_path.parent / "evil.md").exists()


def test_nothing_contacts_another_host_by_itself(rig: Rig) -> None:
    """The links of a text must not cause DNS look-ups, and there is no WebRTC or camera: privacy first."""
    settings = rig.page.widget.get_settings()
    assert not settings.get_enable_dns_prefetching()
    assert not settings.get_enable_webrtc()
    assert not settings.get_enable_media_stream()


def test_a_page_of_another_origin_does_not_get_the_adapter(site: str, tmp_path: Path) -> None:
    """The adapter is injected for the server's origin only: here the shell believes its server is somewhere else."""
    try:
        import claudia_shell_gtk.webpage  # noqa: F401
    except (ImportError, ValueError) as problem:
        pytest.skip(f"WebKitGTK 6.0 is not available ({problem})")
    rig = Rig(site, tmp_path, shim_origin="http://127.0.0.1:9")
    try:
        pump_for(1.5)
        assert rig.messages == []
    finally:
        rig.close()
