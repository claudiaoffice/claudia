"""The AI user answers with a language model (E7.1).

``ModelEngine`` is the engine of one document's assistant (an ``AsyncEngine``). It describes the document to the model,
asks the shared ``claudia_ai.ModelRunner`` (one model for the whole server, one question at a time, on its own thread)
and turns the model's answer into steps: something to say, requests to make. The requests are the model's wish: the
assistant makes them like anybody, so roles, limits and locks decide, and the asker hears about each one that fails.

The event loop never waits for the model. What the model needs from the document is read first, on the loop, and
handed over as text.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable

from claudia_ai import Message, ModelRunner, Request, ToolSpec, Turn
from claudia_core import Document

from .assistant import Call, Say, Step, Task
from .protocol import MethodTable

MEMORY_TURNS = 6  # question and answer pairs remembered per person, for as long as the document stays loaded
HIDDEN_PARAMS = frozenset({"base"})  # the revision of a client's view: not something a model can know


def tools_of(table: MethodTable, names: Iterable[str]) -> tuple[ToolSpec, ...]:
    """The methods ``names`` of ``table``, described for the model. ``KeyError`` for a name the table does not have."""
    described = table.describe()["methods"]
    tools = []
    for name in names:
        method = described[name]
        params = ", ".join(_param(p) for p in method["params"] if p["name"] not in HIDDEN_PARAMS)
        tools.append(ToolSpec(name, f"{name}({params})", " ".join(method["doc"].split())))
    return tuple(tools)


def _param(param: dict) -> str:
    text = f"{param['name']}: {param['type']}"
    if param["required"]:
        return text
    return text if param["default"] is None else f"{text} = {param['default']}"


def steps_of(turn: Turn) -> list[Step]:
    """What the assistant does with the model's answer: say it, then make the requests (or make them, then say it)."""
    calls: list[Step] = [Call(call.method, call.params) for call in turn.calls]
    notes = "\n".join(turn.problems)
    if turn.say:
        return [Say(f"{turn.say}\n{notes}" if notes else turn.say), *calls]
    if calls:
        return [Say(notes), *calls] if notes else [*calls, Say("Done.")]
    return [Say(notes or "I have nothing to add.")]


class ModelEngine:
    """Plans by asking the language model. One per document: it remembers the last conversation with each person."""

    def __init__(
        self,
        runner: ModelRunner,
        tools: tuple[ToolSpec, ...],
        describe: Callable[[Document], str],
        *,
        memory_turns: int = MEMORY_TURNS,
    ):
        self._runner = runner
        self._tools = tools
        self._describe = describe
        self._memory_turns = memory_turns
        self._memory: dict[str, deque[Message]] = {}

    async def plan_async(self, task: Task) -> list[Step]:
        """The steps for what the asker wrote. Raises ``ModelError`` (the assistant tells the asker)."""
        key = task.sender.casefold()
        history = tuple(self._memory.get(key, ()))
        request = Request(task.sender, task.text, self._describe(task.document), self._tools, history)
        turn = await self._runner.answer(request)
        memory = self._memory.setdefault(key, deque(maxlen=2 * self._memory_turns))
        memory.append({"role": "user", "content": task.text})
        memory.append({"role": "assistant", "content": turn.say or "Done."})
        return steps_of(turn)
