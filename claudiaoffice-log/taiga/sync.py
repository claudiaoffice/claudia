"""Sync the backlog and the bug tracker with the Taiga project claudia-office.

    python3 claudiaoffice-log/taiga/sync.py pull [--dry-run] [--theirs] [--only backlog|bugs]
    python3 claudiaoffice-log/taiga/sync.py push [--dry-run] [--only backlog|bugs]
    python3 claudiaoffice-log/taiga/sync.py init [--force]

``pull`` brings what changed in Taiga since the last sync into the repo's Markdown files; it is differential twice
over. Only items whose ``modified_date`` moved are fetched, and of those only the fields that changed in Taiga are
written. ``sync-state.json`` keeps, per item, a fingerprint of every field as it was at the last sync: a field changed
in Taiga and not in the repo is written; a field changed on both sides is a conflict, reported and left alone
(``--theirs`` takes Taiga's). Items new in Taiga become new files, rows and sections; an item deleted in Taiga is
reported, never deleted from the repo.

``push`` creates in Taiga what is new in the repo (the exporters of 2026-11-26); it does not change existing items.
``init`` takes Taiga's present state as the last sync (once, after the first export).
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date

import backlog as bl
import bugs as bt
from client import Taiga, fingerprint, load_state, save_state

E_NUM = re.compile(r"^E\d+(\.\d+)?$")


class Run:
    def __init__(self, args) -> None:
        self.args = args
        self.t = Taiga()
        self.state = load_state()
        self.log: list[str] = []
        self.conflicts: list[str] = []
        self.backlog = bl.Backlog()
        self.tracker = bt.Tracker()
        self.today = date.today().isoformat()

    def say(self, line: str) -> None:
        self.log.append(line)
        print(line, flush=True)

    def want(self, part: str) -> bool:
        return self.args.only in (None, part)

    def write_subject(self, kind: str, d: dict, subject: str) -> dict:
        if self.args.dry_run:
            return {**d, "subject": subject}
        return self.t.req("PATCH", f"/{kind}/{d['id']}", {"subject": subject, "version": d["version"]})

    @staticmethod
    def entry(key: str, d: dict, fields: dict) -> dict:
        return {"key": key, "modified": d["modified_date"], "h": {f: fingerprint(v) for f, v in fields.items()}}

    # ------------------------------------------------------------------ backlog

    def task_view(self, kind: str, d: dict) -> dict:
        return self.t.epic_view(d) if kind == "epics" else self.t.story_view(d)

    def pull_task(self, kind: str, d: dict, entry: dict | None) -> dict | None:
        tv = bl.fields_of(self.task_view(kind, d))
        if entry is None:
            return self.new_task(kind, d, tv)
        tf = self.backlog.by_id(entry["key"])
        if tf is None:
            self.say(f"  ! {tv['num']}: its file is gone from the repo (dotpm id {entry['key']}); not synced")
            return entry
        rv = bl.fields_of(bl.view_of(tf))
        b = entry["h"]
        applied = []
        for f in bl.FIELDS:
            if fingerprint(tv[f]) == b.get(f):
                continue  # not changed in Taiga
            if rv[f] == tv[f]:
                b[f] = fingerprint(tv[f])
                continue
            if fingerprint(rv[f]) != b.get(f) and not self.args.theirs:
                self.conflicts.append(f"{tv['num']} {f}: changed in Taiga and in the repo ({tf.path.name})")
                continue
            if f in ("num", "epic"):
                self.say(f"  ! {rv['num']}: Taiga says {tv['num']} under {tv['epic']}; renumber or move it by hand")
                continue
            self.apply_task(tf, f, tv, rv)
            b[f] = fingerprint(tv[f])
            applied.append(f)
        if applied:
            tf.set("updatedAt", d["modified_date"][:19] + ".000Z")
            self.say(f"  {tv['num']:<8} {', '.join(applied)}  ({tf.path.name})")
        entry["modified"] = d["modified_date"]
        return entry

    def apply_task(self, tf: bl.TaskFile, f: str, tv: dict, rv: dict) -> None:
        if f == "title":
            self.backlog.rename(tf, tv["title"])
        elif f == "status":
            tf.set("status", tv["status"])
            parent = bl.unlink(tf.get("parentId")) if tf.get("parentId") else ""
            epic = self.backlog.by_num(bl.num_of(parent)) if parent else None
            if epic:
                epic.set_checkbox(tf.stem, tv["status"] in ("done", "cancelled"))
        elif f == "body":
            tf.set_body(tv["body"])
        elif f == "progress" and tv["progress"].isdigit():
            tf.set("progress", min(100, int(tv["progress"])))
        elif f == "priority" and tv["priority"] in ("critical", "high", "medium", "low"):
            tf.set("priority", tv["priority"])
        elif f in ("use_cases", "decisions", "risks"):
            tf.set_custom({"use_cases": bl.F_USE, "decisions": bl.F_DEC, "risks": bl.F_RISK}[f], tv[f])
        elif f == "tags":  # use cases and priority as tags, when their footer lines were not edited
            uses = [u for u in bl.USE_CASES if u.lower() in tv["tags"]]
            if [u.strip().lower() for u in rv["use_cases"].split(",") if u.strip()] != [u.lower() for u in uses] \
                    and tv["use_cases"] == rv["use_cases"]:
                tf.set_custom(bl.F_USE, ", ".join(uses))
            if tv["priority"] == rv["priority"]:
                prio = "high" if "priority-high" in tv["tags"] else "low" if "priority-low" in tv["tags"] else None
                current = tf.get("priority", "medium")
                if prio and prio != current:
                    tf.set("priority", prio)
                elif not prio and current in ("high", "low"):
                    tf.set("priority", "medium")

    def new_task(self, kind: str, d: dict, tv: dict) -> dict | None:
        if E_NUM.match(tv["num"]) and (tf := self.backlog.by_num(tv["num"])):
            self.say(f"  = {tv['num']}: already in the repo ({tf.path.name}); bound, the Taiga copy counts as synced")
            return self.entry(tf.get("id"), d, tv)
        epic = None
        if kind == "userstories":
            if not tv["epic"] or not (epic := self.backlog.by_num(tv["epic"])):
                self.say(f"  ! new story \"{d['subject']}\" (#{d['ref']}) has no epic in Taiga; link it to one")
                return None
            num = tv["num"] if (E_NUM.match(tv["num"]) and tv["num"].startswith(tv["epic"] + ".")
                                and not self.backlog.by_num(tv["num"])) else self.backlog.next_number(tv["epic"])
        else:
            num = tv["num"] if E_NUM.match(tv["num"]) and "." not in tv["num"] else self.backlog.next_number(None)
        title = d["subject"] if tv["num"] == num else f"{num} {d['subject']}"
        if title != d["subject"]:
            d = self.write_subject(kind, d, title)
            tv = bl.fields_of(self.task_view(kind, d))
        tf = self.backlog.create(title, epic, tv, d.get("created_date") or bl.now_iso())
        self.say(f"  + {num:<8} new {'story' if epic else 'epic'} from Taiga #{d['ref']}  ({tf.path.name})")
        return self.entry(tf.get("id"), d, tv)

    # ------------------------------------------------------------------ bugs

    def pull_issue(self, d: dict, entry: dict | None) -> dict | None:
        tv = bt.fields_of(self.t.issue_view(d))
        if entry is None:
            return self.new_issue(d, tv)
        ident = entry["key"]
        if self.tracker.where(ident) is None:
            self.say(f"  ! {ident}: no row in the tracker any more; not synced")
            return entry
        rv = bt.fields_of(self.tracker.view_of(ident))
        b = entry["h"]
        todo = []
        for f in bt.FIELDS:
            if fingerprint(tv[f]) == b.get(f):
                continue
            if rv[f] == tv[f] or f == "tags":
                b[f] = fingerprint(tv[f])
                continue
            if fingerprint(rv[f]) != b.get(f) and not self.args.theirs:
                self.conflicts.append(f"{ident} {f}: changed in Taiga and in the tracker")
                continue
            if f == "id":
                self.say(f"  ! {ident}: Taiga calls it {tv['id']} now; IDs are not changed by the sync")
                continue
            todo.append(f)
        if "state" in todo:
            closed = tv["state"] in bt.CLOSED
            if closed != (rv["state"] in bt.CLOSED):
                self.tracker.move(ident, closed, self.today)
            if "status_text" not in todo:
                words = (f"fixed {self.today} (closed in Taiga)" if tv["state"] == "Closed" else
                         f"wontfix (rejected in Taiga, {self.today})" if tv["state"] == "Rejected" else
                         bt.STATUS_WORDS.get(tv["state"], "open"))
                self.tracker.set_cell(ident, 4, words)
        for f in todo:
            if f == "title":
                self.tracker.set_cell(ident, 3, tv["title"])
            elif f == "status_text":
                self.tracker.set_cell(ident, 4, tv["status_text"])
                if tv["state"] not in bt.CLOSED and re.match(r"^\**fixed\b", tv["status_text"], re.I):
                    self.say(f"  ! {ident}: says fixed but is not closed in Taiga; the tracker's guard will object")
            elif f == "pri" and (tv["pri"] in bt.RANK or tv["pri"] == "—"):
                self.tracker.set_priority(ident, tv["pri"])
            elif f == "tpri" and "pri" not in todo:
                self.tracker.set_priority(ident, bt.PRIO_BACK[tv["tpri"]])
            elif f == "category":
                self.tracker.set_cell(ident, 2, tv["category"])
            elif f == "opened":
                self.tracker.set_cell(ident, 5, tv["opened"])
            elif f == "fixed":
                self.tracker.set_cell(ident, 6, tv["fixed"])
            elif f == "body":
                self.tracker.set_body(ident, tv["body"])
            b[f] = fingerprint(tv[f])
        if todo:
            self.say(f"  {ident:<9} {', '.join(todo)}")
        entry["modified"] = d["modified_date"]
        return entry

    def new_issue(self, d: dict, tv: dict) -> dict | None:
        if re.match(rf"^{bt.ID_RE}$", tv["id"]) and self.tracker.where(tv["id"]):
            self.say(f"  = {tv['id']}: already in the tracker; bound, the Taiga copy counts as synced")
            return self.entry(tv["id"], d, tv)
        first = re.match(r"^([A-Za-z]+)(?:-\d*)?[:\s]", d["subject"] + " ")
        prefix = next((p for p in bt.PREFIXES if p in tv["tags"]), None)
        title = d["subject"]
        if first and first.group(1).lower() in bt.PREFIXES:
            prefix = prefix or first.group(1).lower()
            title = d["subject"][first.end():].strip(" :") or d["subject"]
        if prefix is None:
            self.say(f"  ! new issue \"{d['subject']}\" (#{d['ref']}): tag it with one of {', '.join(bt.PREFIXES)}")
            return None
        ident = self.tracker.next_id(prefix.upper())
        others = [t for t in tv["tags"] if t not in bt.PREFIXES and t not in ("p1", "p2", "p3")]
        category = " / ".join([bt.PREFIXES[prefix]] + others)
        closed = tv["state"] in bt.CLOSED
        words = f"fixed {self.today}" if tv["state"] == "Closed" else "wontfix" if closed else \
            "new, open" if tv["state"] == "New" else bt.STATUS_WORDS.get(tv["state"], "open")
        d = self.write_subject("issues", d, f"{ident} {title}")
        tv = bt.fields_of(self.t.issue_view(d))
        self.tracker.add(ident, title, bt.PRIO_BACK[tv["tpri"]], category, words,
                         (d.get("created_date") or self.today)[:10], tv["body"], closed)
        self.say(f"  + {ident:<9} new issue from Taiga #{d['ref']}")
        return self.entry(ident, d, tv)

    # ------------------------------------------------------------------ the commands

    def pull(self) -> None:
        items = self.state["items"]
        kinds = ([("epics", "epic"), ("userstories", "us")] if self.want("backlog") else []) + \
            ([("issues", "issue")] if self.want("bugs") else [])
        for kind, tag in kinds:
            listing = self.t.listing(kind)
            seen = set()
            changed = [x for x in listing if items.get(f"{tag}:{x['id']}", {}).get("modified") != x["modified_date"]]
            print(f"{kind}: {len(listing)} in Taiga, {len(changed)} changed since the last sync", flush=True)
            for x in sorted(changed, key=lambda x: x["ref"]):
                key = f"{tag}:{x['id']}"
                d = self.t.req("GET", f"/{kind}/{x['id']}")
                if kind == "userstories" and "epics" not in d:
                    d["epics"] = x.get("epics")
                handler = self.pull_issue if kind == "issues" else lambda d, e, k=kind: self.pull_task(k, d, e)
                result = handler(d, items.get(key))
                if result is not None:
                    items[key] = result
            seen = {f"{tag}:{x['id']}" for x in listing}
            for key in [k for k in items if k.startswith(tag + ":") and k not in seen]:
                self.say(f"  ! {items[key]['key']}: deleted in Taiga; the repo keeps it")
                del items[key]
        self.finish()

    def push(self) -> None:
        items = self.state["items"]
        bound = {v["key"] for v in items.values()}
        if self.want("backlog"):
            taiga_nums = {x["subject"].split()[0]: x for k in ("epics", "userstories") for x in self.t.listing(k)}
            epic_ids = {v["key"]: int(k.split(":")[1]) for k, v in items.items() if k.startswith("epic:")}
            files = sorted(self.backlog.files.values(), key=lambda f: [int(x) for x in bl.num_of(f.get("title"))[1:].split(".")])
            for tf in files:
                num, is_epic = bl.num_of(tf.get("title")), tf.get("type") == "task"
                if tf.get("id") in bound or num in taiga_nums:
                    continue
                v = bl.view_of(tf)
                body = {"project": self.t.project, "subject": v["subject"], "description": v["description"],
                        "tags": v["tags"], "is_blocked": v["is_blocked"]}
                kind, table = ("epics", self.t.epic_status) if is_epic else ("userstories", self.t.us_status)
                body["status"] = Taiga.name_to_id(table, v["status"])
                self.say(f"  + {num:<8} to Taiga as a new {'epic' if is_epic else 'story'}")
                if self.args.dry_run:
                    continue
                d = self.t.req("POST", f"/{kind}", body)
                if is_epic:
                    epic_ids[tf.get("id")] = d["id"]
                else:
                    parent = self.backlog.by_num(v["epic"])
                    eid = epic_ids.get(parent.get("id")) if parent else None
                    if eid:
                        self.t.req("POST", f"/epics/{eid}/related_userstories", {"epic": eid, "user_story": d["id"]})
                        d = self.t.req("GET", f"/userstories/{d['id']}")
                    else:
                        self.say(f"  ! {num}: its epic is not in Taiga; the story is not linked")
                items[f"{'epic' if is_epic else 'us'}:{d['id']}"] = self.entry(
                    tf.get("id"), d, bl.fields_of(self.task_view(kind, d)))
        if self.want("bugs"):
            taiga_ids = {x["subject"].split()[0] for x in self.t.listing("issues")}
            bug = self.t.issue_type["Bug"]
            for ident in self.tracker.ids():
                if ident in bound or ident in taiga_ids:
                    continue
                v = self.tracker.view_of(ident)
                self.say(f"  + {ident:<9} to Taiga as a new issue")
                if self.args.dry_run:
                    continue
                d = self.t.req("POST", "/issues", {
                    "project": self.t.project, "subject": v["subject"], "description": v["description"],
                    "tags": v["tags"], "type": bug, "status": Taiga.name_to_id(self.t.issue_status, v["status"]),
                    "priority": Taiga.name_to_id(self.t.priority, v["priority"])})
                items[f"issue:{d['id']}"] = self.entry(ident, d, bt.fields_of(self.t.issue_view(d)))
        self.finish()

    def init(self) -> None:
        if self.state["items"] and not self.args.force:
            raise SystemExit("sync-state.json exists already; --force starts over from Taiga's present state")
        items: dict = {}
        for kind, tag in (("epics", "epic"), ("userstories", "us"), ("issues", "issue")):
            listing = self.t.listing(kind)
            print(f"{kind}: {len(listing)}", flush=True)
            for x in listing:
                d = self.t.req("GET", f"/{kind}/{x['id']}")
                if kind == "issues":
                    tv = bt.fields_of(self.t.issue_view(d))
                    key = tv["id"] if self.tracker.where(tv["id"]) else None
                else:
                    tv = bl.fields_of(self.task_view(kind, d))
                    tf = self.backlog.by_num(tv["num"])
                    key = tf.get("id") if tf else None
                if key is None:
                    self.say(f"  ! {d['subject'][:60]} (#{d['ref']}): nothing in the repo matches; a pull adds it")
                    continue
                items[f"{tag}:{d['id']}"] = self.entry(key, d, tv)
        self.state["items"] = items
        self.finish()

    def finish(self) -> None:
        for line in self.conflicts:
            print("  CONFLICT " + line)
        if self.args.dry_run:
            print("dry run: nothing written")
            return
        written = self.backlog.save() + self.tracker.save()
        save_state(self.state)
        print(f"written: {', '.join(written) if written else 'no files'}; state saved"
              + (f"; {len(self.conflicts)} conflicts left as they are" if self.conflicts else ""))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("command", choices=("pull", "push", "init"))
    p.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    p.add_argument("--theirs", action="store_true", help="on a conflict, take Taiga's value")
    p.add_argument("--only", choices=("backlog", "bugs"))
    p.add_argument("--force", action="store_true", help="init: start over even if a state exists")
    args = p.parse_args(argv)
    run = Run(args)
    getattr(run, args.command)()
    return 1 if run.conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
