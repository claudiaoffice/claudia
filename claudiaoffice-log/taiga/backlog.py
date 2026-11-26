"""The backlog's dotpm files (``Projects/claudia-office``) in both directions.

``view_of`` is the exporter: what a file looks like in Taiga. ``fields_of`` reads that form (or Taiga's) into the
fields the sync compares. The ``TaskFile`` methods change a file line by line, so a file that is synced keeps its
front matter's order and quoting and every line nobody changed.
"""

from __future__ import annotations

import json
import random
import re
import string
from datetime import UTC, datetime
from pathlib import Path

from client import PROJECT_MD, TASKS, join_footer, split_footer, unlink
from merge import Unit, merge

F_USE, F_DEC, F_RISK = "y349wfjfmw2k7pty", "p4t0cldrmw2k8l7j", "lejp26ewmw2k8c89"
USE_CASES = ["ALL", "PLATFORM", "PM", "FIN", "SCI", "DATA", "EDU"]

TO_TAIGA = {"todo": "New", "in-progress": "In progress", "review": "Ready for test",
            "blocked": "In progress", "done": "Done", "cancelled": "Archived"}
EPIC_TO_TAIGA = {**TO_TAIGA, "cancelled": "Done"}
FROM_TAIGA = {"New": "todo", "Ready": "todo", "In progress": "in-progress", "Ready for test": "review",
              "Done": "done", "Archived": "cancelled"}
FIELDS = ("num", "title", "status", "body", "progress", "priority", "use_cases", "decisions", "risks", "tags",
          "epic")
STRUCTURAL = re.compile(r"^(Project|Parent): \[\[.*\]\]\s*$")


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def unquote(value: str) -> str:
    value = value.strip()
    if value.startswith('"'):
        try:
            return json.loads(value)
        except ValueError:
            return value.strip('"')
    if value.startswith("'") and value.endswith("'") and len(value) > 1:
        return value[1:-1].replace("''", "'")
    return value


PLAIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9 .,_+()/-]|:(?! ))*$")  # safe as a plain YAML scalar


class TaskFile:
    def __init__(self, path: Path, text: str | None = None):
        self.path = path
        text = path.read_text(encoding="utf-8") if text is None else text
        m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
        if not m:
            raise ValueError(f"{path.name}: no front matter")
        self.fm = m.group(1).split("\n")
        self.body = m.group(2)
        self.dirty = False

    @property
    def stem(self) -> str:
        return self.path.stem

    def save(self) -> None:
        self.path.write_text("---\n" + "\n".join(self.fm) + "\n---\n" + self.body, encoding="utf-8")

    # -- front matter

    def _index(self, key: str) -> int | None:
        for i, line in enumerate(self.fm):
            if line.startswith(f"{key}:"):
                return i
        return None

    def get(self, key: str, default: str = "") -> str:
        i = self._index(key)
        return unquote(self.fm[i].partition(":")[2]) if i is not None else default

    def set(self, key: str, value: str | int) -> None:
        i = self._index(key)
        old = self.fm[i].partition(":")[2].strip() if i is not None else '""'
        if isinstance(value, int):
            text = str(value)
        elif old.startswith('"') or not old or not PLAIN.match(value or ""):
            text = json.dumps(value, ensure_ascii=False)
        else:  # the file wrote this key unquoted: so does the sync
            text = value
        line = f"{key}: {text}"
        if i is None:
            at = self._index("customFields")
            self.fm.insert(at if at is not None else len(self.fm), line)
        elif self.fm[i] != line:
            self.fm[i] = line
        else:
            return
        self.dirty = True

    def custom(self) -> dict[str, str]:
        i = self._index("customFields")
        out: dict[str, str] = {}
        if i is None:
            return out
        for line in self.fm[i + 1:]:
            if not line.startswith("  "):
                break
            k, _, v = line.strip().partition(":")
            out[k.strip()] = unquote(v)
        return out

    def set_custom(self, key: str, value: str) -> None:
        i = self._index("customFields")
        if i is None:
            if not value:
                return
            self.fm.append("customFields:")
            i = len(self.fm) - 1
        j = i + 1
        found = None
        while j < len(self.fm) and self.fm[j].startswith("  "):
            if self.fm[j].strip().startswith(f"{key}:"):
                found = j
            j += 1
        line = f"  {key}: {json.dumps(value, ensure_ascii=False)}"
        if found is not None and not value:
            del self.fm[found]
        elif found is not None:
            if unquote(self.fm[found].partition(":")[2]) == value:
                return
            self.fm[found] = line
        elif value:
            self.fm.insert(j, line)
        else:
            return
        i = self._index("customFields")
        if i is not None and (i + 1 >= len(self.fm) or not self.fm[i + 1].startswith("  ")):
            del self.fm[i]
        self.dirty = True

    def get_list(self, key: str) -> list[str]:
        i = self._index(key)
        if i is None:
            return []
        value = self.fm[i].partition(":")[2].strip()
        if value.startswith("["):
            return [unquote(x) for x in re.findall(r'"(?:[^"\\]|\\.)*"', value)]
        out = []
        for line in self.fm[i + 1:]:
            if not line.startswith("  - "):
                break
            out.append(unquote(line[4:]))
        return out

    def append_list(self, key: str, item: str) -> None:
        i = self._index(key)
        quoted = json.dumps(item, ensure_ascii=False)
        value = self.fm[i].partition(":")[2].strip()
        if value.startswith("["):
            inner = value[1:-1].strip()
            self.fm[i] = f"{key}: [{inner + ', ' if inner else ''}{quoted}]"
        else:
            j = i + 1
            while j < len(self.fm) and self.fm[j].startswith("  - "):
                j += 1
            self.fm.insert(j, f"  - {quoted}")
        self.dirty = True

    # -- body

    def relink(self, stem: str, shown: str) -> None:
        """Every ``[[stem|…]]`` in this file shows ``shown`` (quoted the YAML way inside the front matter)."""
        pattern = re.compile(r"\[\[" + re.escape(stem) + r"\|[^\]]*\]\]")
        fm_shown = json.dumps(shown, ensure_ascii=False)[1:-1]
        fm = [pattern.sub(lambda _m: f"[[{stem}|{fm_shown}]]", line) for line in self.fm]
        body = pattern.sub(lambda _m: f"[[{stem}|{shown}]]", self.body)
        if fm != self.fm or body != self.body:
            self.fm, self.body, self.dirty = fm, body, True

    def set_checkbox(self, stem: str, checked: bool) -> None:
        mark = "x" if checked else " "
        body = re.sub(r"(?m)^- \[.\] (\[\[" + re.escape(stem) + r"[|\]])", lambda m: f"- [{mark}] {m.group(1)}",
                      self.body)
        if body != self.body:
            self.body, self.dirty = body, True

    def append_checkbox(self, heading: str, link: str) -> None:
        lines = self.body.split("\n")
        try:
            h = lines.index(heading)
        except ValueError:
            lines += ["", heading]
            h = len(lines) - 1
        j = h + 1
        while j < len(lines) and lines[j].startswith("- ["):
            j += 1
        lines.insert(j, f"- [ ] {link}")
        self.body, self.dirty = "\n".join(lines), True

    def units(self) -> list[Unit]:
        units: list[Unit] = []
        in_subtasks = False
        for line in self.body.split("\n"):
            if line == "## Subtasks":
                in_subtasks = True
                units.append(Unit(None, [line]))
            elif in_subtasks and re.match(r"- \[.\] ", line):
                units.append(Unit(None, [line]))
            elif STRUCTURAL.match(line):
                in_subtasks = False
                units.append(Unit(None, [line]))
            else:
                in_subtasks = False
                units.append(Unit(unlink(line), [line]))
        return units

    def set_body(self, new_text: str) -> None:
        lines = merge(self.units(), new_text)
        body = "\n".join(lines)
        body = re.sub(r"\n{3,}", "\n\n", body)
        body = re.sub(r"([^\n])\n((?:Parent|Project): \[\[)", r"\1\n\n\2", body)
        if body != self.body:
            self.body, self.dirty = body, True


def body_of(tf: TaskFile) -> str:
    """The body as the exporter sends it (the same three substitutions as the first export of 2026-11-26)."""
    body = re.sub(r"(?m)^Project: \[\[.*?\]\]\s*$", "", tf.body)
    body = re.sub(r"(?m)^Parent: \[\[.*?\]\]\s*$", "", body)
    body = re.sub(r"(?ms)^## Subtasks\n(?:- \[.\] .*\n?)*", "", body)
    return unlink(body).strip()


def num_of(title: str) -> str:
    return title.split()[0] if title.split() else ""


def view_of(tf: TaskFile) -> dict:
    """The exporter: a task file as a Taiga epic or story (normalised view; ``client.Taiga.*_view`` has the same
    shape)."""
    title = tf.get("title")
    cf = tf.custom()
    status = tf.get("status", "todo")
    prio = tf.get("priority", "medium")
    is_epic = tf.get("type") == "task"
    meta = [("Status in repo", status), ("Progress", f"{tf.get('progress', '0')}%"), ("Priority", prio)]
    tags = []
    if cf.get(F_USE):
        meta.append(("Use cases", cf[F_USE]))
        tags += [t.strip().lower() for t in cf[F_USE].split(",") if t.strip()]
    if cf.get(F_DEC):
        meta.append(("Decisions", cf[F_DEC]))
    if cf.get(F_RISK):
        meta.append(("Risks", cf[F_RISK]))
    if prio in ("high", "low"):
        tags.append(f"priority-{prio}")
    meta.append(("Source", f"`claudiaoffice-log/Projects/claudia-office/_tasks/{tf.path.name}`"))
    parent = unlink(tf.get("parentId")) if tf.get("parentId") else ""
    return {"subject": title, "status": (EPIC_TO_TAIGA if is_epic else TO_TAIGA)[status],
            "is_blocked": status == "blocked", "description": join_footer(body_of(tf), meta),
            "tags": sorted(set(tags)), "epic": num_of(parent) if parent else None}


def fields_of(view: dict) -> dict:
    body, meta = split_footer(view["description"])
    status = FROM_TAIGA.get(view["status"], "todo")
    if view.get("is_blocked") and status in ("todo", "in-progress"):
        status = "blocked"
    return {"num": num_of(view["subject"]), "title": view["subject"], "status": status, "body": body,
            "progress": meta.get("Progress", "").rstrip("%").strip(), "priority": meta.get("Priority", ""),
            "use_cases": meta.get("Use cases", ""), "decisions": meta.get("Decisions", ""),
            "risks": meta.get("Risks", ""), "tags": view["tags"], "epic": view.get("epic")}


# ---------------------------------------------------------------- the whole backlog


class Backlog:
    def __init__(self) -> None:
        self.files = {p.stem: TaskFile(p) for p in sorted(TASKS.glob("*.md"))}
        self.project = TaskFile(PROJECT_MD)

    def by_id(self, dotpm_id: str) -> TaskFile | None:
        return next((f for f in self.files.values() if f.get("id") == dotpm_id), None)

    def by_num(self, num: str) -> TaskFile | None:
        return next((f for f in self.files.values() if num_of(f.get("title")) == num), None)

    def save(self) -> list[str]:
        written = []
        for f in [*self.files.values(), self.project]:
            if f.dirty:
                f.save()
                written.append(f.path.name)
        return written

    def link(self, tf: TaskFile) -> str:
        return f"[[{tf.stem}|{tf.get('title')}]]"

    def rename(self, tf: TaskFile, title: str) -> None:
        tf.set("title", title)
        for f in [*self.files.values(), self.project]:
            f.relink(tf.stem, title)

    def new_dotpm_id(self) -> str:
        taken = {f.get("id") for f in self.files.values()} | {self.project.get("id")}
        while True:
            candidate = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
            if candidate not in taken:
                return candidate

    def next_number(self, epic_num: str | None) -> str:
        nums = [num_of(f.get("title")) for f in self.files.values()]
        if epic_num is None:
            return f"E{max(int(n[1:].split('.')[0]) for n in nums) + 1}"
        mine = [int(n.split(".")[1]) for n in nums if n.startswith(epic_num + ".")]
        return f"{epic_num}.{max(mine, default=0) + 1}"

    def create(self, title: str, epic: TaskFile | None, fields: dict, created: str) -> TaskFile:
        """A new epic (``epic`` None) or story from Taiga, written the way dotpm writes one and listed on both sides."""
        num, rest = num_of(title), title.split(" ", 1)[1] if " " in title else ""
        slug = "-".join(re.sub(r"[^a-z0-9]+", " ", rest.lower()).split()[:6]) or "new"
        stem = f"{num.lower()}-{slug}"
        while stem in self.files:
            stem += "-2"
        def q(value: str) -> str:
            return json.dumps(value, ensure_ascii=False)

        parent_link = self.link(epic) if epic else ""
        fm = ["pm-task: true", 'projectId: "[[claudia-office|claudia-office]]"',
              f"parentId: {q(parent_link)}" if epic else "parentId:",
              f"id: {q(self.new_dotpm_id())}", f"title: {q(title)}", f"type: {q('subtask' if epic else 'task')}",
              f"status: {q(fields['status'])}", f"priority: {q(fields['priority'] or 'medium')}", 'start: ""',
              'due: ""', f"progress: {int(fields['progress'] or 0)}", "assignees: []", "tags: []", "subtaskIds: []",
              "dependencies: []", f"createdAt: {q(created)}", f"updatedAt: {q(now_iso())}"]
        custom = [(F_USE, fields["use_cases"]), (F_DEC, fields["decisions"]), (F_RISK, fields["risks"])]
        if any(v for _, v in custom):
            fm.append("customFields:")
            fm += [f"  {k}: {q(v)}" for k, v in custom if v]
        body = f"\n{fields['body']}\n\n" if fields["body"] else "\n"
        if epic:
            body += f"Parent: [[{epic.stem}|{epic.get('title')}]]\n"
        else:
            body += "Project: [[claudia-office|claudia-office]]\n\n## Subtasks\n"
        tf = TaskFile(TASKS / f"{stem}.md", "---\n" + "\n".join(fm) + "\n---\n" + body)
        tf.dirty = True  # written by save(), like every other change
        self.files[stem] = tf
        link = self.link(tf)
        parent = epic or self.project
        parent.append_list("subtaskIds" if epic else "taskIds", link)
        parent.append_checkbox("## Subtasks" if epic else "## Tasks", link)
        return tf
