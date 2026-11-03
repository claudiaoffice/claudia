"""The shell's side of the conversation with the page (shell contract, E5.12), without any GTK.

The window gives the bridge a ``send`` function (which hands text to the web view) and feeds it every message the page
posts. The page is not trusted to be well behaved: its messages are checked against the contract, only the page-to-shell
types are accepted from it, and a state report may only name actions that the manifest has.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from . import contract
from .contract import ContractError, UnknownMessageType
from .manifest import Kind, Manifest

__all__ = ["Bridge"]

log = logging.getLogger(__name__)

CAPABILITIES = ("native-menu", "actions")
"""What this shell offers the page: it shows the menus itself, and it sends ``action`` messages for them."""


class Bridge:
    """Messages between one web page and the shell."""

    def __init__(
        self,
        manifest: Manifest,
        send: Callable[[str], None],
        *,
        shell_version: str,
        on_states: Callable[[dict[str, dict[str, Any]]], None] | None = None,
        on_ready: Callable[[], None] | None = None,
    ) -> None:
        self._manifest = manifest
        self._send = send
        self._shell_version = shell_version
        self._on_states = on_states or (lambda _states: None)
        self._on_ready = on_ready or (lambda: None)
        self._ready = False
        self.page_errors: list[str] = []
        """What the page reported as wrong with the shell's messages, for the log and the diagnostics."""

    @property
    def ready(self) -> bool:
        """Has the page said a ``hello`` that the shell accepted?"""
        return self._ready

    def reset(self) -> None:
        """Forget the page (the web view is loading another one)."""
        self._ready = False

    # ------------------------------------------------------------------------------------------ from the page

    def receive(self, raw: str) -> None:
        """Handle one message that the page posted."""
        try:
            message = contract.parse(raw)
        except UnknownMessageType as unknown:
            log.info("ignored a message the page sent: %s", unknown)
            return
        except ContractError as problem:
            self._reply(contract.error_for(problem))
            return
        handler = {"hello": self._hello, "action_state": self._states, "error": self._page_error}.get(message["type"])
        if handler is None:
            self._reply(contract.error("bad_message", f"'{message['type']}' is sent by the shell, not by the page"))
            return
        handler(message)

    def _hello(self, message: contract.Message) -> None:
        if message["app"] != self._manifest.app:
            self._reply(
                contract.error("bad_message", f"this shell shows {self._manifest.app}, the page shows {message['app']}")
            )
            return
        try:
            version = contract.negotiate(message)
        except ContractError as problem:
            self._reply(contract.error_for(problem))
            return
        self._ready = True
        self._reply(contract.welcome(shell_version=self._shell_version, capabilities=CAPABILITIES, contract=version))
        self._on_ready()

    def _states(self, message: contract.Message) -> None:
        if not self._ready:
            self._reply(contract.error("bad_message", "say 'hello' before reporting action states"))
            return
        known = {a.id for a in self._manifest.actions}
        states: dict[str, dict[str, Any]] = message["states"]
        unknown = sorted(name for name in states if name not in known)
        applied = {name: state for name, state in states.items() if name in known}
        if applied:
            self._on_states(applied)
        if unknown:
            self._reply(contract.error("unknown_action", f"no such action: {', '.join(unknown)}"))

    def _page_error(self, message: contract.Message) -> None:
        text = f"{message['code']}: {message['message']}"
        self.page_errors.append(text)
        log.warning("the page reports a problem: %s", text)

    # -------------------------------------------------------------------------------------------- to the page

    def send_action(self, action_id: str, target: str | None = None) -> bool:
        """Tell the page to carry out a menu action. ``False`` when the page is not there to do it.

        Raises ``KeyError`` for an action the manifest does not have and ``ValueError`` for one that the page does not
        carry out (quit, About and the editing commands are the shell's own).
        """
        action = self._manifest.action(action_id)
        if action.kind is not Kind.PAGE:
            raise ValueError(f"{action_id} is carried out by the {action.kind.value}, not by the page")
        if not self._ready:
            return False
        self._reply(contract.action(action_id, target))
        return True

    def _reply(self, message: contract.Message) -> None:
        import json

        self._send(json.dumps(message, ensure_ascii=False))
