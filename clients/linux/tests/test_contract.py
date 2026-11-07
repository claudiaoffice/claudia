"""The shell contract (E5.12): what page and shell may say to each other, and how versions are negotiated.

The JSON schema in ``clients/contract/`` is the specification that every shell and the page implement. The module under
test validates by hand (no dependency at run time); these tests prove that it and the schema agree.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from claudia_shell_gtk import contract
from claudia_shell_gtk.contract import ContractError, UnknownMessageType

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "contract" / "shell-contract.v1.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))


def text(**message: object) -> str:
    return json.dumps(message)


HELLO = {"type": "hello", "contract": 1, "app": "composes", "frontend": "0.1.0"}
ACTION = {"type": "action", "action": "file.save"}
STATE = {"type": "action_state", "states": {"edit.undo": {"enabled": False}, "view.page": {"checked": True}}}
WELCOME = {
    "type": "welcome",
    "contract": 1,
    "shell": {"name": "gtk", "platform": "linux", "version": "0.1.0"},
    "capabilities": [],
}

# Messages the page may send and the shell must accept ...
VALID = [
    HELLO,
    {"type": "hello", "contract": 1, "app": "computes"},
    {**HELLO, "something_new": [1, 2, 3]},  # (additive evolution: unknown fields are ignored)
    ACTION,
    {**ACTION, "target": "page"},
    STATE,
    {"type": "action_state", "states": {"edit.undo": {"label": "Undo typing"}}},
    {"type": "error", "code": "unsupported_contract", "message": "no", "supported": [1]},
    {**WELCOME, "locale": "de"},  # (E5.7) shell -> page too, but the schema does not care which side sends what
    {**WELCOME, "locale": "de-DE"},
]
# ... and messages nobody may accept.
INVALID = [
    {"type": "hello", "app": "composes"},  # no version
    {"type": "hello", "contract": "1", "app": "composes"},  # the version is a number
    {"type": "hello", "contract": 0, "app": "composes"},
    {"type": "hello", "contract": 1},  # no app
    {"type": "hello", "contract": 1, "app": "Composes!"},
    {"type": "action"},
    {"type": "action", "action": "Save"},  # ids are namespaced and lower case
    {"type": "action", "action": "file.save", "target": 3},
    {"type": "action_state", "states": {}},  # says nothing
    {"type": "action_state", "states": {"edit.undo": {"enabled": "no"}}},
    {"type": "action_state", "states": {"Undo": {"enabled": True}}},
    {"type": "action_state"},
    {"type": "error", "code": "nope", "message": "x"},
    {"type": "error", "code": "internal"},
    {**WELCOME, "locale": 7},  # (E5.7) not a string
    {**WELCOME, "locale": "not a locale!"},
]


def test_the_schema_is_a_valid_json_schema(schema: dict) -> None:
    jsonschema.Draft202012Validator.check_schema(schema)


def test_the_schema_names_its_version(schema: dict) -> None:
    assert schema["$id"].endswith("shell-contract.v1.schema.json")
    assert contract.CONTRACT_VERSION == 1
    assert contract.SUPPORTED_VERSIONS == (1,)


@pytest.mark.parametrize("message", VALID, ids=lambda m: json.dumps(m)[:60])
def test_valid_messages_are_accepted_by_schema_and_parser(schema: dict, message: dict) -> None:
    jsonschema.validate(message, schema)
    assert contract.parse(json.dumps(message))["type"] == message["type"]


@pytest.mark.parametrize("message", INVALID, ids=lambda m: json.dumps(m)[:60])
def test_invalid_messages_are_refused_by_schema_and_parser(schema: dict, message: dict) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(message, schema)
    with pytest.raises(ContractError) as refused:
        contract.parse(json.dumps(message))
    assert refused.value.code == "bad_message"


def test_what_the_shell_builds_is_valid_by_the_schema(schema: dict) -> None:
    jsonschema.validate(contract.welcome(shell_version="0.1.0", capabilities=["native-menu", "actions"]), schema)
    jsonschema.validate(contract.welcome(shell_version="0.1.0", capabilities=["native-menu"], locale="de-DE"), schema)
    jsonschema.validate(contract.action("file.save"), schema)
    jsonschema.validate(contract.error("bad_message", "what?"), schema)
    jsonschema.validate(contract.error("unsupported_contract", "too new", supported=[1]), schema)


def test_welcome_carries_a_locale_only_when_given_one() -> None:
    # (E5.7) additive and optional: a shell that says nothing about locale builds exactly what it always did
    assert "locale" not in contract.welcome(shell_version="0.1.0", capabilities=[])
    assert contract.welcome(shell_version="0.1.0", capabilities=[], locale="de")["locale"] == "de"


def test_welcome_says_who_the_shell_is() -> None:
    welcome = contract.welcome(shell_version="0.1.0", capabilities=["native-menu"])
    assert welcome["contract"] == 1
    assert welcome["shell"] == {"name": "gtk", "platform": "linux", "version": "0.1.0"}
    assert welcome["capabilities"] == ["native-menu"]


def test_text_that_is_not_json_is_refused() -> None:
    with pytest.raises(ContractError) as refused:
        contract.parse("{nope")
    assert refused.value.code == "bad_json"


@pytest.mark.parametrize("raw", ["[]", '"hello"', "3", "null"])
def test_a_message_must_be_an_object(raw: str) -> None:
    with pytest.raises(ContractError) as refused:
        contract.parse(raw)
    assert refused.value.code == "bad_message"


def test_an_unknown_type_is_told_apart_so_that_it_can_be_ignored() -> None:
    with pytest.raises(UnknownMessageType) as refused:
        contract.parse(text(type="telepathy", contract=1))
    assert refused.value.code == "unknown_type"


def test_a_message_without_a_type_is_bad() -> None:
    with pytest.raises(ContractError) as refused:
        contract.parse(text(contract=1))
    assert refused.value.code == "bad_message"


def test_an_oversized_message_is_refused_before_it_is_parsed() -> None:
    huge = json.dumps({**ACTION, "target": "x" * contract.MAX_MESSAGE_BYTES})
    with pytest.raises(ContractError) as refused:
        contract.parse(huge)
    assert refused.value.code == "bad_message"
    assert "too large" in str(refused.value)


def test_unknown_fields_are_kept_out_of_the_way_but_not_an_error() -> None:
    parsed = contract.parse(json.dumps({**HELLO, "something_new": 1}))
    assert parsed["app"] == "composes"


# ------------------------------------------------------------------------------------------------ negotiation


def test_a_hello_for_a_supported_version_is_welcomed() -> None:
    hello = contract.parse(json.dumps(HELLO))
    assert contract.negotiate(hello) == 1


def test_a_hello_for_a_newer_version_is_refused_and_the_error_lists_what_the_shell_speaks() -> None:
    hello = contract.parse(text(type="hello", contract=7, app="composes"))
    with pytest.raises(ContractError) as refused:
        contract.negotiate(hello)
    assert refused.value.code == "unsupported_contract"
    assert refused.value.supported == (1,)
    reply = contract.error_for(refused.value)
    assert reply == {
        "type": "error",
        "code": "unsupported_contract",
        "message": str(refused.value),
        "supported": [1],
    }


def test_an_older_page_than_the_shell_supports_is_refused_too() -> None:
    """A future shell that dropped version 1 must say so, not guess."""
    hello = contract.parse(text(type="hello", contract=1, app="composes"))
    with pytest.raises(ContractError) as refused:
        contract.negotiate(hello, supported=(2, 3))
    assert refused.value.code == "unsupported_contract"
    assert refused.value.supported == (2, 3)


def test_the_newest_common_version_wins() -> None:
    hello = contract.parse(text(type="hello", contract=2, app="composes"))
    assert contract.negotiate(hello, supported=(1, 2)) == 2
