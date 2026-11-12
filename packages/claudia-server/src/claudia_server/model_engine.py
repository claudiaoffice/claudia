"""The AI user answers with a language model, and acts while it thinks (E7.1, E7.5).

``ModelEngine`` is the engine of one document's assistant (an ``AsyncEngine``). It describes the document to the model
through the app's lens, asks the shared ``claudia_ai.ModelRunner`` (one model for the whole server, one question at a
time, on its own thread) and runs the loop of one question: the model asks to look at the document or to change it, the
server makes those requests as the asker's AI (so roles, limits, locks and modes decide) and sends back what came of
them (what it saw; after a change the effect report, which names what was recalculated and what shows an error), and
the model carries on until it answers without requests. Every round is one job on the runner, so other documents'
questions are served in between. Budgets end a model that never answers, and the asker is told so.

The event loop never waits for the model. What the model needs from the document is read on the loop and handed over
as text.
"""

from __future__ import annotations

import json
from collections import Counter, deque
from collections.abc import Iterable
from dataclasses import dataclass, replace

from claudia_ai import Message, ModelRunner, Request, ToolCall, ToolSpec, Turn

from .assistant import Say, Step, Task
from .lens import Lens, cut
from .protocol import MethodTable, RequestError

MEMORY_TURNS = 6  # question and answer pairs remembered per person, for as long as the document stays loaded
HIDDEN_PARAMS = frozenset({"base"})  # the revision of a client's view: not something a model can know


@dataclass(frozen=True)
class Budget:
    """What one question may cost: the rounds the model gets, the requests it may make in all, and how much of what
    comes back is shown to it (per answer and per round)."""

    rounds: int = 8
    calls: int = 30
    result_chars: int = 3000
    round_chars: int = 9000


def tools_of(table: MethodTable, names: Iterable[str], *, kind: str = "change") -> tuple[ToolSpec, ...]:
    """The methods ``names`` of ``table``, described for the model as ``kind`` ("look" or "change"). ``KeyError`` for a
    name the table does not have."""
    described = table.describe()["methods"]
    tools = []
    for name in names:
        method = described[name]
        params = ", ".join(_param(p) for p in method["params"] if p["name"] not in HIDDEN_PARAMS)
        tools.append(ToolSpec(name, f"{name}({params})", " ".join(method["doc"].split()), kind))
    return tuple(tools)


def _param(param: dict) -> str:
    text = f"{param['name']}: {param['type']}"
    if param["required"]:
        return text
    return text if param["default"] is None else f"{text} = {param['default']}"


CARRY_ON = "Carry on with more requests, or give your final answer to the person (without a commands block)."
ANSWER_NOW = "You have used all the requests you may make for this question. Give your final answer to the person now."


class ModelEngine:
    """Plans by asking the language model. One per document: it remembers the last conversation with each person."""

    def __init__(
        self,
        runner: ModelRunner,
        tools: tuple[ToolSpec, ...],
        lens: Lens,
        *,
        memory_turns: int = MEMORY_TURNS,
        budget: Budget = Budget(),  # noqa: B008  (frozen)
    ):
        self._runner = runner
        self._tools = tools
        self._lens = lens
        self._memory_turns = memory_turns
        self._budget = budget
        self._memory: dict[str, deque[Message]] = {}

    async def plan_async(self, task: Task) -> list[Step]:
        """The answer to what the asker wrote, after whatever the model looked at and did on the way. Raises
        ``ModelError`` (the assistant tells the asker)."""
        if task.call is None:
            raise ValueError("the model's loop needs a task that can make requests")
        key = task.sender.casefold()
        history = tuple(self._memory.get(key, ()))
        tools = tuple(t for t in self._tools if t.kind == "look" or task.writes is None or t.name in task.writes)
        can_write = any(t.kind != "look" for t in tools)
        request = Request(task.sender, task.text, self._lens.orient(task.document, can_write=can_write), tools, history)
        say = await self._converse(task, request)
        memory = self._memory.setdefault(key, deque(maxlen=2 * self._memory_turns))
        memory.append({"role": "user", "content": task.text})
        memory.append({"role": "assistant", "content": say})
        return [Say(say)]

    async def _converse(self, task: Task, request: Request) -> str:
        budget = self._budget
        exchange: list[Message] = []
        done: Counter[str] = Counter()
        used = 0
        turn = Turn()
        for number in range(1, budget.rounds + 1):
            turn = await self._runner.answer(replace(request, exchange=tuple(exchange)))
            if not turn.calls and not turn.problems:
                return turn.say or "I have nothing to add."
            if number == budget.rounds or used >= budget.calls:
                break  # no round left to look at what these would do, or none was allowed: do not make them
            results, used = self._make(task, turn, used, done)
            closing = CARRY_ON if used < budget.calls else ANSWER_NOW
            exchange += [
                {"role": "assistant", "content": turn.raw},
                {"role": "user", "content": "Results of your requests:\n" + "\n".join(results) + "\n" + closing},
            ]
        return self._stopped(turn, done, number)

    def _make(self, task: Task, turn: Turn, used: int, done: Counter[str]) -> tuple[list[str], int]:
        """Make the requests of one round; what came of each, in order, cut to the budget."""
        budget, room, results = self._budget, self._budget.round_chars, []
        for index, call in enumerate(turn.calls, start=1):
            if used >= budget.calls:
                outcome = f"not made: you have used all {budget.calls} requests you may make."
            else:
                used += 1
                outcome = self._one(task, call, done)
            outcome = cut(outcome, min(budget.result_chars, max(room, 0)))
            room -= len(outcome)
            results.append(f"[{index}] {call.method} {_short(call.params)}: {outcome}")
        results += [f"- {problem}" for problem in turn.problems]
        return results, used

    def _one(self, task: Task, call: ToolCall, done: Counter[str]) -> str:
        assert task.call is not None
        lens = self._lens
        try:
            if call.method in lens.look_methods:
                return "\n" + lens.show(call.method, call.params, task.call(call.method, call.params))
            with lens.recorder(task.document) as recorded:
                task.call(call.method, call.params)
            done[call.method] += 1
            return "done. What changed:\n" + recorded.report()
        except RequestError as error:
            return f"failed: {error.message}"

    def _stopped(self, turn: Turn, done: Counter[str], rounds: int) -> str:
        """What the asker is told when the model did not finish within its budget."""
        made = ", ".join(f"{method} x{count}" for method, count in done.items())
        text = f"I stopped after {rounds} steps: that is my limit for one question. "
        text += f"I made these changes before stopping: {made}." if made else "I changed nothing."
        return f"{text}\n\nWhere I was: {turn.say}" if turn.say else text


def _short(params: dict) -> str:
    text = json.dumps(params, separators=(",", ":"), ensure_ascii=False)
    return text if len(text) <= 100 else text[:99] + "…"
