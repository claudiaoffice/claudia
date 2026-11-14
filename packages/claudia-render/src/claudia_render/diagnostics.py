"""Reading a tool's complaints into messages with a line of the person's text (D393).

A diagnostic belongs to the person who wrote the text, so a line is a line of *their* text: what a plugin puts in front
of it (``CliSpec.prefix``) is subtracted, and a complaint about that part has no line. The readers are the ones a
manifest may name (:data:`~claudia_render.manifest.DIAGNOSTIC_READERS`); each is small and has a test against what the
real tool prints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .manifest import DIAGNOSTIC_READERS

SEVERITIES = ("error", "warning")
MAX_MESSAGE = 500
MAX_PLAIN_LINES = 5

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_TYPST = re.compile(
    r"^[^:\n]+:(?P<line>\d+):(?P<column>\d+): (?P<severity>error|warning): (?P<message>.*)$", re.MULTILINE
)
_TYPST_LOOSE = re.compile(r"^(?P<severity>error|warning): (?P<message>.*)$", re.MULTILINE)
_MERMAID_LINE = re.compile(r"Parse error on line (?P<line>\d+):")
_STACK = re.compile(r"^\s+at |^\S+\.\w+ \(|^\s*$")


@dataclass(frozen=True)
class Diagnostic:
    """One thing a tool said about the person's text: how bad, what, and where (line and column from 1)."""

    severity: str
    message: str
    line: int | None = None
    column: int | None = None

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {', '.join(SEVERITIES)}")

    def to_data(self) -> dict:
        """The plain-data form clients are sent."""
        return {"severity": self.severity, "message": self.message, "line": self.line, "column": self.column}

    @classmethod
    def from_data(cls, data: dict) -> Diagnostic:
        """Inverse of :meth:`to_data`."""
        return cls(data["severity"], data["message"], data.get("line"), data.get("column"))


def _clean(text: str) -> str:
    return _ANSI.sub("", text).replace("\r\n", "\n")


def _own_line(line: int, offset: int) -> int | None:
    own = line - offset
    return own if own >= 1 else None


def _typst(output: str, offset: int) -> tuple[Diagnostic, ...]:
    found = tuple(
        Diagnostic(m["severity"], m["message"][:MAX_MESSAGE], _own_line(int(m["line"]), offset), int(m["column"]))
        for m in _TYPST.finditer(output)
    )
    if found:
        return found
    loose = _TYPST_LOOSE.search(output)  # a tool that did not use the short format still says "error: ..."
    return (Diagnostic(loose["severity"], loose["message"][:MAX_MESSAGE]),) if loose else ()


def _mermaid(output: str, offset: int) -> tuple[Diagnostic, ...]:
    lines = [line for line in output.splitlines() if not _STACK.match(line)]
    if not lines:
        return ()
    parse = _MERMAID_LINE.search(output)
    if parse:
        after = [line for line in lines if line.startswith(("Expecting", "Unexpected"))]
        message = (after[0] if after else "Parse error")[:MAX_MESSAGE]
        return (Diagnostic("error", message, _own_line(int(parse["line"]), offset)),)
    first = lines[0].removeprefix("Error: ").strip()
    return (Diagnostic("error", first[:MAX_MESSAGE]),)


def _plain(output: str, offset: int) -> tuple[Diagnostic, ...]:
    lines = [line.strip() for line in output.splitlines() if line.strip()][:MAX_PLAIN_LINES]
    return (Diagnostic("error", "\n".join(lines)[:MAX_MESSAGE]),) if lines else ()


_READERS = {"typst-short": _typst, "mermaid-parse": _mermaid, "plain": _plain}


def read_diagnostics(reader: str, output: str, *, line_offset: int = 0) -> tuple[Diagnostic, ...]:
    """What ``output`` (a tool's own words, both streams) says, read by ``reader``; ``line_offset`` is how many lines
    the plugin put in front of the person's text."""
    if reader not in _READERS:
        raise ValueError(f"reader {reader!r}: one of {', '.join(DIAGNOSTIC_READERS)}")
    return _READERS[reader](_clean(output), line_offset)
