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

from .ai_mode import ACT, DEFAULT_MODE, SUGGEST, AiMode, parse_mode
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
    mode: AiMode = DEFAULT_MODE  # how the asker wants it treated (D262)
    writes: frozenset[str] | None = None  # the methods the AI may write through for this asker; ``None``: no limit
    # Makes a request of the document as the AI under this question's account (reads and writes alike) and returns
    # its result; ``RequestError`` if it is refused or fails. An engine that acts while it thinks (the model's loop)
    # uses it.
    call: Callable[[str, dict], Any] | None = None


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

SUGGEST_REFUSAL = (
    "You asked me in suggest mode, and I cannot prepare a proposal in this app yet, so I changed nothing. "
    "Switch to act mode to let me make the change."
)


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
        suggest_methods: Iterable[str] = (),
    ):
        self.engine = engine
        self.pause = pause  # seconds between steps, so that people can follow what happens
        self.max_waiting = max_waiting
        self.allowed_methods = frozenset(allowed_methods)
        self.suggest_methods = frozenset(suggest_methods) & self.allowed_methods  # what it may write for *suggest*
        self._sleep = sleep
        self.hosted: HostedDocument | None = None
        self.connection: Connection | None = None
        self._queue: deque[tuple[ChatRecord, AiMode]] = deque()
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
        assert self.hosted is not None
        mode = parse_mode(self.hosted.ai_mode_of(record.author))  # noted by ``chat``, for this very message
        self._queue.append((record, mode))
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
                record, mode = self._queue.popleft()
                try:
                    await self._answer(record, mode)
                except Exception:
                    log.exception("the assistant failed on a question")
        finally:
            self._worker = None

    def account_for(self, asker: str, mode: AiMode) -> Account:
        """The account one question is answered under (D261, D262): the AI's own, narrowed to what the asker may do
        (her role; nothing at all if she has left) and to what her mode allows (*suggest*: only what it may write as a
        proposal)."""
        assert self.connection is not None and self.hosted is not None
        role = self.hosted.role_of(asker) or "viewer"
        writes = self.allowed_methods if mode == ACT else self.suggest_methods
        return self.connection.account.acting_for(role, writes)

    async def _answer(self, record: ChatRecord, mode: AiMode = DEFAULT_MODE) -> None:
        assert self.hosted is not None
        document = self.hosted.document
        account = self.account_for(record.author, mode)
        document.publish("typing", AI_USER, {"on": True})
        try:
            try:
                task = Task(
                    record.author,
                    record.text,
                    document,
                    mode,
                    account.allowed_methods,
                    call=lambda method, params: self._call(method, params, account),
                )
                steps = await self._plan(task)
            except Exception as exc:  # the engine is a plug-in: whatever it does wrong, the asker is told
                log.exception("the engine failed")
                steps = [Say(f"I could not answer: {exc}")]
            for step in steps:
                await self._sleep(self.pause)
                if not self._run(step, record.author, account, mode):
                    break
        finally:
            document.publish("typing", AI_USER, {"on": False})

    async def _plan(self, task: Task) -> list[Step]:
        if isinstance(self.engine, AsyncEngine):
            return await self.engine.plan_async(task)
        return self.engine.plan(task)

    def _run(self, step: Step, asker: str, account: Account | None = None, mode: AiMode = DEFAULT_MODE) -> bool:
        """Do one step as ``account`` (the AI's own when none is given); ``False`` if the rest of the plan should be
        dropped."""
        if isinstance(step, Say):
            self._say(asker, step.text)
            return True
        if mode == SUGGEST and step.method in self.allowed_methods - self.suggest_methods:
            # D262: not an error, a choice she made; say so and where to change it, before anything is shown or tried
            self._say(asker, SUGGEST_REFUSAL)
            return False
        try:
            if step.focus:
                self._call("presence", {"regions": list(step.focus)}, account)
            self._call(step.method, step.params, account)
        except RequestError as error:
            self._say(asker, f"I could not do that: {error.message}")
            return False
        return True

    def _call(self, method: str, params: dict, account: Account | None = None) -> Any:
        assert self.hosted is not None and self.connection is not None
        hosted = self.hosted
        who = account or self.connection.account
        context = Context(
            hosted.document, who, hosted.limits, hosted.users, hosted.edit_timeout, renderings=hosted.renderings
        )
        hosted.acting_user = who.user
        try:
            return hosted.methods.dispatch(context, method, params)
        finally:
            hosted.acting_user = None

    def _say(self, asker: str, text: str) -> None:
        assert self.hosted is not None
        try:
            self.hosted.document.post_chat(AI_USER, f"@{asker} {text}", users=self.hosted.users())
        except ValueError:
            log.info("the assistant's answer to %s was not sent: %s", asker, text)  # they left in the meantime
