"""A person's private server proves to her own apps that it is hers (E8.5, D1620; CODE-99).

Her apps start the server with a key from her own state folder (``--owner-key-file``) and, before they use a server
they find on her port, ask it to answer a fresh challenge (``GET /api/owner``). The expected answers come from
``clients/contract/private-port.vectors.json``, which the clients' tests read too.
"""

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from claudia_core.testing import ListModel
from claudia_server import Hub, MemoryProvider, ScryptDirectory, create_app
from claudia_server.cli import UsageError, build_parser, owner_key_of
from claudia_server.owner_proof import load_key

VECTORS = json.loads(
    (Path(__file__).resolve().parents[3] / "clients" / "contract" / "private-port.vectors.json").read_text("utf-8")
)
CASES = VECTORS["proofs"]["cases"]
KEY = bytes.fromhex(CASES[0]["key"])
CHALLENGE = CASES[0]["challenge"]
THIS_COMPUTER = ("127.0.0.1", 50000)


def serve(owner_key=None):
    return create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(cost=2**4), owner_key=owner_key)


def client(app, *, port=20501, address=THIS_COMPUTER):
    return TestClient(app, base_url=f"http://127.0.0.1:{port}", client=address)


@pytest.mark.parametrize("case", CASES, ids=lambda case: f"port {case['port']}")
def test_it_answers_the_challenge_with_its_key_and_the_port_it_listens_on(case):
    with client(serve(bytes.fromhex(case["key"])), port=case["port"]) as http:
        answer = http.get("/api/owner", params={"challenge": case["challenge"]})
    assert answer.status_code == 200
    assert answer.json() == {"answer": case["answer"]}


def test_the_answer_says_nothing_of_the_key():
    with client(serve(KEY)) as http:
        text = http.get("/api/owner", params={"challenge": CHALLENGE}).text
    assert CASES[0]["key"] not in text
    assert KEY.decode() not in text


def test_a_server_without_a_key_has_no_owner():
    with client(serve()) as http:
        assert http.get("/api/owner", params={"challenge": CHALLENGE}).status_code == 404


def test_it_answers_nobody_on_another_computer():
    with client(serve(KEY), address=("192.0.2.7", 50000)) as http:
        assert http.get("/api/owner", params={"challenge": CHALLENGE}).status_code == 404


@pytest.mark.parametrize(
    "challenge",
    ["", "00", CHALLENGE + "00", CHALLENGE.upper(), "zz" + CHALLENGE[2:]],
    ids=["none", "short", "long", "upper case", "not hex"],
)
def test_it_answers_only_a_challenge_of_64_lower_case_hex_digits(challenge):
    with client(serve(KEY)) as http:
        assert http.get("/api/owner", params={"challenge": challenge}).status_code == 400


def test_the_key_file_holds_64_hex_digits(tmp_path):
    good = tmp_path / "owner.key"
    good.write_text(CASES[0]["key"] + "\n", encoding="utf-8")
    assert load_key(good) == KEY
    for bad in ("", "abc", CASES[0]["key"] + "00", "zz" + CASES[0]["key"][2:]):
        good.write_text(bad, encoding="utf-8")
        with pytest.raises(ValueError):
            load_key(good)


def test_the_command_line_takes_the_key_from_a_file(tmp_path):
    key_file = tmp_path / "owner.key"
    key_file.write_text(CASES[0]["key"], encoding="utf-8")
    assert owner_key_of(build_parser().parse_args(["--owner-key-file", str(key_file)])) == KEY
    assert owner_key_of(build_parser().parse_args([])) is None


def test_the_command_line_says_what_is_wrong_with_a_key_file(tmp_path):
    with pytest.raises(UsageError, match="--owner-key-file"):
        owner_key_of(build_parser().parse_args(["--owner-key-file", str(tmp_path / "missing.key")]))
    broken = tmp_path / "broken.key"
    broken.write_text("not a key", encoding="utf-8")
    with pytest.raises(UsageError, match="--owner-key-file"):
        owner_key_of(build_parser().parse_args(["--owner-key-file", str(broken)]))
