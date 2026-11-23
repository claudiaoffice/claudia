"""A language model that needs no model, for tests: answers from a function, and can be slow."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .model import Message


class FakeModel:
    """Answers with ``answer(messages)`` (an ``Exception`` it returns is raised) after ``delay`` seconds.

    It gives up early when asked to stop, and records what it was asked."""

    name = "fake model"
    remote = False

    def __init__(self, answer: Callable[[list[Message]], str | Exception] | None = None, delay: float = 0.0):
        self.answer = answer or (lambda messages: "ok")
        self.delay = delay
        self.calls: list[list[Message]] = []
        self.max_new_tokens: list[int] = []
        self.threads: set[threading.Thread] = set()
        self.most_at_once = 0
        self.stopped_early = False
        self._running = 0
        self._lock = threading.Lock()

    def generate(self, messages: list[Message], *, max_new_tokens: int, stop: Callable[[], bool]) -> str:
        """Like ``LanguageModel.generate``."""
        with self._lock:
            self.calls.append(messages)
            self.max_new_tokens.append(max_new_tokens)
            self.threads.add(threading.current_thread())
            self._running += 1
            self.most_at_once = max(self.most_at_once, self._running)
        try:
            end = time.monotonic() + self.delay
            while time.monotonic() < end:
                if stop():
                    self.stopped_early = True
                    return "partial"
                time.sleep(0.01)
            result = self.answer(messages)
            if isinstance(result, Exception):
                raise result
            return result
        finally:
            with self._lock:
                self._running -= 1


@dataclass(frozen=True)
class SentRequest:
    """One request the fake Anthropic received, as Anthropic would have seen it."""

    key: str
    model: str
    system: str
    messages: list[Message]
    max_tokens: int


_FAILURES = {
    "key_refused": (401, "authentication_error", "invalid x-api-key"),
    "credit_used_up": (400, "invalid_request_error", "Your credit balance is too low to access the Anthropic API."),
    "rate_limited": (429, "rate_limit_error", "Number of request tokens has exceeded your rate limit."),
    "overloaded": (529, "overloaded_error", "Overloaded"),
    "unknown_model": (404, "not_found_error", "model: not found"),
}


class FakeAnthropic:
    """A small server on this computer that speaks Anthropic's Messages API (the stream included), for tests and for
    the end-to-end scenarios: no scenario reaches the real Anthropic.

    It accepts the ``key`` (more can be added to ``keys``), answers with ``answer(messages)`` and records every request
    in ``requests``. ``fail`` makes it refuse as Anthropic does, ``go_quiet`` makes it stop answering, ``delay`` and
    ``pause_between_chunks`` make it slow. Use it as a context manager; ``url`` is where it listens."""

    def __init__(self, key: str = "sk-ant-test-key", answer: Callable[[list[Message]], str] | None = None):
        self.keys = {key}
        self.answer = answer or (lambda messages: "ok")
        self.requests: list[SentRequest] = []
        self.delay = 0.0
        self.pause_between_chunks = 0.0
        self._failure: tuple[str, str | None] | None = None
        self._quiet = False
        self._closing = threading.Event()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                fake._handle(self)

            def log_message(self, *args: object) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> FakeAnthropic:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._closing.set()
        self._server.shutdown()
        self._server.server_close()

    def fail(self, kind: str, *, after_text: str | None = None) -> None:
        """Refuse from now on as Anthropic does for ``kind`` (a key of the failures); with ``after_text`` the answer
        starts and then fails in the middle."""
        if kind not in _FAILURES:
            raise ValueError(f"unknown failure {kind!r}")
        self._failure = (kind, after_text)

    def recover(self) -> None:
        """Answer again."""
        self._failure = None
        self._quiet = False

    def go_quiet(self) -> None:
        """Accept requests and never answer them."""
        self._quiet = True

    def _handle(self, request: BaseHTTPRequestHandler) -> None:
        body = json.loads(request.rfile.read(int(request.headers["Content-Length"])))
        key = request.headers.get("x-api-key", "")
        self.requests.append(
            SentRequest(key, body["model"], body.get("system", ""), body["messages"], body["max_tokens"])
        )
        if key not in self.keys:
            self._refuse(request, "key_refused")
        elif self._quiet:
            request.send_response(200)
            request.end_headers()
            request.wfile.flush()
            self._closing.wait()
        elif self._failure is not None and self._failure[1] is None:
            self._refuse(request, self._failure[0])
        else:
            self._stream(request, body["messages"])

    @staticmethod
    def _refuse(request: BaseHTTPRequestHandler, kind: str) -> None:
        status, error_type, message = _FAILURES[kind]
        payload = json.dumps({"type": "error", "error": {"type": error_type, "message": message}}).encode()
        request.send_response(status)
        request.send_header("content-type", "application/json")
        request.send_header("content-length", str(len(payload)))
        request.end_headers()
        request.wfile.write(payload)

    def _stream(self, request: BaseHTTPRequestHandler, messages: list[Message]) -> None:
        time.sleep(self.delay)
        failing = self._failure
        text = (failing[1] or "") if failing else self.answer(messages)
        request.send_response(200)
        request.send_header("content-type", "text/event-stream")
        request.end_headers()
        pieces = text.split(" ")
        try:
            for index, piece in enumerate(pieces):
                chunk = piece if index == len(pieces) - 1 else piece + " "
                self._event(
                    request, {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": chunk}}
                )
                time.sleep(self.pause_between_chunks)
            if failing:
                _, error_type, message = _FAILURES[failing[0]]
                self._event(request, {"type": "error", "error": {"type": error_type, "message": message}})
            else:
                self._event(request, {"type": "message_stop"})
        except (BrokenPipeError, ConnectionResetError):  # the reader gave up: that is what stop does
            pass

    @staticmethod
    def _event(request: BaseHTTPRequestHandler, event: dict) -> None:
        request.wfile.write(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode())
        request.wfile.flush()
