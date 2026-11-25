"""The history of the original (D2005): what an owner's export brings of the document it was made of, as text.

An export's ``history.jsonl`` holds the commands of another document, with revisions that mean nothing in the new one
(D1272, PROC-37). What a person wants of it is who did what and when, so each step becomes one line of text: its
author's name and the sentence that document's history panel said of it. The messages of its chat that were for
everybody become lines too, in the same order of time; a private message was for two people and stays out, since the
note is read by every owner and editor of the new document. Nobody named in a line is given anything.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator

from claudia_core import CommandRegistry, OriginalLine
from claudia_core.errors import KernelError
from claudia_core.messages import EVERYBODY


def original_lines(
    history: Iterable[bytes] | None, chat: Iterable[bytes] | None, registry: CommandRegistry
) -> tuple[OriginalLine, ...]:
    """The lines of the note, oldest first: one per step of ``history`` (every branch), one per message of ``chat`` that
    was for everybody. ``registry`` decodes the steps of the document's app.

    It never refuses: it runs once the new document exists, and ``read_export`` has already checked that every line is
    JSON. What a hand-written file gets wrong shows as it is: a step this version cannot read by its kind, a missing
    name as unknown, a missing time as none; a line that is no object at all is nothing anybody did."""
    lines = [*_steps(history or (), registry), *_messages(chat or ())]
    return tuple(sorted(lines, key=lambda line: line.when))


def _items(payloads: Iterable[bytes], kind: str) -> Iterator[dict]:
    for payload in payloads:
        item = json.loads(payload)
        if isinstance(item, dict) and item.get("t") == kind and isinstance(item.get("d"), dict):
            yield item["d"]


def _steps(history: Iterable[bytes], registry: CommandRegistry) -> Iterator[OriginalLine]:
    for step in _items(history, "entry"):
        what = _summary(step.get("command"), registry)
        origin = step.get("origin", "do")
        yield _line(step, what if origin == "do" else f"{origin} · {what}")


def _summary(command: object, registry: CommandRegistry) -> str:
    """What the history panel of the original said of the step; the command's kind for one this version cannot read."""
    if not isinstance(command, dict):
        return "?"
    try:
        return registry.decode(command).summary
    except (KernelError, KeyError, TypeError, ValueError, AttributeError):  # another version's, or written by hand
        return str(command.get("k", "?"))


def _messages(chat: Iterable[bytes]) -> Iterator[OriginalLine]:
    for message in _items(chat, "chat"):
        if message.get("to", EVERYBODY) == EVERYBODY:
            yield _line(message, str(message.get("text", "")), said=True)


def _line(data: dict, what: str, *, said: bool = False) -> OriginalLine:
    when, who = data.get("time"), data.get("author")
    return OriginalLine(when if isinstance(when, str) else "", who if isinstance(who, str) else None, what, said)
