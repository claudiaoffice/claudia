"""The window of a Claudia shell: header bar with the native menus, and the page below it (D40, D42).

The window owns the GIO actions of the manifest. What an action does depends on who carries it out (``Kind``): the web
page (the window sends an ``action`` message through the :class:`~claudia_shell_gtk.bridge.Bridge`), the web view's own
editing commands (cut, copy, paste), or the shell itself (quit, About).

The page itself is made by a ``page_factory`` (see ``webpage.WebPage``); the window only needs a small interface from
it, so the window is tested without WebKit.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from importlib import resources
from typing import Any, Protocol

from ._gi import Adw, Gio, GLib, Gtk
from ._version import __version__
from .bridge import Bridge
from .identity import AppIdentity
from .manifest import Action, Kind, Manifest, about_links, composes, menu_elements

__all__ = ["ComposesWindow", "Page", "PageFactory"]

log = logging.getLogger(__name__)

# The page's own dark-mode choice (D120's View ▸ Dark Mode, a `Kind.PAGE` checkable) is the one thing native chrome
# also needs to know: see `set_action_states`'s use of it below.
_DARK_ACTION = "view.dark"


class Page(Protocol):
    """What the window needs from the web page it shows."""

    widget: Any

    def send(self, raw: str) -> None: ...
    def load(self, url: str) -> None: ...
    def run_editing_command(self, command: str) -> None: ...
    def close(self) -> None: ...


PageFactory = Callable[..., Page]
"""``factory(origin=, on_message=, on_reset=, on_problem=, on_download=)`` makes the page for a server at ``origin``."""


def _layout() -> str:
    """The window layout with the menus of the manifest merged in."""
    text = resources.files("claudia_shell_gtk").joinpath("data/window.ui").read_text(encoding="utf-8")
    return text.replace("<!-- menus -->", menu_elements(composes()))


@Gtk.Template(string=_layout())
class ComposesWindow(Adw.ApplicationWindow):
    """The main window of claudia composes."""

    __gtype_name__ = "ClaudiaWindow"

    toasts = Gtk.Template.Child()
    pages = Gtk.Template.Child()
    error_page = Gtk.Template.Child()
    error_label = Gtk.Template.Child()
    web_slot = Gtk.Template.Child()

    def __init__(
        self,
        identity: AppIdentity,
        manifest: Manifest,
        *,
        page_factory: PageFactory,
        locale: str | None = None,
        **properties: Any,
    ):
        super().__init__(**properties)
        self._identity = identity
        self._manifest = manifest
        self._page_factory = page_factory
        self._page: Page | None = None
        self.about_dialog: Adw.Dialog | None = None
        self.last_toast = ""
        self._bridge = Bridge(
            manifest,
            self._send_to_page,
            shell_version=__version__,
            locale=locale,
            on_states=self.set_action_states,
            on_ready=self._page_is_ready,
        )
        # GTK emits "destroy" only when the object is finally disposed, which can be long after the window is gone:
        # the page is released when the window is closed (and by the application on shutdown), "destroy" is the net.
        self.connect("close-request", self._on_close_request)
        self.connect("destroy", lambda _window: self.release_page())
        self.set_title(identity.title)
        self.set_icon_name(identity.application_id)
        for action in manifest.actions:
            self._add_action(action)

    # ------------------------------------------------------------------------------------------------ what is shown

    @property
    def visible_page(self) -> str:
        """``starting``, ``error`` or ``web``."""
        return str(self.pages.get_visible_child_name())

    @property
    def error_title(self) -> str:
        return str(self.error_page.get_title())

    @property
    def error_details(self) -> str:
        return str(self.error_label.get_label())

    def show_error(self, title: str, details: str = "") -> None:
        """Replace the window's content with a problem report that the person can read and copy from."""
        log.error("%s: %s", title, details)
        self.error_page.set_title(title)
        self.error_label.set_label(details)
        self.error_label.set_visible(bool(details))
        self.pages.set_visible_child_name("error")

    def show_page(self, url: str) -> None:
        """Show the web page of the server at ``url`` (made and loaded on the first call)."""
        if self._page is None:
            self._page = self._page_factory(
                origin=url,
                on_message=self._bridge.receive,
                on_reset=self._page_is_reloading,
                on_problem=self.show_error,
                on_download=lambda path: self.toast(f"Saved {path.name} to {path.parent.name}"),
            )
            self.web_slot.append(self._page.widget)
            self._page.load(url)
            self._set_editing_enabled(True)
        self.pages.set_visible_child_name("web")

    def toast(self, text: str) -> None:
        """A short message at the bottom of the window."""
        self.last_toast = text
        self.toasts.add_toast(Adw.Toast.new(text))

    # ---------------------------------------------------------------------------------------------------- actions

    def _add_action(self, spec: Action) -> None:
        if spec.kind is Kind.PAGE and spec.checkable:
            action = Gio.SimpleAction.new_stateful(spec.id, None, GLib.Variant.new_boolean(False))
            action.connect("change-state", self._on_change_state)
        else:
            action = Gio.SimpleAction.new(spec.id, None)
            action.connect("activate", self._on_activate)
        if spec.kind is not Kind.SHELL:
            action.set_enabled(False)  # until the page is there (page actions) or the page is shown (editing)
        self.add_action(action)

    def _on_activate(self, action: Gio.SimpleAction, _parameter: Any) -> None:
        spec = self._manifest.action(action.get_name())
        if spec.kind is Kind.PAGE:
            self._bridge.send_action(spec.id)
        elif spec.kind is Kind.EDITING and self._page is not None and spec.editing:
            self._page.run_editing_command(spec.editing)
        elif spec.id == "file.quit":
            self.close()
        elif spec.id == "help.about":
            self._show_about()
        else:  # a new shell action without a handler is a mistake in the shell, not in the person's request
            log.error("nothing carries out the action %s", spec.id)

    def _on_change_state(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        """The person ticked or unticked a choice: ask the page for it. The state changes when the page confirms."""
        self._bridge.send_action(action.get_name(), "on" if value.get_boolean() else "off")

    def set_action_states(self, states: dict[str, dict[str, Any]]) -> None:
        """Apply the ``enabled`` and ``checked`` states that the page reported."""
        for name, state in states.items():
            action = self.lookup_action(name)
            if action is None:
                continue
            if "enabled" in state:
                action.set_enabled(bool(state["enabled"]))
            if "checked" in state and action.get_state() is not None:
                action.set_state(GLib.Variant.new_boolean(bool(state["checked"])))
            if name == _DARK_ACTION and "checked" in state:
                self._sync_native_theme(bool(state["checked"]))

    @staticmethod
    def _sync_native_theme(dark: bool) -> None:
        """Native dialogs (the About dialog, D28) are plain GTK/libadwaita — a rendering stack entirely separate
        from the page's own `data-theme` CSS, with nothing tying the two together unless the shell says so itself
        (the owner's 2026-11-06 report: the About dialog stayed whatever colour GTK's own theme was, regardless of
        the document's own Dark Mode setting). The page already reports `view.dark`'s *resolved* state — light or
        dark, "system" already settled — on every change, click or system-triggered alike (`TextWorkspace.vue`'s
        `menus`, `shell-bridge.ts`'s `reportStates`); this is the other half. `FORCE_*`, not `PREFER_*`: the whole
        point of the tri-state is that a person can ask for dark regardless of what the desktop itself is set to,
        so the shell's own chrome has to be just as overridable."""
        scheme = Adw.ColorScheme.FORCE_DARK if dark else Adw.ColorScheme.FORCE_LIGHT
        Adw.StyleManager.get_default().set_color_scheme(scheme)

    def _set_page_actions_enabled(self, enabled: bool) -> None:
        for spec in self._manifest.actions:
            if spec.kind is Kind.PAGE:
                self.lookup_action(spec.id).set_enabled(enabled)

    def _set_editing_enabled(self, enabled: bool) -> None:
        for spec in self._manifest.actions:
            if spec.kind is Kind.EDITING:
                self.lookup_action(spec.id).set_enabled(enabled)

    def _page_is_ready(self) -> None:
        self._set_page_actions_enabled(True)

    def _page_is_reloading(self) -> None:
        self._bridge.reset()
        self._set_page_actions_enabled(False)

    def _on_close_request(self, _window: Any) -> bool:
        self.release_page()
        return False  # let the window close

    def release_page(self) -> None:
        """Let the page go (it holds on to the network session that all web views share). Safe to repeat."""
        page, self._page = self._page, None
        if page is not None:
            page.close()

    def _send_to_page(self, raw: str) -> None:
        if self._page is not None:
            self._page.send(raw)

    def _show_about(self) -> None:
        """D28's shared About dialog, built by hand rather than from ``Adw.AboutDialog``: that widget's own "Website"
        / "Troubleshooting" / "Legal" row is a set of full-width, Adwaita-sized pill buttons — correct content,
        wrong size next to the web app's own, far smaller buttons (the owner's 2026-11-06 report). Content-sized
        buttons in a plain `Adw.Dialog`, styled by the `.about-link` rule in `data/style.css`, give the same
        content without inheriting a size we do not otherwise use anywhere in this shell."""
        dialog = Adw.Dialog(content_width=300)
        view = Adw.ToolbarView()
        header = Adw.HeaderBar(show_title=False)
        view.add_top_bar(header)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, halign=Gtk.Align.CENTER)
        body.set_margin_start(24)
        body.set_margin_end(24)
        body.set_margin_bottom(24)

        icon = Gtk.Image.new_from_icon_name(self._identity.application_id)
        icon.set_pixel_size(64)
        icon.set_margin_bottom(12)
        body.append(icon)

        title = Gtk.Label(label=self._identity.title)
        title.add_css_class("title-3")
        body.append(title)

        version = Gtk.Label(label=f"v{__version__}")
        version.add_css_class("dim-label")
        version.add_css_class("caption")
        version.set_margin_bottom(16)
        body.append(version)

        links = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER)
        for label, url in about_links():
            button = Gtk.Button(label=label)
            button.add_css_class("about-link")
            button.connect("clicked", lambda _b, u=url: self._open_link(u))
            links.append(button)
        body.append(links)

        view.set_content(body)
        dialog.set_child(view)
        self.about_dialog = dialog
        dialog.present(self)

    @staticmethod
    def _open_link(url: str) -> None:
        Gio.AppInfo.launch_default_for_uri_async(url, None, None, None)
