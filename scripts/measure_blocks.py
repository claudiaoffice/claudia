"""How small a document's history is in blocks, against sealing every change on its own (E2.5, D1269).

``uv run python scripts/measure_blocks.py --typing 200 2000 6000``      a typing log of each length, made in computes
``uv run python scripts/measure_blocks.py --document plan.claudia --name Ann``   the history of a real document

``--typing`` makes the log the way the first measurement did (2026-11-19): one ``set_cells`` per change in computes, a
mix of numbers, formulas and short text, cycling through 40 rows × 6 columns. ``--document`` reads the history of a
document file instead (blocks and journal) and asks for the password; it needs someone who holds the history key (an
owner or an editor). Nothing in the document is changed.

Both turn the history into the records the server seals (``history_items``) and measure them the same way: sealed one
by one (each record with its own nonce and tag, no compression across records) and folded into blocks by the real
packing code, in a throw-away document. Prints one row per log, as in the table of the E2.5 story.
"""

from __future__ import annotations

import argparse
import getpass
import json
import secrets
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path

from claudia_computes import AddSheet, SetCells, SheetId, WorkbookModel, parse_input
from claudia_core import Document, MemoryStore
from claudia_document_file import KdfParams, Part, begin, create_document, pack_journal, read_state, unlock
from claudia_document_file.crypto import seal
from claudia_server.filestore import history_items
from claudia_server.sealed import record_bytes

ROWS, COLUMNS = 40, 6
SHEET = SheetId("s1")
_CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
_PASSWORD = "Measure-only-1"


def typing_log(changes: int) -> list[bytes]:
    """The sealed records of ``changes`` edits made one cell at a time in a new workbook (the first record adds the
    sheet)."""
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet(SHEET, "Sheet1"), author="ana")
    for i in range(changes):
        row, column = (i // COLUMNS) % ROWS, i % COLUMNS
        value = (str(i * 7 % 1000), f"=A{row + 1}+{i % 10}", f"item {i}")[i % 3]
        doc.execute(SetCells(SHEET, ((row, column, parse_input(value)),)), author="ana")
    return [record_bytes(kind, data) for kind, data in history_items(doc.log)]


def document_log(path: Path, name: str) -> list[bytes]:
    """The history records of a document file (needs the history key)."""
    unlocked = unlock(path, name, getpass.getpass(f"Password of {name} in {path.name}: "))
    if unlocked is None:
        raise SystemExit("wrong name or password")
    return read_state(path, unlocked.keys).history


def one_by_one(payloads: Sequence[bytes]) -> int:
    key = secrets.token_bytes(32)
    return sum(len(seal(key, payload, b"measure")) for payload in payloads)


def in_blocks(payloads: Sequence[bytes]) -> tuple[int, int]:
    """Bytes and number of the history blocks that packing makes from ``payloads``."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "measure.claudia"
        owner = create_document(path, name="measure", app="computes", owner="M", password=_PASSWORD, kdf=_CHEAP)
        writer = begin(path, owner.keys)
        for payload in payloads:
            writer.append(Part.HISTORY, payload)
        pack_journal(path, owner.keys, writer).close()
        with zipfile.ZipFile(path) as z:
            stored = [z.read(n) for n in z.namelist() if n.startswith("history/") and n.endswith(".blk")]
    return sum(len(b) for b in stored), len(stored)


def row(label: str, payloads: Sequence[bytes]) -> dict[str, object]:
    single = one_by_one(payloads)
    blocked, count = in_blocks(payloads)
    return {
        "log": label,
        "records": len(payloads),
        "raw": sum(len(p) for p in payloads),
        "one_by_one": single,
        "in_blocks": blocked,
        "ratio": round(single / blocked, 1),
        "blocks": count,
    }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--typing", type=int, nargs="+", metavar="CHANGES", help="typing logs of these lengths")
    parser.add_argument("--document", type=Path, help="a document file whose history to measure")
    parser.add_argument("--name", help="the name to log in to --document with")
    parser.add_argument("--json", action="store_true", help="print the rows as JSON")
    args = parser.parse_args(argv)
    if not args.typing and not args.document:
        parser.error("give --typing or --document")
    if args.document and not args.name:
        parser.error("--document needs --name")

    rows = [row(f"typing {n}", typing_log(n)) for n in args.typing or ()]
    if args.document:
        rows.append(row(args.document.name, document_log(args.document, args.name)))
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    print("| Log | Records | Raw bytes | One by one | In blocks | Ratio | Blocks |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        sizes = " | ".join(f"{r[k]:,}".replace(",", " ") for k in ("raw", "one_by_one", "in_blocks"))
        print(f"| {r['log']} | {r['records']} | {sizes} | {r['ratio']} | {r['blocks']} |")


if __name__ == "__main__":
    main()
