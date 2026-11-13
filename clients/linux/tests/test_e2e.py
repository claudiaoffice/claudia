"""The whole thing: the real application with the real server (Python 3.14) and the built web frontend.

Slow (a few seconds) and dependent on the checkout: it needs ``uv sync`` (``.venv``) and a built frontend
(``npm run build`` in ``web``), and is skipped when either is missing. Run: ``xvfb-run -a pytest -m e2e``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from support import evaluate, pump, pump_for

from claudia_shell_gtk import identity
from claudia_shell_gtk.launch import find_frontend, find_server_python

pytestmark = [pytest.mark.gtk, pytest.mark.e2e]

# A new document first shows its recovery key; the person confirms having stored it and goes on.
CONFIRM_RECOVERY_KEY = """
(() => {
  if (!document.querySelector('[data-testid=recovery-key]')) return 'waiting'
  document.querySelector('input[type=checkbox]').click()
  const go = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Continue')
  if (go.disabled) return 'waiting'
  go.click()
  return 'confirmed'
})()
"""

FILL_AND_CREATE = """
(() => {
  // The GTK stack flips to "web" as soon as the view starts loading the URL, not once the Vue app inside has
  // mounted the Open dialog; running before that leaves these inputs missing, so wait for them like the recovery
  // key dialog above does.
  const field = (name) => document.querySelector('input[name=' + name + ']')
  const create = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Create document')
  if (!field('document') || !field('user') || !field('password') || !create) return 'waiting'
  const set = (name, value) => {
    const input = field(name)
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    setter.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  }
  set('document', 'e2e-notes'); set('user', 'ann'); set('password', 'Secret123x')
  create.click()
  return 'clicked'
})()
"""

# Type a word into the text the way the browser does it for a keyboard (Tools ▸ Insert Sample Text did this until it
# was taken out of the menu, 2026-11-12).
TYPE_A_WORD = """
(() => {
  const text = document.querySelector('[data-testid=text] [data-block]')
  if (!text) return 'waiting'
  text.focus()
  const range = document.createRange()
  range.selectNodeContents(text)
  range.collapse(false)
  const selection = getSelection()
  selection.removeAllRanges()
  selection.addRange(range)
  document.execCommand('insertText', false, 'Hello')
  return 'typed'
})()
"""


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if find_server_python() is None or find_frontend() is None:
        pytest.skip("needs the repository's .venv (uv sync) and a built frontend (npm run build in web)")
    try:
        import claudia_shell_gtk.webpage  # noqa: F401
    except (ImportError, ValueError) as problem:
        pytest.skip(f"WebKitGTK 6.0 is not available ({problem})")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_DOWNLOAD_DIR", str(tmp_path / "Downloads"))
    from claudia_shell_gtk._gi import Adw, Gio
    from claudia_shell_gtk.app import ClaudiaApp

    Adw.init()
    application = ClaudiaApp(identity.get("composes"), flags=Gio.ApplicationFlags.NON_UNIQUE)
    application.register(None)
    application.activate()
    yield application
    application.shutdown_for_test()


def test_composes_starts_its_server_shows_the_page_and_the_native_menu_drives_it(app, tmp_path: Path) -> None:
    window = app.window
    server_pid = app._server.pid  # noqa: SLF001
    assert window.visible_page == "starting"

    pump(lambda: window.visible_page == "web", timeout=60, what="the server to answer")
    bridge = window._bridge  # noqa: SLF001
    view = window._page.widget  # noqa: SLF001
    # The page is loaded only once its cache has been emptied (``WebPage._load_current``, asynchronous): until then
    # the view is shown but has no address yet (PROC-12).
    pump(lambda: view.get_uri() is not None, timeout=15, what="the page to start loading")
    assert view.get_uri().startswith("http://127.0.0.1:")

    # Before a document is open the page has no menus, so the page actions are disabled. The page itself has
    # nothing to say "hello" with yet either: the shell bridge is made by a workspace component (Workspace.vue /
    # TextWorkspace.vue / SlideWorkspace.vue), and nothing of that sort is on screen while the Open dialog is
    # (`app.vue` shows it exactly when no document is open) -- so `bridge.ready` only turns true once one is.
    pump(lambda: not window.lookup_action("file.save").get_enabled(), what="no menu yet, so nothing to do")
    assert not bridge.ready

    # Create a document through the page's own Open dialog.
    pump(lambda: evaluate(view, FILL_AND_CREATE) == "clicked", timeout=30, what="the create-document form to render")
    pump(lambda: evaluate(view, CONFIRM_RECOVERY_KEY) == "confirmed", timeout=30, what="the recovery key dialog")
    pump(lambda: bridge.ready, timeout=30, what="the now-open document's workspace to say hello")
    pump(lambda: window.lookup_action("file.save").get_enabled(), timeout=30, what="the document to open")
    pump(lambda: window.lookup_action("view.page").get_state() is not None)

    # The web menu bar is hidden but still has its place in the layout.
    style = evaluate(
        view,
        "(() => { const s = getComputedStyle(document.querySelector('nav.menus'));"
        " return s.visibility + '/' + s.height })()",
    )
    assert style == "hidden/0px"

    # Native "Page View" drives the web view setting and the tick follows.
    page_action = window.lookup_action("view.page")
    assert page_action.get_state().get_boolean() is False
    page_action.activate(None)
    pump(lambda: page_action.get_state().get_boolean() is True, timeout=15, what="the Page View tick")
    page_action.activate(None)
    pump(lambda: page_action.get_state().get_boolean() is False, timeout=15, what="the Page View tick to go")

    # After typing, Undo is possible (in the page, the way the browser types: `insertText`). It may be possible
    # before already: a new text's first step is its language, set by its maker's client (D915; UX-33 asks whether
    # that step should be undoable at all).
    pump(lambda: evaluate(view, TYPE_A_WORD) == "typed", timeout=15, what="the text to take a word")
    pump(lambda: window.lookup_action("edit.undo").get_enabled(), timeout=15, what="Undo to become possible")

    # A picture for people to look at.
    shot = os.environ.get("CLAUDIA_E2E_SCREENSHOT")
    if shot:
        pump_for(0.5)
        _screenshot(window, Path(shot))

    # Closing the window ends the server.
    app.shutdown_for_test()
    with pytest.raises(ProcessLookupError):
        os.kill(server_pid, 0)


def _screenshot(window, path: Path) -> None:
    from claudia_shell_gtk._gi import Gdk, Gtk

    paintable = Gtk.WidgetPaintable.new(window)
    snapshot = Gtk.Snapshot()
    paintable.snapshot(snapshot, window.get_width(), window.get_height())
    node = snapshot.to_node()
    renderer = window.get_native().get_renderer()
    texture = renderer.render_texture(node, None)
    texture.save_to_png(str(path))
    assert isinstance(texture, Gdk.Texture)
