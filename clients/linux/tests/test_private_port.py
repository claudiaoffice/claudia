"""A person's private server: its port and its proof (E8.5, D1620, D1621). The twin of
``clients/neutralino/tests/private-port.test.ts``; the expected values are those of
``clients/contract/private-port.vectors.json``, which the server's and the macOS/Windows client's tests read too."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claudia_shell_gtk.owner_key import OWNER_KEY_FILE, owner_answer, owner_key, proves
from claudia_shell_gtk.private_port import PRIVATE_PORTS, private_port, walk_from

VECTORS = json.loads(
    (Path(__file__).resolve().parents[2] / "contract" / "private-port.vectors.json").read_text(encoding="utf-8")
)
CASES = VECTORS["proofs"]["cases"]


@pytest.mark.parametrize("case", VECTORS["ports"]["byUid"], ids=lambda case: f"uid {case['uid']}")
def test_the_port_follows_the_account_number(case: dict) -> None:
    assert private_port(case["uid"]) == case["port"]


def test_the_ports_are_never_8765_and_below_those_the_system_hands_out() -> None:
    assert PRIVATE_PORTS == (20000, 29999)


def test_while_her_port_is_held_the_others_are_tried_in_one_order() -> None:
    order = list(walk_from(29998))
    assert order[:3] == [29999, 20000, 20001]
    assert len(order) == 9999
    assert 29998 not in order


def test_her_key_is_the_one_another_window_wrote_first(tmp_path: Path) -> None:
    theirs = "ab" * 32

    def make() -> bytes:
        (tmp_path / OWNER_KEY_FILE).write_text(theirs + "\n", encoding="utf-8")  # the other window, a moment earlier
        return bytes(32)

    assert owner_key(tmp_path, make=make).key.hex() == theirs
    assert (tmp_path / OWNER_KEY_FILE).read_text(encoding="utf-8").strip() == theirs


@pytest.mark.parametrize("case", CASES, ids=lambda case: f"port {case['port']}")
def test_the_proof_covers_the_key_and_the_port_the_server_listens_on(case: dict) -> None:
    assert owner_answer(bytes.fromhex(case["key"]), case["port"], case["challenge"]) == case["answer"]


def test_only_the_right_answer_proves_it() -> None:
    case = CASES[0]
    key = bytes.fromhex(case["key"])
    assert proves(key, case["port"], case["challenge"], case["answer"])
    assert not proves(key, case["port"] + 1, case["challenge"], case["answer"])
    assert not proves(key, case["port"], case["challenge"], case["answer"].upper())
    assert not proves(key, case["port"], case["challenge"], case["answer"][:-2])
    assert not proves(key, case["port"], case["challenge"], 42)
    assert not proves(key, case["port"], case["challenge"], "ü" * 64)  # whatever answers on the port
