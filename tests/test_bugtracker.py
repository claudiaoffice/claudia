"""The tracker's index tells the truth about itself (PROC-15).

``claudiaoffice-log/bugtracker.md`` opens with an index in two tables, *Open* and *Fixed*, each headed with its count.
The index is the status of record, so a fixed item left under *Open*, or a count that no longer matches its rows,
makes every reader (and every agent picking the next bug) start from a wrong picture.
"""

import re
from pathlib import Path

TRACKER = Path(__file__).resolve().parent.parent / "claudiaoffice-log" / "bugtracker.md"
HEADING = re.compile(r"^### (Open|Fixed) \((\d+)\)$")
ROW = re.compile(r"^\| ([A-Z]+-\d+) \|")


def _index() -> dict[str, tuple[int, list[list[str]]]]:
    """Each index table by name: the count its heading states, and its rows split into cells."""
    tables: dict[str, tuple[int, list[list[str]]]] = {}
    current = None
    for line in TRACKER.read_text(encoding="utf-8").splitlines():
        heading = HEADING.match(line)
        if heading:
            current = heading.group(1)
            tables[current] = (int(heading.group(2)), [])
        elif line.startswith("## "):
            current = None
        elif current and ROW.match(line):
            tables[current][1].append([cell.strip() for cell in line.strip("|").split("|")])
    return tables


def _says_fixed(status: str) -> bool:
    return re.match(r"^\**fixed\b", status, re.IGNORECASE) is not None


def test_the_tracker_has_both_index_tables():
    assert set(_index()) == {"Open", "Fixed"}


def test_each_index_heading_counts_its_rows():
    for name, (stated, rows) in _index().items():
        assert stated == len(rows), f"### {name} says {stated}, its table has {len(rows)} rows"


def test_no_item_under_open_says_it_is_fixed():
    _, rows = _index()["Open"]
    fixed = [row[0] for row in rows if _says_fixed(row[4])]
    assert not fixed, f"move these rows to the Fixed table: {fixed}"


def test_an_item_is_in_one_index_table_only():
    tables = _index()
    both = {row[0] for row in tables["Open"][1]} & {row[0] for row in tables["Fixed"][1]}
    assert not both, f"in Open and in Fixed: {sorted(both)}"


def test_the_open_items_are_in_priority_order():
    """The *Open* table says it is sorted by priority (P1, P2, P3, then items that wait for a decision without one)."""
    rank = {"P1": 1, "P2": 2, "P3": 3, "—": 4}
    _, rows = _index()["Open"]
    priorities = [rank.get(row[1], 4) for row in rows]
    late = [row[0] for row, before in zip(rows[1:], priorities, strict=False) if rank.get(row[1], 4) < before]
    assert priorities == sorted(priorities), f"out of priority order: {late}"
