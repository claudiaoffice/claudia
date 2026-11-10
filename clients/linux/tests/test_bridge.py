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


# ----------------------------------------------------------------------- connecting to another server (E5.8)


class ConnectRecorder(Recorder):
    def __init__(self) -> None:
        super().__init__()
        self.connects: list[str] = []
        self.lists: list[list] = []
        self.remembered = [{"origin": "https://a.example.org", "label": "A", "custom": False}]

    def on_connect(self, address: str) -> None:
        self.connects.append(address)

    def on_servers(self, entries: list) -> None:
        self.lists.append(entries)

    def server_list(self) -> list:
        return self.remembered


@pytest.fixture
def server_rig() -> tuple[Bridge, ConnectRecorder]:
    recorder = ConnectRecorder()
    bridge = Bridge(
        manifest.computes(),
        recorder.send,
        shell_version="0.1.0",
        on_states=recorder.on_states,
        on_ready=recorder.on_ready,
        on_connect=recorder.on_connect,
        on_servers=recorder.on_servers,
        server_list=recorder.server_list,
    )
    return bridge, recorder


def hello_computes() -> str:
    return hello(app="computes")


def test_a_shell_that_can_connect_says_so_and_then_sends_the_servers_it_remembers(server_rig) -> None:
    bridge, recorder = server_rig
    bridge.receive(hello_computes())
    assert recorder.sent[0]["capabilities"] == ["native-menu", "actions", "connect", "servers"]
    assert recorder.sent[1] == contract.servers(recorder.remembered)
    assert len(recorder.sent) == 2


def test_a_shell_without_these_abilities_does_not_claim_them(rig) -> None:
    bridge, recorder = rig
    bridge.receive(hello())
    assert recorder.sent[0]["capabilities"] == ["native-menu", "actions"]
    assert len(recorder.sent) == 1  # no servers message either


def test_the_page_asking_to_connect_reaches_the_shell(server_rig) -> None:
    bridge, recorder = server_rig
    bridge.receive(hello_computes())
    bridge.receive(json.dumps({"type": "connect", "address": "https://demo.example.org:8420"}))
    assert recorder.connects == ["https://demo.example.org:8420"]


def test_a_page_that_has_not_said_hello_cannot_make_the_shell_connect(server_rig) -> None:
    bridge, recorder = server_rig
    bridge.receive(json.dumps({"type": "connect", "address": "https://demo.example.org"}))
    assert recorder.connects == []
    assert recorder.sent[0]["type"] == "error"
    assert recorder.sent[0]["code"] == "bad_message"


def test_a_shell_that_cannot_connect_says_so_instead_of_silence(rig) -> None:
    bridge, recorder = rig
    bridge.receive(hello())
    bridge.receive(json.dumps({"type": "connect", "address": "https://demo.example.org"}))
    assert recorder.sent[-1]["type"] == "error"
    assert "connect" in recorder.sent[-1]["message"]


def test_the_list_the_page_hands_back_reaches_the_shell(server_rig) -> None:
    bridge, recorder = server_rig
    bridge.receive(hello_computes())
    entries = [{"origin": "https://b.example.org", "label": "B", "custom": True}]
    bridge.receive(json.dumps({"type": "servers", "servers": entries}))
    assert recorder.lists == [entries]


def test_a_list_before_hello_is_not_taken(server_rig) -> None:
    bridge, recorder = server_rig
    bridge.receive(json.dumps({"type": "servers", "servers": []}))
    assert recorder.lists == []
    assert recorder.sent[0]["code"] == "bad_message"


def test_the_shell_can_tell_the_page_why_a_connection_failed(server_rig) -> None:
    bridge, recorder = server_rig
    bridge.receive(hello_computes())
    recorder.sent.clear()
    assert bridge.send_connect_failed("unreachable", "Could not reach demo.example.org.")
    assert recorder.sent == [contract.connect_failed("unreachable", "Could not reach demo.example.org.")]


def test_nothing_is_sent_to_a_page_that_is_not_there_any_more(server_rig) -> None:
    bridge, recorder = server_rig  # no hello yet, or the page reloaded in the meantime
    assert not bridge.send_connect_failed("unreachable", "x")
    assert not bridge.send_servers([])
    assert recorder.sent == []


def test_the_shell_can_send_a_changed_list(server_rig) -> None:
    bridge, recorder = server_rig
    bridge.receive(hello_computes())
    recorder.sent.clear()
    assert bridge.send_servers(recorder.remembered)
    assert recorder.sent == [contract.servers(recorder.remembered)]


def test_the_page_may_not_send_what_only_the_shell_sends_with_a_server_list(server_rig) -> None:
    bridge, recorder = server_rig
    bridge.receive(hello_computes())
    recorder.sent.clear()
    bridge.receive(json.dumps({"type": "connect_failed", "code": "unreachable", "message": "x"}))
    assert recorder.sent[0]["code"] == "bad_message"


def test_a_page_that_does_not_know_its_apps_yet_is_welcomed_as_the_shells_own_app(rig) -> None:
    """The start page of a server that keeps its document list behind a secret cannot say which app it shows."""
    bridge, recorder = rig
    bridge.receive(json.dumps({"type": "hello", "contract": 1}))
    assert bridge.ready
    assert recorder.sent[0]["type"] == "welcome"


def test_a_page_that_names_another_app_is_still_refused(rig) -> None:
    bridge, recorder = rig
    bridge.receive(json.dumps({"type": "hello", "contract": 1, "app": "creates"}))
    assert not bridge.ready
    assert recorder.sent[0]["type"] == "error"
