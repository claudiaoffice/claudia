"""The AI as one more participant of a document (E3.6).

The assistant is a connection named ``ai`` that is attached to a hosted document. It hears the chat messages that are
addressed to it (``@ai ...``), asks an *engine* what to do, and then does it the way everybody does: it chats back to
the one who asked and changes the document through the same protocol methods (``set_cells`` ...), so roles, limits and
locks apply to it like to anybody else, and its work is in the history under its name and can be undone as its own.

The engine is a plug-in. It gets a ``Task`` (who asked, what, and the document to look at) and returns a list of
steps: ``Say`` something, or ``Call`` a method. ``claudia_server.standin.ScriptedEngine`` is a stand-in that
understands a few phrases; ``claudia_server.model_engine.ModelEngine`` asks a language model (OpenVINO, E7.1).
An engine that has to wait for something slow (a model) is an ``AsyncEngine``: it is awaited, so the event loop keeps
serving everybody else meanwhile. It must read the document before it first awaits and keep its own copy: other
people go on editing while it waits.

Questions are answered one at a time, in the order they were asked; with ``max_waiting`` a document refuses the ones
that would wait too long behind others. While it works the assistant shows that it is typing and where it is working
(its cursor), so people can watch.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

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


@runtime_checkable
class AsyncEngine(Protocol):
    """An engine that waits for something slow, such as a language model, and so is awaited."""

    async def plan_async(self, task: Task) -> list[Step]:
        """The steps that answer ``task``. May raise: the assistant then says it could not answer."""


class Assistant:
    """The AI participant of one document.

    ``max_waiting`` is how many questions may wait behind the one being answered; further ones are refused at once
    with a message (``None``: no limit). ``allowed_methods`` are the write methods its account may call (SEC-10):
    whoever makes the assistant for an app passes its entry of ``apps.MODEL_METHODS``, so the engine's plan is
    checked at dispatch, not only by its own filtering of what the model wrote. The default, no methods, is a safe
    one to fall back to, not a convenience: an assistant made without thinking about this writes nothing."""

    def __init__(
        self,
        engine: Engine | AsyncEngine,
        *,
        pause: float = 0.5,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        max_waiting: int | None = None,
        allowed_methods: Iterable[str] = (),
    ):
        self.engine = engine
        self.pause = pause  # seconds between steps, so that people can follow what happens
        self.max_waiting = max_waiting
        self.allowed_methods = frozenset(allowed_methods)
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
        self.connection = hosted.connect(Account.assistant(self.allowed_methods), lambda _frame: None)
        hosted.assistant = self
        hosted.document.subscribe(self._on_event)
        return self.connection

    def _on_event(self, event: object) -> None:
        if not isinstance(event, ChatPosted):
            return
        record = event.record
        if not (record.to and is_reserved(record.to) and not is_reserved(record.author)):
            return
        if self.max_waiting is not None and len(self._queue) >= self.max_waiting:
            busy = f"I am busy with {len(self._queue)} other questions here. Ask me again in a moment."
            self._say(record.author, busy)
            return
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
                steps = await self._plan(Task(record.author, record.text, document))
            except Exception as exc:  # the engine is a plug-in: whatever it does wrong, the asker is told
                log.exception("the engine failed")
                steps = [Say(f"I could not answer: {exc}")]
            for step in steps:
                await self._sleep(self.pause)
                if not self._run(step, record.author):
                    break
        finally:
            document.publish("typing", AI_USER, {"on": False})

    async def _plan(self, task: Task) -> list[Step]:
        if isinstance(self.engine, AsyncEngine):
            return await self.engine.plan_async(task)
        return self.engine.plan(task)

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
