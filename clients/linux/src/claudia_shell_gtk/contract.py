"""The shell contract, version 1 (E5.12): the messages the web page and the desktop shell send each other.

The specification is the JSON schema ``clients/contract/shell-contract.v1.schema.json``; the tests check that this
module and the schema accept and refuse the same messages. Nothing here imports GTK, so every shell and the tests
can use it.

How the contract evolves: inside a version only *additions* are made (a new optional field, a new message type). A
receiver ignores fields it does not know and ignores messages of a type it does not know (:class:`UnknownMessageType`
is never answered). A breaking change is a new version with a new schema file; :func:`negotiate` makes a shell and a
page agree on one, or refuse each other with a message that says which versions the shell speaks.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, TypeGuard

__all__ = [
    "CONNECT_FAILED_CODES",
    "CONTRACT_VERSION",
    "MAX_MESSAGE_BYTES",
    "MAX_SERVER_LIST",
    "SUPPORTED_VERSIONS",
    "ContractError",
    "Message",
    "UnknownMessageType",
    "action",
    "connect_failed",
    "error",
    "error_for",
    "negotiate",
    "parse",
    "servers",
    "welcome",
]

CONTRACT_VERSION = 1
"""The version this module builds messages for."""
SUPPORTED_VERSIONS: tuple[int, ...] = (1,)
"""The versions this shell understands, oldest first."""
MAX_MESSAGE_BYTES = 64 * 1024
"""A message longer than this is refused unread, because the page is not trusted to be polite."""

Message = dict[str, Any]

_ACTION_ID = re.compile(r"^[a-z]+(\.[a-z][a-z0-9-]*)+$")
_TOKEN = re.compile(r"^[a-z][a-z0-9-]*$")
_LOCALE = re.compile(r"^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$")  # a BCP-47-ish tag (E5.7); loose on purpose
_ERROR_CODES = ("bad_json", "bad_message", "unsupported_contract", "unknown_action", "internal")
CONNECT_FAILED_CODES = (
    "bad_address",
    "insecure",
    "unreachable",
    "not_claudia",
    "wrong_app",
    "certificate_expired",
    "certificate_invalid",
    "not_trusted",
)
"""Why a ``connect`` can fail (E5.8): what the page may rely on to decide what to show next."""
MAX_SERVER_LIST = 64
"""The most servers a ``servers`` message may carry."""
_MAX_ACTION_ID = 64
_MAX_TOKEN = 32
_MAX_TEXT = 512
_MAX_ADDRESS = 255
_MAX_LABEL = 128


class ContractError(Exception):
    """A message that cannot be accepted. ``code`` is one of the codes of the schema's ``error`` message
    (``unknown_type`` is the one exception: it is never sent back)."""

    def __init__(self, code: str, message: str, *, supported: Sequence[int] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.supported = tuple(supported) if supported is not None else None


class UnknownMessageType(ContractError):
    """A well-formed message of a type this version does not know. Receivers ignore it (additive evolution)."""

    def __init__(self, message_type: str) -> None:
        super().__init__("unknown_type", f"unknown message type {message_type!r}")


# ---------------------------------------------------------------------------------------------------- parsing


def parse(raw: str) -> Message:
    """The message in ``raw`` (one JSON object), checked against the contract.

    Raises :class:`ContractError` (``bad_json`` or ``bad_message``) for anything the schema refuses and
    :class:`UnknownMessageType` for a type it does not define. Unknown extra fields are left in place.
    """
    if len(raw.encode("utf-8", "surrogatepass")) > MAX_MESSAGE_BYTES:
        raise ContractError("bad_message", f"message too large (more than {MAX_MESSAGE_BYTES} bytes)")
    try:
        message = json.loads(raw)
    except (ValueError, RecursionError) as problem:
        raise ContractError("bad_json", f"not JSON: {problem}") from problem
    if not isinstance(message, dict):
        raise ContractError("bad_message", "a message is a JSON object")
    kind = message.get("type")
    if not isinstance(kind, str):
        raise ContractError("bad_message", "a message has a 'type'")
    check = _CHECKS.get(kind)
    if check is None:
        raise UnknownMessageType(kind)
    check(message)
    return message


def _bad(what: str) -> ContractError:
    return ContractError("bad_message", what)


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _text(message: Mapping[str, Any], key: str, *, limit: int, required: bool = False) -> None:
    value = message.get(key)
    if value is None:
        if required:
            raise _bad(f"'{message['type']}' needs '{key}'")
        return
    if not isinstance(value, str) or len(value) > limit:
        raise _bad(f"'{key}' is text of at most {limit} characters")


def _token(value: object, what: str) -> None:
    if not (isinstance(value, str) and len(value) <= _MAX_TOKEN and _TOKEN.match(value)):
        raise _bad(f"{what} is a lower case word (letters, digits, hyphens)")


def _action_id(value: object, what: str = "an action") -> None:
    if not (isinstance(value, str) and len(value) <= _MAX_ACTION_ID and _ACTION_ID.match(value)):
        raise _bad(f"{what} is named like 'file.save' (lower case, namespaced)")


def _version(message: Mapping[str, Any]) -> None:
    value = message.get("contract")
    if not _is_int(value) or value < 1:
        raise _bad(f"'{message['type']}' needs 'contract', a whole number from 1")


def _check_hello(message: Message) -> None:
    _version(message)
    if "app" in message:  # a page that does not know yet which app its server runs (it wants a login first) omits it
        _token(message["app"], "'app'")
    _text(message, "frontend", limit=64)


def _check_welcome(message: Message) -> None:
    _version(message)
    shell = message.get("shell")
    if not isinstance(shell, dict):
        raise _bad("'welcome' needs 'shell'")
    _token(shell.get("name"), "the shell's name")
    if shell.get("platform") not in ("linux", "windows", "macos"):
        raise _bad("the shell's platform is linux, windows or macos")
    _text(shell, "version", limit=64, required=True)
    capabilities = message.get("capabilities")
    if not isinstance(capabilities, list) or len(set(map(str, capabilities))) != len(capabilities):
        raise _bad("'capabilities' is a list of different words")
    for capability in capabilities:
        _token(capability, "a capability")
    locale = message.get("locale")
    if locale is not None and not (isinstance(locale, str) and len(locale) <= 35 and _LOCALE.match(locale)):
        raise _bad("'locale' is a BCP-47-ish tag such as 'de' or 'de-DE'")


def _check_action(message: Message) -> None:
    _action_id(message.get("action"))
    _text(message, "target", limit=256)


def _check_action_state(message: Message) -> None:
    states = message.get("states")
    if not isinstance(states, dict) or not states:
        raise _bad("'action_state' needs 'states' with at least one action")
    for name, state in states.items():
        _action_id(name)
        if not isinstance(state, dict):
            raise _bad(f"the state of {name} is an object")
        for flag in ("enabled", "checked"):
            if flag in state and not isinstance(state[flag], bool):
                raise _bad(f"'{flag}' of {name} is true or false")
        _text(state, "label", limit=128)


def _check_error(message: Message) -> None:
    if message.get("code") not in _ERROR_CODES:
        raise _bad(f"'code' is one of {', '.join(_ERROR_CODES)}")
    _text(message, "message", limit=_MAX_TEXT, required=True)
    supported = message.get("supported")
    if supported is not None and not (isinstance(supported, list) and all(_is_int(v) and v >= 1 for v in supported)):
        raise _bad("'supported' is a list of contract versions")


def _check_connect(message: Message) -> None:
    _text(message, "address", limit=_MAX_ADDRESS, required=True)
    if not message["address"]:
        raise _bad("'connect' needs an address")


def _check_connect_failed(message: Message) -> None:
    if message.get("code") not in CONNECT_FAILED_CODES:
        raise _bad(f"'code' is one of {', '.join(CONNECT_FAILED_CODES)}")
    _text(message, "message", limit=_MAX_TEXT, required=True)


def _check_server_entry(entry: object) -> None:
    if not isinstance(entry, dict):
        raise _bad("a server is an object")
    origin = entry.get("origin")
    if not (isinstance(origin, str) and 0 < len(origin) <= _MAX_ADDRESS):
        raise _bad(f"a server's 'origin' is text of 1 to {_MAX_ADDRESS} characters")
    label = entry.get("label")
    if not (isinstance(label, str) and len(label) <= _MAX_LABEL):
        raise _bad(f"a server's 'label' is text of at most {_MAX_LABEL} characters")
    if not isinstance(entry.get("custom"), bool):
        raise _bad("a server's 'custom' is true or false")
    if "local" in entry and not isinstance(entry["local"], bool):
        raise _bad("a server's 'local' is true or false")


def _check_servers(message: Message) -> None:
    entries = message.get("servers")
    if not isinstance(entries, list) or len(entries) > MAX_SERVER_LIST:
        raise _bad(f"'servers' is a list of at most {MAX_SERVER_LIST} servers")
    for entry in entries:
        _check_server_entry(entry)


_CHECKS: dict[str, Callable[[Message], None]] = {
    "hello": _check_hello,
    "welcome": _check_welcome,
    "action": _check_action,
    "action_state": _check_action_state,
    "error": _check_error,
    "connect": _check_connect,
    "connect_failed": _check_connect_failed,
    "servers": _check_servers,
}

# -------------------------------------------------------------------------------------------------- negotiation


def negotiate(hello: Message, supported: Sequence[int] = SUPPORTED_VERSIONS) -> int:
    """The contract version page and shell will speak, or a :class:`ContractError` (``unsupported_contract``).

    The page names the one version it speaks; the shell either speaks it too or says which versions it does.
    """
    asked = hello["contract"]
    if asked in supported:
        return int(asked)
    speaks = ", ".join(str(v) for v in supported)
    raise ContractError(
        "unsupported_contract",
        f"this shell speaks shell contract version {speaks}; the page asked for {asked}",
        supported=supported,
    )


# --------------------------------------------------------------------------------------------------- building


def welcome(
    *, shell_version: str, capabilities: Iterable[str], contract: int = CONTRACT_VERSION, locale: str | None = None
) -> Message:
    """The shell's answer to a ``hello``: the agreed version, who the shell is, what it offers.

    ``locale`` (E5.7, D31) is the shell's own best guess at the person's locale — the OS locale by default, or
    whatever the person picked in the shell itself once that exists. The page is never required to use it: locale is
    always the client's own setting, and the page may already have a stored override of its own."""
    message: Message = {
        "type": "welcome",
        "contract": contract,
        "shell": {"name": "gtk", "platform": "linux", "version": shell_version},
        "capabilities": list(capabilities),
    }
    if locale is not None:
        message["locale"] = locale
    return message


def action(action_id: str, target: str | None = None) -> Message:
    """The message that tells the page to carry out the menu action ``action_id``."""
    message: Message = {"type": "action", "action": action_id}
    if target is not None:
        message["target"] = target
    _check_action(message)
    return message


def error(code: str, message: str, *, supported: Sequence[int] | None = None) -> Message:
    """An ``error`` message. ``code`` must be one of the schema's codes."""
    built: Message = {"type": "error", "code": code, "message": message[:_MAX_TEXT]}
    if supported is not None:
        built["supported"] = list(supported)
    _check_error(built)
    return built


def error_for(problem: ContractError) -> Message:
    """The ``error`` message that answers a :class:`ContractError` (not meant for ``unknown_type``: ignore those)."""
    return error(problem.code, str(problem), supported=problem.supported)


def connect_failed(code: str, message: str) -> Message:
    """The message that tells the page why a ``connect`` was not made (``code`` is one of
    :data:`CONNECT_FAILED_CODES`; a message that is too long is cut)."""
    built: Message = {"type": "connect_failed", "code": code, "message": message[:_MAX_TEXT]}
    _check_connect_failed(built)
    return built


def servers(entries: Iterable[Mapping[str, Any]]) -> Message:
    """The list of servers the shell remembers for its app (``servers.for_page`` makes it)."""
    built: Message = {"type": "servers", "servers": [dict(entry) for entry in entries]}
    _check_servers(built)
    return built
