"""The Markdown of speaker notes as the lines of a file that has none (D298).

A slide's notes are Markdown in the model (D293), and neither pptx nor odp has Markdown: both hold paragraphs of
runs that are bold or italic or neither. So the file gets what Markdown *means* -- ``**bold**`` a bold run, a
heading a bold line, a bullet a ``•`` in front of the line -- and a link, a code span, a picture or a quote is
written as plain words, which :func:`markdown_to_lines` says it did, so an export can report it.

A *line* is a list of :class:`Run`. List markers are text in it (``"• "``, ``"1. "``, two spaces per level of
nesting), so a file format that holds real lists maps them to its own list on the way out and back to the same
text on the way in, and this module need not know how.

:func:`lines_to_markdown` is the way back and the two are meant to meet in the middle: what was Markdown the app
could write comes back as the same Markdown; words from a file come back escaped, so what a person typed into
Word as ``2 * 3`` is not read as emphasis the next time.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

#: A bullet in a file: the marks other programs write at the start of a line, and the dash.
BULLET = "•"
_BULLET_MARKS = f"{BULLET}◦▪–—-"
_BULLET_LINE = re.compile(rf"(\s*)[{_BULLET_MARKS}]\s+")
_NUMBER_LINE = re.compile(r"(\s*)(\d+[.)])\s+")
_MARKDOWN_BULLET = re.compile(r"(\s*)[-*+]\s+(.*)")
_MARKDOWN_NUMBER = re.compile(r"(\s*)(\d+[.)])\s+(.*)")
_HEADING = re.compile(r"#{1,6}\s+(.*)")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)\)")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]*)\)")
_ESCAPABLE = "\\`*_{}[]()#+-.!>|~"
_TO_ESCAPE = re.compile(r"([\\`*_\[\]])")


@dataclass(frozen=True)
class Run:
    """Words that look one way: bold, italic, both or neither."""

    text: str
    bold: bool = False
    italic: bool = False


Line = list[Run]


def _merged(runs: Iterable[Run]) -> Line:
    """``runs`` without empty ones, and one run for neighbours that look the same."""
    merged: Line = []
    for run in runs:
        if not run.text:
            continue
        if merged and (merged[-1].bold, merged[-1].italic) == (run.bold, run.italic):
            merged[-1] = Run(merged[-1].text + run.text, run.bold, run.italic)
        else:
            merged.append(run)
    return merged


# -- Markdown to lines -------------------------------------------------------------------------------------------
def markdown_to_lines(markdown: str) -> tuple[list[Line], set[str]]:
    """``markdown`` as the lines a file holds, and which of ``"heading"``, ``"link"``, ``"image"``, ``"code"`` and
    ``"quote"`` it used, which the file shows only as plain words (a heading as a bold line)."""
    flattened: set[str] = set()
    lines: list[Line] = []
    in_fence = False
    for raw in markdown.split("\n"):
        text = raw.rstrip()
        if text.lstrip().startswith("```"):
            in_fence = not in_fence
            flattened.add("code")
        elif in_fence:
            lines.append(_merged([Run(raw)]))
        elif not text.strip():
            if not lines or lines[-1]:
                lines.append([])
        else:
            lines.append(_block(text, flattened))
    return lines, flattened


def _block(text: str, flattened: set[str]) -> Line:
    """One line of Markdown (not blank, not in a code fence) as the runs of a line."""
    heading = _HEADING.fullmatch(text)
    if heading:
        flattened.add("heading")
        return _merged(Run(run.text, True, run.italic) for run in _inline(heading.group(1), flattened))
    bullet = _MARKDOWN_BULLET.fullmatch(text)
    if bullet:
        return _merged([Run(f"{bullet.group(1)}{BULLET} "), *_inline(bullet.group(2), flattened)])
    number = _MARKDOWN_NUMBER.fullmatch(text)
    if number:
        return _merged([Run(f"{number.group(1)}{number.group(2)} "), *_inline(number.group(3), flattened)])
    if text.startswith(">"):
        flattened.add("quote")
        text = text[1:].removeprefix(" ")
    return _merged(_inline(text, flattened))


def _inline(text: str, flattened: set[str]) -> Line:
    """The runs of one line's words: emphasis made into looks, escapes undone, links and code made plain."""
    runs: Line = []
    state = {"bold": False, "italic": False}
    buffer: list[str] = []

    def flush() -> None:
        runs.append(Run("".join(buffer), state["bold"], state["italic"]))
        buffer.clear()

    def add(sub: Line) -> None:
        flush()
        runs.extend(Run(r.text, state["bold"] or r.bold, state["italic"] or r.italic) for r in sub)

    i = 0
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text) and text[i + 1] in _ESCAPABLE:
            buffer.append(text[i + 1])
            i += 2
        elif char == "`" and text.find("`", i + 1) > i:
            end = text.find("`", i + 1)
            buffer.append(text[i + 1 : end])
            flattened.add("code")
            i = end + 1
        elif char == "!" and (image := _IMAGE.match(text, i)):
            buffer.append(image.group(1))
            flattened.add("image")
            i = image.end()
        elif char == "[" and (link := _LINK.match(text, i)):
            add(_inline(link.group(1), flattened) + [Run(f" ({link.group(2)})")] if link.group(2) else [])
            flattened.add("link")
            i = link.end()
        elif char in "*_" and (found := _emphasis(text, i, state)):
            flush()  # what came before the mark looks the way it did before it
            for kind in found[1]:
                state[kind] = not state[kind]
            i += found[0]
        else:
            buffer.append(char)
            i += 1
    flush()
    return _merged(runs)


def _emphasis(text: str, i: int, state: dict[str, bool]) -> tuple[int, tuple[str, ...]] | None:
    """If the marks at ``i`` open or close emphasis, how many characters they are and which looks they flip in
    ``state``; ``None`` if they are just characters (``5 * 3``, ``snake_case``, a mark that never closes)."""
    mark = text[i]
    length = len(text[i:]) - len(text[i:].lstrip(mark))
    length = 3 if length == 3 else 2 if length >= 2 else 1
    kinds = ("bold", "italic") if length == 3 else ("bold",) if length == 2 else ("italic",)
    before = text[i - 1] if i else " "
    after = text[i + length] if i + length < len(text) else " "
    if all(state[kind] for kind in kinds):  # a closing mark: it follows a word, and with ``_`` it ends one
        if before.isspace() or (mark == "_" and after.isalnum()):
            return None
    elif not any(state[kind] for kind in kinds):  # an opening mark: it leads into a word and something closes it
        if after.isspace() or (mark == "_" and before.isalnum()) or not _closes(text, i + length, mark * length):
            return None
    else:
        return None
    return length, kinds


def _closes(text: str, start: int, marks: str) -> bool:
    """Is there, from ``start`` on, a ``marks`` that could close what opened?"""
    at = text.find(marks, start)
    while at >= 0:
        after = text[at + len(marks)] if at + len(marks) < len(text) else " "
        if at > start and not text[at - 1].isspace() and not (marks[0] == "_" and after.isalnum()):
            return True
        at = text.find(marks, at + len(marks))
    return False


# -- lines to Markdown -------------------------------------------------------------------------------------------
def lines_to_markdown(lines: Iterable[Sequence[Run]]) -> str:
    """The Markdown of the lines of a file: bold and italic runs as ``**`` and ``*``, a bullet or a number at the
    start of a line as a Markdown list, every other mark in the words escaped so it is read as the words it was.
    Empty lines at the end are dropped."""
    out = [_line(list(line)) for line in lines]
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def _line(runs: list[Run]) -> str:
    plain = "".join(run.text for run in runs)
    prefix = ""
    bullet = _BULLET_LINE.match(plain)
    number = _NUMBER_LINE.match(plain)
    if bullet:
        runs, prefix = _without(runs, bullet.end()), f"{bullet.group(1)}- "
    elif number:
        runs, prefix = _without(runs, number.end()), f"{number.group(1)}{number.group(2)} "
    body = "".join(_marked(run) for run in runs)
    if not prefix and body[:1] in ("#", ">", "+"):
        body = "\\" + body
    return prefix + body


def _without(runs: list[Run], count: int) -> list[Run]:
    """``runs`` without their first ``count`` characters."""
    kept: list[Run] = []
    for run in runs:
        if count >= len(run.text):
            count -= len(run.text)
        else:
            kept.append(Run(run.text[count:], run.bold, run.italic))
            count = 0
    return kept


def _marked(run: Run) -> str:
    """One run as Markdown, the marks around its words and not around the spaces at their edges."""
    core = run.text.strip()
    if not core:
        return run.text
    lead, trail = run.text[: len(run.text) - len(run.text.lstrip())], run.text[len(run.text.rstrip()) :]
    mark = ("**" if run.bold else "") + ("*" if run.italic else "")
    escaped = _TO_ESCAPE.sub(r"\\\1", core)
    return f"{lead}{mark}{escaped}{mark[::-1]}{trail}"
