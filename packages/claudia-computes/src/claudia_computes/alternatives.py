"""Alternatives: several values for one input, written ``{800, 1000, 1300}`` (E6.21, D294).

What a person types is read here and stored as an ordinary formula, ``=ALTERNATIVES(800,1000,1300)`` (or
``=SCENARIOS("low",800,"base",1000)`` when the alternatives have names). Everything that already follows formulas
then works on them without a special case: cells they name, rows inserted above them, copying, the history.
``formula.forms.alternatives.brace_text`` gives the form the person typed back, for the formula bar.

A list holds values, ranges (``800..1300 step 250``) and formulas (``=B2*0.9``), and may be a mix. A name comes
before a colon (``low: 800``). Text that is not a well-formed list stays text: typing never fails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

MAX_ALTERNATIVES = 1_000  # in one cell: a range that would give more is not read as alternatives
_RANGE = re.compile(r"(-?\d+(?:\.\d+)?)\s*\.\.\s*(-?\d+(?:\.\d+)?)(?:\s+step\s+(-?\d+(?:\.\d+)?))?")
_LABELLED = re.compile(r"([^\W\d][\w ]*?)\s*:\s*(.+)", re.DOTALL)
_CELL_LIKE = re.compile(r"\$?[A-Za-z]{1,3}\$?\d+")
_COLUMN_LIKE = re.compile(r"\$?[A-Za-z]{1,3}")


@dataclass(frozen=True, slots=True)
class Alternative:
    """One alternative: what it is called (or ``None``) and the formula text that gives its value."""

    label: str | None
    source: str


def parse_alternatives(text: str) -> tuple[Alternative, ...] | None:
    """The alternatives that ``text`` is, or ``None`` when it is not a well-formed ``{...}`` list."""
    body = text.strip()
    if len(body) < 2 or body[0] != "{" or body[-1] != "}":
        return None
    parts = _split(body[1:-1])
    if parts is None:
        return None
    found: list[Alternative] = []
    for part in parts:
        expanded = _item(part.strip())
        if expanded is None:
            return None
        found.extend(expanded)
        if len(found) > MAX_ALTERNATIVES:
            return None
    return tuple(found) if found else None


def _split(body: str) -> list[str] | None:
    """The parts between the commas that are not inside brackets or text; ``None`` when they do not balance."""
    parts: list[str] = []
    depth = start = 0
    quoted = False
    for at, char in enumerate(body):
        if char == '"':
            quoted = not quoted
        elif quoted:
            continue
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth < 0:
                return None
        elif char == "," and depth == 0:
            parts.append(body[start:at])
            start = at + 1
    if quoted or depth:
        return None
    parts.append(body[start:])
    return parts


def _item(part: str) -> list[Alternative] | None:
    if not part:
        return None
    label = None
    named = _LABELLED.fullmatch(part)
    if named and not _is_reference(named.group(1), named.group(2)):
        label, part = named.group(1).strip(), named.group(2).strip()
    span = _RANGE.fullmatch(part)
    if span:
        values = _expand(*span.groups())
        return None if values is None else [Alternative(label, v) for v in values]
    source = part[1:].strip() if part.startswith("=") else part
    return [Alternative(label, source)] if source else None


def _is_reference(before: str, after: str) -> bool:
    """``A1:B2`` and ``A:A`` are references, not a name before a colon."""
    before, after = before.strip(), after.strip()
    return bool(_CELL_LIKE.fullmatch(before) or (_COLUMN_LIKE.fullmatch(before) and _COLUMN_LIKE.fullmatch(after)))


def _expand(first: str, last: str, step: str | None) -> list[str] | None:
    try:
        low, high, by = Decimal(first), Decimal(last), Decimal(step) if step is not None else Decimal(1)
    except InvalidOperation:
        return None
    if by == 0 or (high - low) * by < 0:
        return None
    count = int((high - low) / by) + 1
    if count > MAX_ALTERNATIVES:
        return None
    return [_number_text(low + by * i) for i in range(count)]


def _number_text(value: Decimal) -> str:
    return str(int(value)) if value == value.to_integral_value() else format(value.normalize(), "f")


def formula_for(alternatives: tuple[Alternative, ...]) -> str:
    """The formula that stores ``alternatives``: ``ALTERNATIVES`` for a plain list, ``SCENARIOS`` when they are named
    (the names and values alternate; an unnamed one among named ones is called ``alt`` and its position, which reads
    back as a name)."""
    if all(a.label is None for a in alternatives):
        return "=ALTERNATIVES(" + ",".join(a.source for a in alternatives) + ")"
    parts: list[str] = []
    for position, a in enumerate(alternatives, start=1):
        label = a.label if a.label is not None else f"alt {position}"
        parts += ['"' + label.replace('"', '""') + '"', a.source]
    return "=SCENARIOS(" + ",".join(parts) + ")"
