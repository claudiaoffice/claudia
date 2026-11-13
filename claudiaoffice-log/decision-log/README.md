# The decision log

One decision is one file. The name says enough to decide from a directory listing whether a file is worth opening:

```
<number>-<status>-<applies-to>-<short-description>.md
0177-current-all-shared-object-layer-body-anchor.md
```

* **number**: the decision's number, four digits with leading zeros so the folder sorts in order. Everywhere
  else — code, notes, backlog — it is cited as `D177`, without the zeros.
* **status**, one of
  * `current` — the latest word on its topic, in force;
  * `undecided` — left open, but nothing waits for it (a proposal not yet confirmed by the owner is undecided too);
  * `blocking` — open, and work cannot go on until it is decided;
  * `superseded` — no longer in force; the file names its successor.
* **applies-to**: `composes`, `computes`, `creates`, or `all`. A decision that is not about one app alone —
  the server, the kernel, the container, the clients, the protocol — is `all`.
* **short-description**: a few lowercase words, hyphenated.

`_rounds.md` holds the prose that used to sit between the tables of the single-file log: the vision statement, the
reasons for each round and the earlier renumbering passes. `ranges.md` hands out numbers.

## Inside a file

```markdown
---
id: D177
title: "An object is a shared body plus an app-specific anchor"
status: current
applies-to: all
date: 2026-11-08
round: "Shapes, images and styles: one shared object layer (thirty-first round)"
supersedes: []
superseded-by: []
---

# D177 · An object is a shared body plus an app-specific anchor

The decision, in full.

**Notes.** Why, what was rejected, what follows from it.
```

The front matter repeats the status and the scope so a check can read them without parsing the file name.
`previous-id` appears on the few decisions that were renumbered after a collision.

## Writing and changing decisions

* **Take a number from your range** in `ranges.md` before writing the first decision. Never pick "the next free
  number" by looking at the folder: two branches doing that in parallel is exactly how D151, D160, D177–D179 and
  D204 came to mean two things at once.
* **A decision is replaced, never deleted.** The new one lists the old one under `supersedes`; the old one gets
  `status: superseded`, `superseded-by: [Dnew]`, and is renamed (`git mv`) so its file name says so too.
* **Changing a status renames the file.** Links between decisions are by number (`D177`), never by file name, so a
  rename breaks nothing. Obsidian `[[…]]` links to a decision file are therefore not used.
* **Cite by number.** A backlog story lists its decisions in the `decisions` field (`"D177, D178"`); code and notes
  write `D177` in prose.

## What the gate checks

`tests/test_decision_log.py`:

* every file name has the pattern above, and its number, status and scope agree with its front matter;
* no number is allocated twice;
* every `D<n>` cited in the code, the docs, the backlog's `decisions` fields and the decisions themselves exists here;
* `supersedes` and `superseded-by` point at real decisions, a superseded decision names its successor, and both
  sides of a supersession agree;
* every number in use lies in a range `ranges.md` has handed out.
