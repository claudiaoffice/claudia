# Taiga sync

The backlog (`Projects/claudia-office/`) and the bug tracker (`bugtracker-open.md`, `bugtracker-fixed.md`) are
mirrored in the Taiga project *claudia-office*: epics and stories as Taiga epics and user stories, tracker items as
Taiga issues. The Markdown files stay the record; Taiga is where people can also work on them.

```sh
claudiaoffice-log/taiga/sync.sh pull --dry-run   # what changed in Taiga, and what a pull would write
claudiaoffice-log/taiga/sync.sh pull             # bring it into the files
claudiaoffice-log/taiga/sync.sh push --dry-run   # what is new in the repo and not yet in Taiga
```

`sync.sh` passes everything on to `sync.py` (`--theirs`, `--only backlog|bugs` too); `init` is only reachable
through `sync.py`.

Standard library only. Credentials come from `TAIGA_USERNAME` / `TAIGA_PASSWORD`, or else from the `taiga` MCP
server's entry in `~/.claude.json`. Commit `sync-state.json` together with the files a pull changed.

## Pull (Taiga → repo)

Differential twice over:

1. Only items whose `modified_date` moved since the last sync are fetched.
2. Of those, only the fields that changed in Taiga are written. `sync-state.json` keeps a fingerprint of every field
   as it was at the last sync. A field changed in Taiga only is written; a field changed in the repo only is left
   alone; a field changed on both sides is reported as a **CONFLICT** and left alone (`--theirs` takes Taiga's).
   The exit code is 1 while conflicts remain.

| Taiga | Backlog file |
|---|---|
| subject | `title`, and every `[[file\|title]]` link to it (epic lists, `## Subtasks`, `Parent:`) |
| status (and *blocked*) | `status`, and the checkbox in the epic's `## Subtasks` |
| description, above the rule | the body; paragraphs not edited keep their lines and `[[links]]` |
| footer: Progress, Priority, Use cases, Decisions, Risks | `progress`, `priority`, the custom fields |
| tags `all`, `edu`, … / `priority-high`, `priority-low` | use cases / priority (when their footer lines were not edited) |
| a new story linked to an epic | a new file with the next E-number of that epic (the subject in Taiga gets the number) |
| a new epic | a new file with the next E-number, listed in the project |

| Taiga | Tracker |
|---|---|
| subject (after the ID) | the title cell of the index row |
| status | the status cell; Closed / Rejected moves the row and its sections to `bugtracker-fixed.md` (under *Synced from Taiga, date*), New etc. moves them back (*Reopened in Taiga, date*) |
| priority, or the footer's Priority | the Pri cell, the *Open* table kept in priority order |
| footer: Tracker status, Category, Opened, Fixed | those cells |
| description, above the rule | the item's `###` sections; paragraphs not edited keep the tracker's wraps |
| a new issue tagged `sec`, `perf`, `ux`, `proc`, `code`, `doc` or `web` | a row and a section with the next ID of that category (on every branch); the subject in Taiga gets the ID |

Not synced by a pull, but reported: a story moved to another epic or renumbered in Taiga (do it by hand, the E-number
and the epic belong together), a changed issue ID, anything deleted in Taiga (the repo keeps it). Comments,
assignees and attachments stay in Taiga.

## Push (repo → Taiga)

Creates in Taiga what is new in the repo: epics, stories (linked to their epic) and tracker items, the way the first
export of 2026-11-26 wrote them. It does not change items Taiga already has; a change made in the repo reaches
Taiga only when somebody makes it there too.

## Init

`init` takes Taiga's present state as the last sync. Use it only for a fresh project right after an export; the
state committed here was seeded from what the first export actually sent, so the Taiga edits made before the sync
existed were pulled, not swallowed.
