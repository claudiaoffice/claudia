"""One document's AI: who answers each question, and what the chat says about it (E7.11).

``AiRouter`` is the engine of a document's assistant (an ``AsyncEngine``). For every question it asks the server's
``ProviderDesk`` who answers *this* document now, hands the question to that provider's engine and puts who answered
on what it says. It never falls back: when Claude is the provider and fails, the person is told so in one sentence and
nobody else answers instead (decided 2026-11-22).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace

from claudia_ai import (
    Answerer,
    FailureReason,
    ModelError,
    ModelRunner,
    ModelTimeout,
    ProviderError,
    Request,
    ToolSpec,
    Turn,
)
from claudia_core import Via

from .ai_consent import CLAUDE, AiConsent
from .ai_desk import CLAUDE_VIA, Failure, ProviderDesk
from .assistant import AiTurn, Engine, Say, Task
from .lens import Lens
from .model_engine import Budget, ConversationMemory, ModelEngine

log = logging.getLogger("claudia_server")

UNAVAILABLE = "{name} is not available at the moment. The administrator can see why."
STOPPED = "Stopped: {name} was switched off."
NOTE_NO_ANSWER = "no answer was made"
NOTE_STOPPED = "stopped at its next step"


class Withdrawn(ModelError):
    """Claude may not be asked any more: the owners withdrew their consent or the administrator switched it off."""


class GatedRunner:
    """A runner that asks whether it still may before every round, so that a switch-off ends a question at its next
    step and nothing more is sent (a question is a loop of rounds; each round is the only place it calls out)."""

    def __init__(self, runner: ModelRunner, may: Callable[[], bool]):
        self._runner = runner
        self.may = may

    async def answer(self, request: Request) -> Turn:
        """The runner's answer; ``Withdrawn`` instead of asking when it may not any more."""
        if not self.may():
            raise Withdrawn
        return await self._runner.answer(request)


@dataclass(frozen=True)
class ModelParts:
    """What a language model needs to work in one app: the lens through which it sees a document, the requests it may
    make, and what one question may cost."""

    lens: Lens
    tools: tuple[ToolSpec, ...]
    budget: Budget = Budget()  # noqa: B008  (frozen)


class AiRouter:
    """The engine of one document's assistant: decides per question, remembers the conversation across providers."""

    def __init__(self, desk: ProviderDesk, stand_in: Engine | None, parts: ModelParts | None):
        self._desk = desk
        self._stand_in = stand_in
        self._parts = parts
        self._memory = ConversationMemory()

    def answering(self, consent: AiConsent) -> Via:
        """Who answers a question in a document whose owners decided ``consent``, and why not Claude where it is
        not (the note), for the badge."""
        decision, note = self._desk.decide(consent)
        return replace(decision.via, note=note)

    def offers_claude(self) -> bool:
        """Can the owners of a document allow Claude here at all?"""
        return self._desk.offers_claude

    async def plan_async(self, task: Task) -> list[AiTurn]:
        """The steps that answer ``task``, each ``Say`` marked with who answered."""
        decision, note = self._desk.decide(task.consent() if task.consent else AiConsent())
        via = replace(decision.via, note=note)
        if decision.runner is None or self._parts is None:
            return _marked(self._plan_stand_in(task), via)
        if via.provider != CLAUDE:
            return _marked(await self._engine(decision.runner).plan_async(task), via)
        return await self._ask_claude(task, decision.runner, via)

    def _plan_stand_in(self, task: Task) -> list[AiTurn]:
        if self._stand_in is None:
            raise ModelError("there is no assistant for this kind of document without a language model")
        return self._stand_in.plan(task)

    def _engine(self, runner: Answerer) -> ModelEngine:
        assert self._parts is not None
        parts = self._parts
        return ModelEngine(runner, parts.tools, parts.lens, memory=self._memory, budget=parts.budget)

    async def _ask_claude(self, task: Task, runner: ModelRunner, via: Via) -> list[AiTurn]:
        def may() -> bool:
            return task.consent is not None and self._desk.may_ask_claude(runner, task.consent())

        try:
            steps = await self._engine(GatedRunner(runner, may)).plan_async(task)
        except Withdrawn:
            return [Say(STOPPED.format(name=CLAUDE_VIA.label), replace(via, note=NOTE_STOPPED))]
        except ModelError as error:
            if not may():  # the question ran into the switch-off, not into a fault of Claude's
                return [Say(STOPPED.format(name=CLAUDE_VIA.label), replace(via, note=NOTE_STOPPED))]
            self._failed(error)
            return [Say(UNAVAILABLE.format(name=CLAUDE_VIA.label), replace(via, note=NOTE_NO_ANSWER))]
        self._desk.health.answered(CLAUDE)
        return _marked(steps, via)

    def _failed(self, error: ModelError) -> None:
        """Note what went wrong, for the administrator's page; the person only reads the one sentence."""
        if isinstance(error, ProviderError):
            reason, detail = error.reason, error.detail
        elif isinstance(error, ModelTimeout):
            reason, detail = FailureReason.TIMED_OUT, str(error)
        else:
            reason, detail = FailureReason.OTHER, str(error)
        log.warning("Claude did not answer: %s (%s)", reason.value, detail)
        self._desk.health.failed(Failure(CLAUDE, reason, detail, self._desk.now()))


def _marked(steps: list[AiTurn], via: Via) -> list[AiTurn]:
    """``steps`` with ``via`` on every ``Say``: the person reads who answered under what was said."""
    return [replace(step, via=via) if isinstance(step, Say) else step for step in steps]
