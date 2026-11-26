"""Put a text edited in Taiga back into a repo file without losing what Taiga cannot show.

The exporters flatten a file's body into Taiga's form: ``[[file|Shown]]`` links become ``Shown``, the tracker's hard
wraps are joined into one line per paragraph, dotpm's ``Parent:`` / ``Project:`` / ``## Subtasks`` lines are dropped.
A merge compares the repo's units (one per paragraph or line, keyed by their Taiga form) with the lines that came
back from Taiga: a unit whose key is unchanged keeps its original lines, links and wraps included; only what was
really edited in Taiga is written, in Taiga's words. Fixed units (dotpm's own lines) stay where they are.
"""

from __future__ import annotations

import difflib
import re
import textwrap
from dataclasses import dataclass, field

BLOCK = re.compile(r"\s*([-*+] |\d+[.)] |\||#|>|```)")


@dataclass
class Unit:
    key: str | None  # the unit's text in Taiga's form; None for a fixed unit
    raw: list[str] = field(default_factory=list)


def unwrap_units(lines: list[str], keyed: list[str] | None = None) -> list[Unit]:
    """Join hard-wrapped paragraph lines (lists, tables, headings, quotes and code stay as they are).

    ``keyed`` is the same text in the form whose join is the key (the tracker demotes ``###`` to ``####``); ``lines``
    is what the unit keeps as its raw text."""
    keyed = keyed if keyed is not None else lines
    units: list[Unit] = []
    code = False
    for raw, line in zip(lines, keyed, strict=True):
        if line.strip().startswith("```"):
            code = not code
            units.append(Unit(line, [raw]))
            continue
        prev = units[-1].key if units else ""
        if (not code and line.strip() and prev and prev.strip() and not BLOCK.match(line)
                and not prev.lstrip().startswith(("|", "#", "```")) and not prev.endswith("  ")):
            units[-1].key = prev.rstrip() + " " + line.strip()
            units[-1].raw.append(raw)
        else:
            units.append(Unit(line, [raw]))
    return units


def unwrap(md: str) -> str:
    return "\n".join(u.key for u in unwrap_units(md.split("\n")))


def rewrap(line: str, width: int = 120) -> list[str]:
    """A paragraph from Taiga, wrapped the way the tracker wraps its own."""
    if not line.strip() or len(line) <= width or line.lstrip().startswith(("|", "#", "```", ">")):
        return [line]
    m = re.match(r"(\s*(?:[-*+] |\d+[.)] )?)", line)
    lead = m.group(1) if m else ""
    return textwrap.wrap(line, width=width, initial_indent="", subsequent_indent=" " * len(lead),
                         break_long_words=False, break_on_hyphens=False) or [line]


def merge(units: list[Unit], new_text: str, render=lambda line: [line]) -> list[str]:
    """The repo's units with Taiga's ``new_text`` merged in. Leading and trailing blank units stay fixed."""
    keyed = [i for i, u in enumerate(units) if u.key is not None]
    while keyed and not units[keyed[0]].key.strip():
        keyed.pop(0)
    while keyed and not units[keyed[-1]].key.strip():
        keyed.pop()
    is_keyed = set(keyed)
    new_lines = new_text.split("\n") if new_text else []
    ops = difflib.SequenceMatcher(None, [units[i].key for i in keyed], new_lines, autojunk=False).get_opcodes()
    out: list[str] = []
    nxt = 0  # the next unit not yet written

    def flush_fixed(upto: int) -> None:
        nonlocal nxt
        while nxt < upto:
            if nxt not in is_keyed:
                out.extend(units[nxt].raw)
            nxt += 1

    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            for k in range(i1, i2):
                flush_fixed(keyed[k])
                out.extend(units[keyed[k]].raw)
                nxt = keyed[k] + 1
        else:
            if i2 > i1:
                flush_fixed(keyed[i2 - 1] + 1)
            for line in new_lines[j1:j2]:
                out.extend(render(line))
    flush_fixed(len(units))
    return out
