"""The bug tracker (``bugtracker-open.md``, ``bugtracker-fixed.md``) in both directions.

The index tables are the status of record (``tests/test_bugtracker.py``): an item's row is in the *Open* table of
the open file or the *Fixed* table of the fixed file, and its ``### ID`` sections live in the same file. A row
changes cell by cell; an item that is closed or reopened in Taiga moves, row and sections, to the other file.
"""

from __future__ import annotations

import re
import subprocess
from datetime import date

from client import FIXED_MD, LOG, OPEN_MD, REPO, join_footer, split_footer
from merge import merge, rewrap, unwrap, unwrap_units

ID_RE = r"[A-Z]+-\d+"
ROW = re.compile(rf"^\| ({ID_RE}) \|")
PRIO = {"P1": "High", "P2": "Normal", "P3": "Low"}
PRIO_BACK = {v: k for k, v in PRIO.items()}
RANK = {"P1": 1, "P2": 2, "P3": 3}
CLOSED = {"Closed", "Rejected"}
PREFIXES = {"sec": "Security", "perf": "Performance", "ux": "UX", "proc": "Process", "code": "Code",
            "doc": "Docs", "web": "Website"}
STATUS_WORDS = {"New": "open", "In progress": "in progress", "Ready for test": "in progress (ready for test)",
                "Needs Info": "needs decision", "Postponed": "postponed"}
FIELDS = ("id", "title", "state", "status_text", "pri", "tpri", "category", "opened", "fixed", "body", "tags")


def clean(s: str) -> str:
    return re.sub(r"\*\*", "", s).strip()


def demote(line: str) -> str:
    return "#" + line if line.startswith("### ") else line


def status_for(status_cell: str, closed_file: bool) -> str:
    """The Taiga status of an index row (the mapping of the first export, 2026-11-26)."""
    s = clean(status_cell).replace("`", "").lower()
    if closed_file:
        if s.startswith(("superseded", "wontfix", "closed")):
            return "Rejected"
        if s.startswith("open") and "fixed" not in s:
            return "Postponed"
        return "Closed"
    if "needs decision" in s or "needs the owner" in s:
        return "Needs Info"
    if "postponed" in s or "deferred" in s:
        return "Postponed"
    if "in progress" in s or "partly fixed" in s:
        return "In progress"
    return "New"


def fields_of(view: dict) -> dict:
    body, meta = split_footer(view["description"])
    ident, _, title = view["subject"].partition(" ")
    return {"id": ident, "title": title.strip(), "state": view["status"], "status_text": meta.get("Tracker status", ""),
            "pri": meta.get("Priority", ""), "tpri": view["priority"], "category": meta.get("Category", ""),
            "opened": meta.get("Opened", ""), "fixed": meta.get("Fixed", ""), "body": body, "tags": view["tags"]}


class TrackerFile:
    def __init__(self, path, table: str):
        self.path, self.table = path, table
        self.lines = path.read_text(encoding="utf-8").split("\n")
        self.dirty = False

    def save(self) -> None:
        self.path.write_text("\n".join(self.lines), encoding="utf-8")

    def heading(self) -> int:
        return next(i for i, l in enumerate(self.lines) if re.match(rf"^### {self.table} \(\d+\)$", l))

    def index_end(self) -> int:
        return next(i for i, l in enumerate(self.lines) if i > self.heading() and l.startswith("## "))

    def rows(self) -> list[tuple[int, list[str]]]:
        out = []
        for i in range(self.heading(), self.index_end()):
            if ROW.match(self.lines[i]):
                out.append((i, [c.strip() for c in self.lines[i].split("|")[1:-1]]))
        return out

    def row(self, ident: str) -> tuple[int, list[str]] | None:
        return next(((i, c) for i, c in self.rows() if c[0] == ident), None)

    def recount(self) -> None:
        h = self.heading()
        line = f"### {self.table} ({len(self.rows())})"
        if self.lines[h] != line:
            self.lines[h], self.dirty = line, True

    def sections(self, ident: str) -> list[tuple[int, int]]:
        """Each ``### ID`` section as (first line, end); the same bounds as the exporter's."""
        out, i = [], 0
        while i < len(self.lines):
            if re.match(rf"### {re.escape(ident)}\b", self.lines[i]):
                j = i + 1
                while j < len(self.lines) and not re.match(r"#{1,3} ", self.lines[j]):
                    j += 1
                out.append((i, j))
                i = j
            else:
                i += 1
        return out

    def set_row(self, i: int, cells: list[str]) -> None:
        line = "| " + " | ".join(cells) + " |"
        if self.lines[i] != line:
            self.lines[i], self.dirty = line, True

    def insert_row(self, cells: list[str]) -> None:
        rows = self.rows()
        line = "| " + " | ".join(cells) + " |"
        if self.table == "Open":  # by priority, at the end of its own
            rank = RANK.get(clean(cells[1]), 4)
            after = [i for i, c in rows if RANK.get(clean(c[1]), 4) <= rank]
        else:  # by ID: after the last of its category with a lower number
            pre, num = cells[0].split("-")
            after = [i for i, c in rows if c[0].split("-")[0] == pre and int(c[0].split("-")[1]) < int(num)]
        at = (after[-1] + 1) if after else (rows[-1][0] + 1 if rows else self.heading() + 2)
        if not after and self.table == "Open" and rows:
            at = rows[0][0]
        self.lines.insert(at, line)
        self.dirty = True
        self.recount()

    def remove_row(self, ident: str) -> list[str]:
        i, cells = self.row(ident)
        del self.lines[i]
        self.dirty = True
        self.recount()
        return cells

    def cut_sections(self, ident: str) -> list[str]:
        out: list[str] = []
        for start, end in reversed(self.sections(ident)):
            block = self.lines[start:end]
            while block and not block[-1].strip():
                block.pop()
            out = block + [""] + out
            del self.lines[start:end]
            self.dirty = True
        return out

    def append_under(self, title: str, block: list[str]) -> None:
        """Add ``block`` at the end, under a ``## title`` written once per day."""
        while self.lines and not self.lines[-1].strip():
            self.lines.pop()
        last_h2 = max((i for i, l in enumerate(self.lines) if l.startswith("## ")), default=-1)
        if last_h2 < 0 or self.lines[last_h2] != f"## {title}":
            self.lines += ["", f"## {title}"]
        self.lines += [""] + [l for l in block] + [""]
        while len(self.lines) > 1 and not self.lines[-1].strip() and not self.lines[-2].strip():
            self.lines.pop()
        self.dirty = True


class Tracker:
    def __init__(self) -> None:
        self.open = TrackerFile(OPEN_MD, "Open")
        self.fixed = TrackerFile(FIXED_MD, "Fixed")

    def files(self):
        return (self.open, self.fixed)

    def where(self, ident: str) -> tuple[TrackerFile, int, list[str]] | None:
        for f in self.files():
            r = f.row(ident)
            if r:
                return f, r[0], r[1]
        return None

    def ids(self) -> list[str]:
        return [c[0] for f in self.files() for _, c in f.rows()]

    def save(self) -> list[str]:
        written = []
        for f in self.files():
            if f.dirty:
                f.save()
                written.append(f.path.name)
        return written

    # -- the exporter

    def section_lines(self, ident: str) -> list[str]:
        """The item's sections in both files, joined the way the exporter joins them."""
        parts = []
        for f in self.files():
            for start, end in f.sections(ident):
                parts.append("\n".join(f.lines[start:end]).strip())
        return "\n\n".join(parts).split("\n") if parts else []

    def view_of(self, ident: str) -> dict:
        f, _, c = self.where(ident)
        closed_file = f is self.fixed
        body = unwrap("\n".join(demote(l) for l in self.section_lines(ident)))
        meta = [("Tracker status", c[4]), ("Priority", clean(c[1])), ("Category", c[2])]
        if c[5]:
            meta.append(("Opened", c[5]))
        if c[6]:
            meta.append(("Fixed", c[6]))
        srcs = sorted({g.path.name for g in self.files() if g.sections(ident)})
        meta.append(("Source", ", ".join(f"`claudiaoffice-log/{s}`" for s in srcs) or "(index row only)"))
        tags = [ident.split("-")[0].lower()] + [t.strip().lower() for t in re.split(r"[/,]", c[2]) if t.strip()]
        if clean(c[1]) in PRIO:
            tags.append(clean(c[1]).lower())
        return {"subject": f"{ident} {clean(c[3])}"[:490],
                "status": status_for(c[4], closed_file), "priority": PRIO.get(clean(c[1]), "Normal"),
                "description": join_footer(body if body else c[3], meta), "tags": sorted(set(tags))}

    # -- changes from Taiga

    def set_cell(self, ident: str, col: int, value: str) -> None:
        f, i, cells = self.where(ident)
        if clean(cells[col]) != clean(value) or cells[col] != value:
            cells[col] = value
            f.set_row(i, cells)

    def set_priority(self, ident: str, pri: str) -> None:
        f, i, cells = self.where(ident)
        if clean(cells[1]) == pri:
            return
        cells[1] = pri
        if f is self.open:  # keep the table in priority order
            f.remove_row(ident)
            f.insert_row(cells)
        else:
            f.set_row(i, cells)

    def move(self, ident: str, to_fixed: bool, today: str) -> None:
        src, dst = (self.open, self.fixed) if to_fixed else (self.fixed, self.open)
        if src.row(ident) is None:
            return
        cells = src.remove_row(ident)
        if to_fixed and not cells[6]:
            cells[6] = today
        if not to_fixed:
            cells[6] = ""
        dst.insert_row(cells)
        block = src.cut_sections(ident)
        if block:
            dst.append_under(f"Synced from Taiga, {today}" if to_fixed else f"Reopened in Taiga, {today}", block)

    def set_body(self, ident: str, new_body: str) -> None:
        """Merge Taiga's text into the item's sections; the units keep the tracker's own wraps."""
        raw = self.section_lines(ident)
        units = unwrap_units(raw, [demote(l) for l in raw])
        lines = merge(units, new_body, render=rewrap)
        lines = [l[1:] if re.match(rf"#### {re.escape(ident)}\b", l) else l for l in lines]
        # split back into sections
        parts: list[list[str]] = []
        for line in lines:
            if re.match(rf"### {re.escape(ident)}\b", line) or not parts:
                parts.append([])
            parts[-1].append(line)
        parts = [p for p in ("\n".join(p).strip().split("\n") for p in parts) if any(x.strip() for x in p)]
        home = self.where(ident)[0]
        places = [(f, s, e) for f in self.files() for s, e in f.sections(ident)]
        if not places:  # an item with an index row only gets its first section
            home.append_under(f"Synced from Taiga, {date.today().isoformat()}", [l for p in parts for l in p + [""]])
            return
        if [p for p in parts] == [[x for x in "\n".join(f.lines[s:e]).strip().split("\n")] for f, s, e in places]:
            return
        if len(parts) != len(places):  # the sections' count changed: all of the text goes where the first one was
            parts = [[l for p in parts for l in p + [""]][:-1]]
        for (f, s, e), part in reversed(list(zip(places, parts + [[]] * (len(places) - len(parts)), strict=False))):
            tail = []
            k = e
            while k > s and not f.lines[k - 1].strip():
                k -= 1
                tail.append("")
            f.lines[s:e] = part + tail if part else []
            f.dirty = True

    def next_id(self, prefix: str) -> str:
        """The next number of a category: in both files, and on every branch (the tracker's own rule)."""
        nums = [int(i.split("-")[1]) for i in self.ids() if i.startswith(prefix + "-")]
        try:
            refs = subprocess.run(["git", "-C", str(REPO), "for-each-ref", "--format=%(refname)", "refs/heads",
                                   "refs/remotes"], capture_output=True, text=True, check=True).stdout.split()
            if refs:
                found = subprocess.run(["git", "-C", str(REPO), "grep", "-h", "-o", "-E", rf"\b{prefix}-[0-9]+\b",
                                        *refs, "--", str(LOG.relative_to(REPO))], capture_output=True, text=True)
                nums += [int(x.split("-")[1]) for x in re.findall(rf"{prefix}-\d+", found.stdout)]
        except (OSError, subprocess.CalledProcessError):
            pass
        return f"{prefix}-{max(nums, default=0) + 1:02d}"

    def add(self, ident: str, title: str, pri: str, category: str, status_text: str, opened: str, body: str,
            closed: bool) -> None:
        f = self.fixed if closed else self.open
        cells = [ident, pri, category, title, status_text, opened, date.today().isoformat() if closed else ""]
        f.insert_row(cells)
        block = [f"### {ident} · {title} · {pri} · {status_text}"]
        block += [l for line in body.split("\n") for l in rewrap(line)] if body else []
        f.append_under(f"Reported in Taiga, {date.today().isoformat()}", block)
