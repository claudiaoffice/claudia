# claudiaoffice-log

The project's own memory, kept next to the code and opened as an Obsidian vault. Agents read it instead of the
claude.ai project context.

| Where | What |
|---|---|
| `Projects/claudia-office/` | The backlog: one file per epic and per story, for the dotpm ("project-manager") plugin |
| `decision-log/` | The decision log: one file per decision; its `README.md` has the rules, `ranges.md` the numbers |
| `bugtracker.md` | Bugs and QA findings (UX-, SEC-, PERF-, PROC-, DOC-, CODE- numbers) |
| `implementation-notes/` | What was built and why it looks the way it does, per feature |
| `notes/` | Design notes, spike results, mock-ups |

## The backlog

`Projects/claudia-office/claudia-office.md` is the project; `_tasks/` holds one file per epic (`type: "task"`,
`e10-claudia-creates.md`) and per story (`type: "subtask"`, `e10.8-images-and-figures.md`). Read only the files a
piece of work touches; the epic file lists its stories.

**A story's file.** The front matter is dotpm's; the body is the story, then `**Acceptance:**`, `**Notes:**` and
`**Status evidence:**` paragraphs, then `Parent: [[…]]`.

| Front-matter field | Meaning |
|---|---|
| `title` | `"E10.8 Images and figures"` — always starts with the story's E-number |
| `status` | `todo`, `in-progress`, `blocked`, `review`, `done` or `cancelled` |
| `progress` | 0–100, an estimate from the code, not from hope |
| `parentId` | `"[[e10-claudia-creates\|E10 claudia creates]]"`, the epic |
| `customFields.y349wfjfmw2k7pty` | **use cases**: `ALL`, `PLATFORM`, `PM`, `FIN`, `SCI`, `DATA`, `EDU` |
| `customFields.p4t0cldrmw2k8l7j` | **decisions**: `"D67, D66"` — numbers only, never file names |
| `customFields.lejp26ewmw2k8c89` | **risks**, free text |

The opaque keys are dotpm's ids for the project's custom fields (`claudia-office.md`, `customFields`).

**Adding or moving a story** means editing both sides: the story's `parentId` and the epic's `subtaskIds` and its
`## Subtasks` list; a new epic also goes into the project's `taskIds` and `## Tasks` list. Creating the story in
Obsidian does this by itself; an agent writing files has to do it by hand. `id` is 16 random lowercase letters and
digits, unique across the folder.

**Status follows the code.** A story is `done` when the tree shows it, and its status evidence names the files;
`tests/test_notes_claim_built_files.py` fails a paragraph that says "built" about a path that is not in the tree
(name a path that lives on another branch as `branch:path`).

## What the gate checks

* `tests/test_backlog.py` — every task file is a valid dotpm task; ids and E-numbers are unique; a story and its
  epic name each other; a story sits under the epic its number says; the project lists exactly the epics.
* `tests/test_decision_log.py` — the decision files follow their naming rule, no number is used twice, every number
  comes from a handed-out range, and every `D<n>` cited in the code, in a story's decisions field or in another
  decision exists.
