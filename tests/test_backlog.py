"""The backlog's dotpm files hang together: every story has an epic that lists it, and nothing points nowhere.

Since 2026-11-10 the backlog is one Markdown file per story, read by the dotpm ("project-manager") Obsidian plugin
(``claudiaoffice-log/README.md``). The plugin keeps a parent and its children linked from **both** sides — a story's
``parentId`` and its epic's ``subtaskIds``, an epic and the project's ``taskIds`` — and an agent editing one side
only is the most likely way for the board to go quietly wrong. Which decisions a story cites is checked in
``test_decision_log.py``, next to every other citation.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = ROOT / "claudiaoffice-log" / "Projects" / "claudia-office"
PROJECT = PROJECT_DIR / "claudia-office.md"
TASKS = PROJECT_DIR / "_tasks"

STATUSES = {"todo", "in-progress", "blocked", "review", "done", "cancelled"}  # .obsidian/plugins/project-manager
PRIORITIES = {"critical", "high", "medium", "low"}
LINK = re.compile(r"\[\[([^|\]]+)(?:\|[^\]]*)?\]\]")
STORY_ID = re.compile(r"^E\d+(\.\d+)?\b")


def front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path.name}: no front matter"
    fields = {}
    for line in match.group(1).splitlines():
        if line.startswith(" "):
            continue  # customFields' own entries
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def unquoted(value: str) -> str:
    return value.strip().strip('"')


def links(value: str) -> list[str]:
    return LINK.findall(value)


def tasks() -> dict[str, dict[str, str]]:
    return {path.stem: front_matter(path) for path in sorted(TASKS.glob("*.md"))}


def test_every_task_file_is_a_dotpm_task_with_known_values():
    wrong = []
    for stem, fields in tasks().items():
        if fields.get("pm-task") != "true":
            wrong.append(f"{stem}: not marked pm-task")
        if unquoted(fields.get("type", "")) not in ("task", "subtask"):
            wrong.append(f"{stem}: type {fields.get('type')!r}")
        if unquoted(fields.get("status", "")) not in STATUSES:
            wrong.append(f"{stem}: status {fields.get('status')!r} is not one of {sorted(STATUSES)}")
        if unquoted(fields.get("priority", "")) not in PRIORITIES:
            wrong.append(f"{stem}: priority {fields.get('priority')!r}")
        if not STORY_ID.match(unquoted(fields.get("title", ""))):
            wrong.append(f"{stem}: title {fields.get('title')!r} does not start with its E-number")
        progress = fields.get("progress", "")
        if not progress.isdigit() or not 0 <= int(progress) <= 100:
            wrong.append(f"{stem}: progress {progress!r}")
    assert not wrong, "\n".join(wrong)


def test_ids_and_story_numbers_are_unique():
    all_tasks = tasks()
    for key, what in (("id", "id"), ("title", "E-number")):
        seen: dict[str, str] = {}
        for stem, fields in all_tasks.items():
            value = unquoted(fields[key])
            if key == "title":
                value = STORY_ID.match(value).group(0)
            assert value not in seen, f"{stem} and {seen[value]} share the {what} {value!r}"
            seen[value] = stem


def test_a_story_and_its_epic_name_each_other():
    all_tasks = tasks()
    wrong = []
    for stem, fields in all_tasks.items():
        if unquoted(fields["type"]) == "subtask":
            parents = links(fields.get("parentId", ""))
            if len(parents) != 1 or parents[0] not in all_tasks:
                wrong.append(f"{stem}: parentId {fields.get('parentId')!r} is not one existing epic")
                continue
            parent = all_tasks[parents[0]]
            if stem not in links(parent.get("subtaskIds", "")):
                wrong.append(f"{stem}: its epic {parents[0]} does not list it under subtaskIds")
        for child in links(fields.get("subtaskIds", "")):
            if child not in all_tasks:
                wrong.append(f"{stem}: subtaskIds names {child}, which has no file")
            elif links(all_tasks[child].get("parentId", "")) != [stem]:
                wrong.append(f"{stem}: lists {child}, whose parentId is not this epic")
    assert not wrong, "\n".join(wrong)


def test_a_story_belongs_to_the_epic_its_number_says():
    wrong = []
    for stem, fields in tasks().items():
        if unquoted(fields["type"]) != "subtask":
            continue
        epic = STORY_ID.match(unquoted(fields["title"])).group(0).split(".")[0]
        parent = links(fields["parentId"])[0]
        if not parent.startswith(epic.lower() + "-"):
            wrong.append(f"{stem}: {epic} story filed under {parent}")
    assert not wrong, "\n".join(wrong)


def test_the_project_lists_every_epic_and_nothing_else():
    listed = links(front_matter(PROJECT).get("taskIds", ""))
    epics = {stem for stem, fields in tasks().items() if unquoted(fields["type"]) == "task"}
    assert set(listed) == epics, f"missing: {sorted(epics - set(listed))}; unknown: {sorted(set(listed) - epics)}"
    assert len(listed) == len(set(listed)), "an epic is listed twice in taskIds"
