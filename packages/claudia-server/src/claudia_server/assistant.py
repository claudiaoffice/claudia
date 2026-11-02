"""The AI as one more participant of a document (E3.6).

The assistant is a connection named ``ai`` that is attached to a hosted document. It hears the chat messages that are
addressed to it (``@ai ...``), asks an *engine* what to do, and then does it the way everybody does: it chats back to
the one who asked and changes the document through the same protocol methods (``set_cells`` ...), so roles, limits and
locks apply to it like to anybody else, and its work is in the history under its name and can be undone as its own.

The engine is a plug-in. It gets a ``Task`` (who asked, what, and the document to look at) and returns a list of
steps: ``Say`` something, or ``Call`` a method. ``claudia_server.standin.ScriptedEngine`` is a stand-in that
understands a few phrases; a real model (OpenVINO, E3.6) takes its place without anything else changing.

Questions are answered one at a time, in the order they were asked. While it works the assistant shows that it is typing
and where it is working (its cursor), so people can watch.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from claudia_core import ChatPosted, ChatRecord, Document

from .auth import AI_USER, Account, is_reserved
from .hub import HubError
from .protocol import Context, RequestError

if TYPE_CHECKING:
    from .hub import Connection, HostedDocument

log = logging.getLogger("claudia_server")


@dataclass(frozen=True)
class Task:
    """One question for the engine: who asked, what they wrote (without the ``@ai``) and the document to look at.

    The document is for reading; every change goes through a ``Call`` step."""

    sender: str
    text: str
    document: Document


@dataclass(frozen=True)
class Say:
    """Answer the asker in the chat."""

    text: str


@dataclass(frozen=True)
class Call:
    """Call a protocol method as the assistant. ``focus`` (regions in wire form) is shown as its place first."""

    method: str
    params: dict[str, Any] = field(default_factory=dict)
    focus: tuple[dict, ...] = ()


Step = Say | Call


class Engine(Protocol):
    """What decides what the assistant does."""

    def plan(self, task: Task) -> list[Step]:
        """The steps that answer ``task``. May raise: the assistant then says it could not answer."""


class Assistant:
    """The AI participant of one document."""

    def __init__(
        self,
        engine: Engine,
        *,
        pause: float = 0.5,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.engine = engine
        self.pause = pause  # seconds between steps, so that people can follow what happens
        self._sleep = sleep
        self.hosted: HostedDocument | None = None
        self.connection: Connection | None = None
        self._queue: deque[ChatRecord] = deque()
        self._worker: asyncio.Task | None = None

    # -- joining ---------------------------------------------------------------------------
    def attach(self, hosted: HostedDocument) -> Connection:
        """Join the document. There is one assistant per document."""
        if hosted.assistant is not None:
            raise HubError("bad_request", f"{hosted.id} already has an assistant")
        self.hosted = hosted
        self.connection = hosted.connect(Account.assistant(), lambda _frame: None)
        hosted.assistant = self
        hosted.document.subscribe(self._on_event)
        return self.connection

    def _on_event(self, event: object) -> None:
        if not isinstance(event, ChatPosted):
            return
        record = event.record
        if record.to and is_reserved(record.to) and not is_reserved(record.author):
            self._queue.append(record)
            self._start()

    def _start(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # no event loop yet (a test without one): the question waits in the queue
        if self._worker is None and self._queue:
            self._worker = loop.create_task(self._work())

    async def idle(self) -> None:
        """Return when every question asked so far has been answered."""
        self._start()
        while self._worker is not None:
            await self._worker

    # -- answering ---------------------------------------------------------------------------
    async def _work(self) -> None:
        try:
            while self._queue:
                record = self._queue.popleft()
                try:
                    await self._answer(record)
                except Exception:
                    log.exception("the assistant failed on a question")
        finally:
            self._worker = None

    async def _answer(self, record: ChatRecord) -> None:
        assert self.hosted is not None
        document = self.hosted.document
        document.publish("typing", AI_USER, {"on": True})
        try:
            try:
                steps = self.engine.plan(Task(record.author, record.text, document))
            except Exception as exc:  # the engine is a plug-in: whatever it does wrong, the asker is told
                log.exception("the engine failed")
                steps = [Say(f"I could not answer: {exc}")]
            for step in steps:
                await self._sleep(self.pause)
                if not self._run(step, record.author):
                    break
        finally:
            document.publish("typing", AI_USER, {"on": False})

    def _run(self, step: Step, asker: str) -> bool:
        """Do one step; ``False`` if the rest of the plan should be dropped."""
        if isinstance(step, Say):
            self._say(asker, step.text)
            return True
        try:
            if step.focus:
                self._call("presence", {"regions": list(step.focus)})
            self._call(step.method, step.params)
        except RequestError as error:
            self._say(asker, f"I could not do that: {error.message}")
            return False
        return True

    def _call(self, method: str, params: dict) -> Any:
        assert self.hosted is not None and self.connection is not None
        hosted = self.hosted
        context = Context(hosted.document, self.connection.account, hosted.limits, hosted.users, hosted.edit_timeout)
        return hosted.methods.dispatch(context, method, params)

    def _say(self, asker: str, text: str) -> None:
        assert self.hosted is not None
        try:
            self.hosted.document.post_chat(AI_USER, f"@{asker} {text}", users=self.hosted.users())
        except ValueError:
            log.info("the assistant's answer to %s was not sent: %s", asker, text)  # they left in the meantime
