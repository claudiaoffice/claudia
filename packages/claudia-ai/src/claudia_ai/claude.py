"""Claude as a language model: Anthropic's Messages API, with the administrator's provider key (E7.11, D266).

``ClaudeModel`` is a ``LanguageModel`` like the local one, so everything above it (the prompt, the loop of requests, the
queue) is the same for both. What differs is that content leaves this computer, which ``remote`` says, and that it can
fail in ways a local model cannot: ``ProviderError`` carries the *reason* (``FailureReason``), so the person is told in
one sentence and the administrator can read why.

The answer is read as a stream, so that ``stop`` (a time limit, shutting down, a switch-off) is honoured while it is
still running; nothing is streamed to the person. HTTP goes through ``Transport``, a one-method seam on the standard
library (no new dependency), so tests talk to ``claudia_ai.testing.FakeAnthropic`` and never to Anthropic.

The provider key is sent in a request header and nowhere else: it is not in any message, ``repr`` or error.
"""

from __future__ import annotations

import contextlib
import json
import socket
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .model import Message, ModelError

DEFAULT_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"
DEFAULT_READ_TIMEOUT = 30.0  # seconds without a byte from Anthropic before the answer is given up on


class FailureReason(Enum):
    """Why Anthropic did not answer. The value is what the settings page and the log call it."""

    KEY_REFUSED = "key_refused"
    CREDIT_USED_UP = "credit_used_up"
    RATE_LIMITED = "rate_limited"
    OVERLOADED = "overloaded"
    UNREACHABLE = "unreachable"
    UNKNOWN_MODEL = "unknown_model"
    TIMED_OUT = "timed_out"
    OTHER = "other"

    def admin_sentence(self, *, model: str = "", seconds: float = 0, detail: str = "") -> str:
        """What the administrator reads on the AI page (mock 2 D). English; the page translates by ``value``."""
        match self:
            case FailureReason.KEY_REFUSED:
                return "Anthropic refused the key."
            case FailureReason.CREDIT_USED_UP:
                return "The credit balance at Anthropic is used up."
            case FailureReason.RATE_LIMITED:
                return "Anthropic's rate limit was reached."
            case FailureReason.OVERLOADED:
                return "Anthropic is overloaded at the moment."
            case FailureReason.UNREACHABLE:
                return "Anthropic cannot be reached from this server."
            case FailureReason.UNKNOWN_MODEL:
                return f"Anthropic does not know the model “{model}”."
            case FailureReason.TIMED_OUT:
                return f"Anthropic did not answer within {seconds:g} seconds."
            case _:
                return f"Anthropic answered with an error: {detail}" if detail else "Anthropic answered with an error."


class ProviderError(ModelError):
    """A remote provider did not answer. ``str(error)`` is the one sentence for the person who asked; ``reason`` and
    ``detail`` are for the administrator (``detail`` is what Anthropic said, never the key)."""

    def __init__(self, reason: FailureReason, detail: str = "", *, provider: str = "Claude"):
        super().__init__(f"{provider} is not available at the moment. The administrator can see why.")
        self.reason = reason
        self.detail = detail
        self.provider = provider


class Response(Protocol):
    """What ``Transport.post`` gives back: the status and the body, line by line."""

    status: int

    def lines(self) -> Iterator[bytes]:
        """The body's lines, as they arrive."""
        ...

    def close(self) -> None:
        """Give the connection up. May be called from another thread while ``lines`` waits: that wait ends."""
        ...


class Transport(Protocol):
    """The one call to the network. ``OSError`` (``TimeoutError`` for a silent server) when there is none."""

    def post(self, url: str, headers: dict[str, str], body: bytes, *, timeout: float) -> Response:
        """POST ``body``; ``timeout`` is how long one read may wait."""
        ...


@dataclass
class _UrllibResponse:
    status: int
    _raw: object

    def lines(self) -> Iterator[bytes]:
        yield from self._raw  # type: ignore[misc]  # an http.client.HTTPResponse is an iterator of lines

    def close(self) -> None:
        # A read that waits in another thread is not woken by closing the file, only by shutting the connection down
        # (PROC-67). The socket is borrowed by its number and handed back (detach) without being closed: the response
        # closes it. Not a duplicate: on Windows a socket's number is a handle, which os.dup cannot copy.
        with contextlib.suppress(OSError, ValueError, AttributeError):  # (already closed, or an error answer)
            same = socket.socket(fileno=self._raw.fileno())  # type: ignore[attr-defined]
            try:
                same.shutdown(socket.SHUT_RDWR)
            finally:
                same.detach()
        self._raw.close()  # type: ignore[attr-defined]


class UrllibTransport:
    """``Transport`` on the standard library."""

    def post(self, url: str, headers: dict[str, str], body: bytes, *, timeout: float) -> Response:
        """See ``Transport.post``."""
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")  # noqa: S310  (https or a test's http)
        try:
            raw = urllib.request.urlopen(request, timeout=timeout)  # noqa: S310
        except urllib.error.HTTPError as error:  # an answer with a status: the body says why
            return _UrllibResponse(error.code, error)
        return _UrllibResponse(raw.status, raw)


def reason_of(status: int, kind: str, message: str) -> FailureReason:
    """What a status and the error type and message of Anthropic's answer mean."""
    lowered = message.lower()
    if status in (401, 403) or kind in ("authentication_error", "permission_error"):
        return FailureReason.KEY_REFUSED
    if status == 402 or "credit balance" in lowered:
        return FailureReason.CREDIT_USED_UP
    if status == 429 or kind == "rate_limit_error":
        return FailureReason.RATE_LIMITED
    if status in (500, 503, 529) or kind in ("overloaded_error", "api_error"):
        return FailureReason.OVERLOADED
    if status == 404 or kind == "not_found_error":
        return FailureReason.UNKNOWN_MODEL
    return FailureReason.OTHER


def _alternating(messages: list[Message]) -> tuple[str, list[Message]]:
    """The system text; the other messages, those of one role in a row joined (the API wants them to alternate)."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    joined: list[Message] = []
    for message in messages:
        if message["role"] == "system":
            continue
        if joined and joined[-1]["role"] == message["role"]:
            joined[-1] = {"role": message["role"], "content": joined[-1]["content"] + "\n\n" + message["content"]}
        else:
            joined.append(dict(message))
    return system, joined


class ClaudeModel:
    """A chat model that is Anthropic's Claude, reached with ``key``. ``remote`` is ``True``: content leaves this
    computer. ``base_url`` is for tests and for an operator who must go through a proxy (never a field of a page)."""

    remote = True

    def __init__(
        self,
        key: str,
        model: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        transport: Transport | None = None,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
    ):
        self.model = model
        self.name = f"Claude · {model}"
        self._key = key
        self._url = base_url.rstrip("/") + "/v1/messages"
        self._transport = transport or UrllibTransport()
        self._read_timeout = read_timeout

    def __repr__(self) -> str:
        return f"ClaudeModel({self.model!r})"

    def generate(self, messages: list[Message], *, max_new_tokens: int, stop: Callable[[], bool]) -> str:
        """The next message of Claude, or what there is of it when ``stop()`` turns true. Raises ``ProviderError``."""
        system, conversation = _alternating(messages)
        body = {"model": self.model, "max_tokens": max_new_tokens, "messages": conversation, "stream": True}
        if system:
            body["system"] = system
        headers = {"x-api-key": self._key, "anthropic-version": API_VERSION, "content-type": "application/json"}
        try:
            response = self._transport.post(self._url, headers, json.dumps(body).encode(), timeout=self._read_timeout)
        except TimeoutError as exc:
            raise ProviderError(FailureReason.TIMED_OUT) from exc
        except OSError as exc:  # no route, refused, no DNS: whatever it is, it cannot be reached
            raise ProviderError(FailureReason.UNREACHABLE, type(exc).__name__) from exc
        if response.status != 200:
            try:
                raise self._refusal(response)
            finally:
                response.close()
        try:
            return self._answer(response, stop)
        except TimeoutError as exc:
            raise ProviderError(FailureReason.TIMED_OUT) from exc
        except OSError as exc:  # the connection broke in the middle
            raise ProviderError(FailureReason.UNREACHABLE, type(exc).__name__) from exc

    def _answer(self, response: Response, stop: Callable[[], bool]) -> str:
        """The answer's text, read in a thread of its own while this one watches ``stop()``: once it turns true the
        question ends with what there is, at once, even if Anthropic has gone silent and the read would wait for the
        read timeout (PROC-67). The connection is given up in the background: closing it waits for the read, which
        ends at once where the system can wake it, and elsewhere at its timeout. ``response`` is closed either way."""
        pieces: list[str] = []
        failed: list[BaseException] = []
        done = threading.Event()

        def read() -> None:
            try:
                self._read(response, stop, pieces)
            except BaseException as error:  # noqa: BLE001 - handed over to the thread that waits for it
                failed.append(error)
            finally:
                done.set()

        threading.Thread(target=read, name="claudia-claude-read", daemon=True).start()
        while not done.wait(0.05):  # the pace of the watch
            if stop():
                threading.Thread(target=response.close, name="claudia-claude-close", daemon=True).start()
                return "".join(pieces)
        response.close()
        if failed and not stop():
            raise failed[0]
        return "".join(pieces)

    def _refusal(self, response: Response) -> ProviderError:
        text = b"".join(response.lines()).decode("utf-8", "replace")
        try:
            error = json.loads(text).get("error", {})
        except ValueError:
            error = {}
        message = str(error.get("message", ""))
        return ProviderError(
            reason_of(response.status, str(error.get("type", "")), message), message or f"HTTP {response.status}"
        )

    def _read(self, response: Response, stop: Callable[[], bool], pieces: list[str]) -> None:
        """Add the answer's text to ``pieces`` as it streams in, until it ends or ``stop()`` turns true."""
        for line in response.lines():
            if stop():
                break
            if not line.startswith(b"data:"):
                continue
            event = json.loads(line[5:])
            match event.get("type"):
                case "content_block_delta" if event["delta"].get("type") == "text_delta":
                    pieces.append(event["delta"]["text"])
                case "error":
                    error = event.get("error", {})
                    message = str(error.get("message", ""))
                    raise ProviderError(reason_of(0, str(error.get("type", "")), message), message)
                case "message_stop":
                    break
