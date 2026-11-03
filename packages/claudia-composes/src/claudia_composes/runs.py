"""Authorship runs: who wrote which stretch of a paragraph (E9.10, D63).

A paragraph's text comes with a list of runs that together are exactly as long as the text. A run names the person
who wrote it and, when the text came in by accepting a suggestion, whose suggestion it was (``via``). The runs are
part of the state the commands maintain, so they are rebuilt by replaying the log and nothing else is stored.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Run:
    """``length`` characters written by ``author`` (``None``: unknown), through ``via``'s suggestion if any."""

    length: int
    author: str | None
    via: str | None = None


def total(runs: list[Run]) -> int:
    """The number of characters the runs cover."""
    return sum(run.length for run in runs)


def normalized(runs: list[Run]) -> list[Run]:
    """The runs without empty ones, with neighbours of the same origin joined."""
    out: list[Run] = []
    for run in runs:
        if run.length <= 0:
            continue
        if out and (out[-1].author, out[-1].via) == (run.author, run.via):
            out[-1] = Run(out[-1].length + run.length, run.author, run.via)
        else:
            out.append(run)
    return out


def slice_runs(runs: list[Run], start: int, end: int) -> list[Run]:
    """The part of the runs from ``start`` up to ``end``."""
    out: list[Run] = []
    position = 0
    for run in runs:
        lo, hi = max(start, position), min(end, position + run.length)
        if lo < hi:
            out.append(Run(hi - lo, run.author, run.via))
        position += run.length
    return normalized(out)


def delete_runs(runs: list[Run], start: int, end: int) -> list[Run]:
    """The runs without the characters from ``start`` up to ``end``."""
    return normalized([*slice_runs(runs, 0, start), *slice_runs(runs, end, total(runs))])


def insert_runs(runs: list[Run], offset: int, new: list[Run]) -> list[Run]:
    """The runs with ``new`` put in at ``offset``."""
    return normalized([*slice_runs(runs, 0, offset), *new, *slice_runs(runs, offset, total(runs))])


def runs_to_data(runs: list[Run]) -> list[list]:
    """The plain-data form: ``[[length, author, via], ...]``."""
    return [[run.length, run.author, run.via] for run in runs]


def runs_from_data(data: list[list]) -> list[Run]:
    """Inverse of ``runs_to_data``."""
    return [Run(length, author, via) for length, author, via in data]
