"""What the model is asked and how its answer is read (E7.1; the placeholder for the real agent, E7.5).

``Agent.messages`` builds the conversation the model gets from a ``Request``; ``Agent.parse`` turns the answer into a
``Turn``: what to say and which requests to make on the document. The rest of the system does not care how.

The provisional convention: the answer is plain text for the person; if the model was asked to change the document it
ends the text with a fenced block

    ```commands
    [{"method": "set_cells", "params": {"sheet": "s1", "cells": [{"row": 0, "col": 0, "input": "1"}]}}]
    ```

each entry being a request of the server's protocol, from the list of ``ToolSpec`` the request offers. The agent does
not know the protocol; whoever builds the ``Request`` says what may be asked, and whoever reads the ``Turn`` makes
the requests (as the user ``ai``, so they are checked, limited, locked, logged and undoable like anybody's).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from .model import LanguageModel, Message

CALL_LIMIT = 50  # requests one answer may make

SYSTEM_PROMPT = """You are "ai", an assistant working inside a shared document, next to the people who edit it.
Answer briefly and in the language you are spoken to.
{context}
{ability}"""

CAN_CHANGE = """Only if you were asked to change the document, end your answer with a block like this
(a JSON list of requests):
```commands
[{{"method": "<name>", "params": {{...}}}}]
```
Without such a block nothing in the document changes. The requests you may make:
{tools}"""

CANNOT_CHANGE = "You cannot change this document: you can only answer."

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_BLOCK = re.compile(r"```commands[ \t]*\n(.*?)```", re.DOTALL)
_CUT_OFF_BLOCK = re.compile(r"```commands.*", re.DOTALL)


@dataclass(frozen=True)
class ToolSpec:
    """A request the model may make: its name, how to write it, and what it does."""

    name: str
    signature: str
    summary: str


@dataclass(frozen=True)
class ToolCall:
    """A request the model asked for."""

    method: str
    params: dict


@dataclass
class Request:
    """One thing somebody asked, with everything the model may know about the document.

    ``context`` is free text about the document (its sheets, say); ``history`` are the earlier messages with this
    person."""

    asker: str
    text: str
    context: str = ""
    tools: tuple[ToolSpec, ...] = ()
    history: Sequence[Message] = ()


@dataclass
class Turn:
    """What the model answered: text for the asker, requests to make, and what in the answer could not be used."""

    say: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


class Agent:
    """The prompt and the reading of the answer."""

    def messages(self, request: Request) -> list[Message]:
        """The conversation the model gets."""
        if request.tools:
            tools = "\n".join(f"- {tool.signature}: {tool.summary}" for tool in request.tools)
            ability = CAN_CHANGE.format(tools=tools)
        else:
            ability = CANNOT_CHANGE
        system = SYSTEM_PROMPT.format(context=request.context, ability=ability)
        return [{"role": "system", "content": system}, *request.history, {"role": "user", "content": request.text}]

    def parse(self, raw: str, tools: Sequence[ToolSpec]) -> Turn:
        """Read an answer; only requests named in ``tools`` are taken."""
        text = _THINK.sub("", raw)
        turn = Turn()
        if "<think>" in text:  # the model ran out of room while thinking
            text = text.split("<think>", 1)[0]
            turn.problems.append(
                "I ran out of room while thinking. Ask again (shorter, or in smaller steps): "
                "the server limits how long my answers may be."
            )
        if found := _BLOCK.search(text):
            text = text[: found.start()] + text[found.end() :]
            self._take_calls(found.group(1), {tool.name for tool in tools}, turn)
        elif cut := _CUT_OFF_BLOCK.search(text):
            text = text[: cut.start()]
            turn.problems.append("My answer was cut off in the middle of my requests; nothing was changed.")
        turn.say = text.strip()
        return turn

    def respond(self, model: LanguageModel, request: Request, *, max_new_tokens: int, stop: Callable[[], bool]) -> Turn:
        """Ask the model and read its answer. This blocks: it runs on the worker thread. Raises ``ModelError``."""
        raw = model.generate(self.messages(request), max_new_tokens=max_new_tokens, stop=stop)
        return self.parse(raw, request.tools)

    @staticmethod
    def _take_calls(block: str, allowed: set[str], turn: Turn) -> None:
        try:
            items = json.loads(block)
            if not isinstance(items, list):
                raise ValueError("not a list")  # noqa: TRY301
        except ValueError as exc:
            turn.problems.append(f"I wrote requests that could not be read ({exc}); nothing was changed.")
            return
        if len(items) > CALL_LIMIT:
            turn.problems.append(
                f"I wrote {len(items)} requests; at most {CALL_LIMIT} are made at once, the rest were dropped."
            )
            items = items[:CALL_LIMIT]
        for item in items:
            name = item.get("method") if isinstance(item, dict) else None
            params = item.get("params", {}) if isinstance(item, dict) else None
            if not isinstance(name, str) or not isinstance(params, dict):
                turn.problems.append(f"I wrote a request that could not be read: {json.dumps(item)[:120]}")
            elif name not in allowed:
                turn.problems.append(f"I asked for something I am not allowed to do here: {name}.")
            else:
                turn.calls.append(ToolCall(name, params))
