"""The shell's side of the conversation with the page (E5.12), without any GTK: messages in, messages out.

The page is not trusted to be well behaved: what it sends is checked against the contract, only the page-to-shell
message types are accepted from it, and nothing it says can name an action the manifest does not have.
"""

from __future__ import annotations

import json

import pytest

from claudia_shell_gtk import contract, manifest
from claudia_shell_gtk.bridge import Bridge


class Recorder:
    """Stands in for the web view and for the window's reactions."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.states: list[dict] = []
        self.ready = 0

    def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    def on_states(self, states: dict) -> None:
        self.states.append(states)

    def on_ready(self) -> None:
        self.ready += 1


@pytest.fixture
def rig() -> tuple[Bridge, Recorder]:
    recorder = Recorder()
    bridge = Bridge(
        manifest.composes(),
        recorder.send,
        shell_version="0.1.0",
        on_states=recorder.on_states,
        on_ready=recorder.on_ready,
    )
    return bridge, recorder


def hello(**changes: object) -> str:
    return json.dumps({"type": "hello", "contract": 1, "app": "composes", **changes})


def test_a_hello_is_answered_with_a_welcome_that_says_the_shell_has_native_menus(rig) -> None:
    bridge, recorder = rig
    bridge.receive(hello())
    assert recorder.sent == [contract.welcome(shell_version="0.1.0", capabilities=["native-menu", "actions"])]
    assert bridge.ready
    assert recorder.ready == 1


def test_a_page_that_speaks_a_newer_contract_is_told_what_the_shell_speaks(rig) -> None:
    bridge, recorder = rig
    bridge.receive(hello(contract=9))
    assert recorder.sent[0]["type"] == "error"
    assert recorder.sent[0]["code"] == "unsupported_contract"
    assert recorder.sent[0]["supported"] == [1]
    assert not bridge.ready


def test_a_page_that_shows_another_app_is_refused(rig) -> None:
    """The server hands out one app; a computes page in the composes shell means something is mis-configured."""
    bridge, recorder = rig
    bridge.receive(hello(app="computes"))
    assert recorder.sent[0]["code"] == "bad_message"
    assert "composes" in recorder.sent[0]["message"]
    assert not bridge.ready


def test_a_page_that_reloads_says_hello_again_and_is_welcomed_again(rig) -> None:
    bridge, recorder = rig
    bridge.receive(hello())
    bridge.receive(hello())
    assert [m["type"] for m in recorder.sent] == ["welcome", "welcome"]
    assert recorder.ready == 2  # (the window forgets the old page's action states each time)


def test_text_that_is_not_json_is_answered_with_an_error(rig) -> None:
    bridge, recorder = rig
    bridge.receive("{nope")
    assert recorder.sent == [contract.error("bad_json", recorder.sent[0]["message"])]


def test_an_unknown_message_type_is_ignored_without_an_answer(rig) -> None:
    bridge, recorder = rig
    bridge.receive(json.dumps({"type": "telepathy"}))
    assert recorder.sent == []


@pytest.mark.parametrize("kind", ["welcome", "action"])
def test_the_page_may_not_send_what_only_the_shell_sends(rig, kind: str) -> None:
    bridge, recorder = rig
    bridge.receive(hello())
    recorder.sent.clear()
    message = contract.action("file.quit") if kind == "action" else contract.welcome(shell_version="9", capabilities=[])
    bridge.receive(json.dumps(message))
    assert recorder.sent[0]["code"] == "bad_message"
    assert "page" in recorder.sent[0]["message"]


def test_an_action_is_sent_to_the_page_once_it_has_said_hello(rig) -> None:
    bridge, recorder = rig
    bridge.receive(hello())
    recorder.sent.clear()
    assert bridge.send_action("file.save") is True
    assert bridge.send_action("view.page", target="on") is True
    assert recorder.sent == [
        {"type": "action", "action": "file.save"},
        {"type": "action", "action": "view.page", "target": "on"},
    ]


def test_an_action_is_not_sent_before_the_page_is_there(rig) -> None:
    bridge, recorder = rig
    assert bridge.send_action("file.save") is False
    assert recorder.sent == []


def test_an_action_the_manifest_does_not_have_is_never_sent(rig) -> None:
    bridge, _ = rig
    bridge.receive(hello())
    with pytest.raises(KeyError):
        bridge.send_action("file.explode")


def test_action_states_from_the_page_reach_the_window(rig) -> None:
    bridge, recorder = rig
    bridge.receive(hello())
    bridge.receive(json.dumps({"type": "action_state", "states": {"edit.undo": {"enabled": False}}}))
    assert recorder.states == [{"edit.undo": {"enabled": False}}]


def test_states_for_unknown_actions_are_reported_and_only_the_known_ones_applied(rig) -> None:
    bridge, recorder = rig
    bridge.receive(hello())
    recorder.sent.clear()
    states = {"edit.undo": {"enabled": True}, "file.explode": {"enabled": True}}
    bridge.receive(json.dumps({"type": "action_state", "states": states}))
    assert recorder.states == [{"edit.undo": {"enabled": True}}]
    assert recorder.sent[0]["code"] == "unknown_action"
    assert "file.explode" in recorder.sent[0]["message"]


def test_states_before_hello_are_ignored(rig) -> None:
    """A page that did not introduce itself does not get to change the menus."""
    bridge, recorder = rig
    bridge.receive(json.dumps({"type": "action_state", "states": {"edit.undo": {"enabled": True}}}))
    assert recorder.states == []
    assert recorder.sent[0]["code"] == "bad_message"


def test_an_error_from_the_page_is_remembered_for_the_log_and_not_answered(rig) -> None:
    bridge, recorder = rig
    bridge.receive(json.dumps({"type": "error", "code": "internal", "message": "the shim broke"}))
    assert recorder.sent == []
    assert bridge.page_errors == ["internal: the shim broke"]


def test_reset_forgets_the_page(rig) -> None:
    """When the web view starts loading another page the old hello no longer counts."""
    bridge, _ = rig
    bridge.receive(hello())
    bridge.reset()
    assert not bridge.ready
    assert bridge.send_action("file.save") is False


def test_an_action_that_the_page_does_not_carry_out_is_never_sent_to_it(rig) -> None:
    bridge, _ = rig
    bridge.receive(hello())
    with pytest.raises(ValueError, match="not by the page"):
        bridge.send_action("file.quit")
