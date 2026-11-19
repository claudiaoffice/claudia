# Review of `tables.feature` and `objects-in-composes.feature` (draft of 2026-11-19)

How to answer: for each question, "ok" accepts my proposal; anything else replaces it. When all are answered I move the
answers into the feature files (and the decision log, with the id range you give me) and delete this file.

**Suggested order of review:** the invariants file first (12 scenarios, 8 `@core`), then in `tables.feature` only the
`@core` rules. The `@extended` rules and everything `@needs-decision` can wait for the answers below.
The `@core` rules are: inserting, filling with the keyboard, row/column/sort entries, sorting, options, totals, among
the paragraphs, long tables over pages, two people, assistive technology.

## A. What I saw when I looked at the table (throwaway run in Chrome, `main` + this branch at `496b3db`)

`composes-tables.md` §15 says the table was never looked at in a browser. I did that: a local server, Chrome, a new text
with two paragraphs, the table inserted with Ctrl+Shift+F, then typing. The scripts are throwaway and not in the
patch. I did **not** reproduce "the table is drawn twice" (one `<table>`, four rows, twelve boxes); that fix is with the
other agent and may already be in a branch I do not have. What I did see:

| # | What | Size | Seen |
|---|---|---|---|
| B1 | **Words are typed twice when a box is left with Tab or Enter.** Typed "A" + Enter gives "AA", "C" + Tab gives "CC", "Dee" + Tab gives "DeeDee"; the history shows two entries "typed …" each. Clicking elsewhere gives it once ("B"). Slow typing, 120 ms per key, makes no difference. It looks like two commits (the key handler and then the blur) where the second one adds to the first instead of replacing it. | 1 (huge: every table fill is wrong) | every time: Enter once, Tab in ten boxes |
| B2 | **The table was shown after "After"**, though my caret was at the end of "Before" (clicked there with the mouse, then Ctrl+Shift+F). The design says: right after the paragraph the caret is in. I do not know whether the anchor or only the drawing is wrong. | 2 (medium) | 1 of 1 (twice, mouse and keyboard) |
| B3 | **An empty table shows almost nothing**: the look "Rules" draws a line above and under the header and nothing between rows, empty boxes have no border and no hint. A new 3×4 table looks like one line, so one cannot tell there are rows to type in. The boxes exist (351×23 px each); they are just not visible. | 3 (small), but it is the "obviously not working" impression | 2 of 2 |
| B4 | With very fast typing (Playwright's default, no pause after Tab) words went into the wrong box, because focus moves only after the commit has been confirmed. A fast typist on a slow connection would meet the same. Not diagnosed further. | 2 (medium), unsure | 1 of 1 |

The scenarios now say "reads exactly 'Roof 1', once", "the history shows one entry per box", "the table is between
'Before' and 'After'", and "I can see where every box is, also while it is empty". They will fail on this commit until B1–B3 are fixed.

**Question 0:** B1 to B4 are in the table code that the other agent is working on. Do you want me to (a) leave them to
that agent and just put them in `bugtracker.md`, (b) fix B1–B3 in this branch after the scenarios are approved (the
failing scenarios first, then the fix, TDD), or (c) hand them to the other agent as the first acceptance tests?
*Proposal: (c) if that agent is still on the table, otherwise (b); and B1–B4 into the bugtracker either way.*

## B. Questions about behaviour (proposal first)

| Q   | Question                                                                                            | Proposal                                                                                                                                                                                                                                                                                                      |                                                                                                                                                         |
| --- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | The Insert dialog: "4 rows with a header" is 4 rows in all (1 header + 3 body) or 4 body rows?      | 4 rows in all, as in Word and LibreOffice; the dialog says "rows (including the header)". Default 3 × 3 with a header.                                                                                                                                                                                        | OK                                                                                                                                                      |
| 2   | After inserting, where is the caret?                                                                | In the first box of the header row; a header box is where a person starts typing.                                                                                                                                                                                                                             | OK                                                                                                                                                      |
| 3   | How fast must a 100 × 10 table be (insert and scroll)?                                              | Inserted and drawn in under 2 seconds on a normal laptop; I will measure first and only then pin a number.                                                                                                                                                                                                    | OK                                                                                                                                                      |
| 4   | The caret is in the middle of a paragraph: where does the table go?                                 | After that paragraph, which stays in one piece (the design note's rule).                                                                                                                                                                                                                                      | OK                                                                                                                                                      |
| 5   | The caret is in an empty paragraph: does the table replace it?                                      | Yes, the empty paragraph is used up, so no blank line is left behind.                                                                                                                                                                                                                                         | OK                                                                                                                                                      |
| 6   | The caret is already in a table and I choose Insert ▸ Table….                                       | The entry is not available inside a table (no table in a table); the dialog is not offered.                                                                                                                                                                                                                   | OK                                                                                                                                                      |
| 7   | Esc in a box: where does the caret go? And how does a keyboard-only person get *into* a table?      | Esc restores the box and puts the caret in the text after the table. Into a table: the arrow key down from the paragraph above, or the key for Table Options…; a Tab at the end of a table never traps (Tab in the last box adds a row, so Esc is the exit; it is announced). To be checked with BITV.        | OK                                                                                                                                                      |
| 8   | Words typed in a box but not yet committed: reload, lost connection.                                | Committed on every blur, on page hide, and before the connection is dropped; if the connection is lost, a box shows "not saved yet" and keeps the words until it is back.                                                                                                                                     | I think there is an overall concept for dealing with lost connection: we show a banner? Please check again if there is a separate decision needed here. |
| 9   | Pasting several lines into one box.                                                                 | The first line stays in the box, the rest go into the boxes below (rows are added if the table can grow), as in a spreadsheet. One undo.                                                                                                                                                                      | OK                                                                                                                                                      |
| 10  | Deleting the last body row / the only column.                                                       | Not deleted: one empty row / one column stays. To get rid of everything: Remove table.                                                                                                                                                                                                                        | Deleting the last row/col removes the table, no separate "remove table" necessary                                                                       |
| 11  | Delete row with the caret in the header.                                                            | Refused with a hint to use Table Options… (header rows).                                                                                                                                                                                                                                                      | OK                                                                                                                                                      |
| 12  | Merge Cells: "the box and its neighbour only" is what exists. Is that enough for the first version? | Yes; Merge and Split stay `@extended` and their scenarios are written but run last.                                                                                                                                                                                                                           | OK                                                                                                                                                      |
| 13  | Remove table: asks first?                                                                           | No question, because it is one undo and keeps its words; the history shows "Removed a table".                                                                                                                                                                                                                 | OK (same entry in log if last row/col is deleted)                                                                                                       |
| 14  | Deleting or splitting the paragraph the table hangs from.                                           | Split: the table stays with the first half. Delete the whole paragraph: the table moves to the previous paragraph (or the next, if there is none); it is never deleted by deleting a paragraph.                                                                                                               | OK                                                                                                                                                      |
| 15  | Backspace at the start of "After" / a selection across the table.                                   | Backspace only moves the caret into the table's last box, nothing is deleted. A selection that contains the table is deleted with the table, and the person is asked once ("Delete the table too?"), as with other objects. *Please check against the object rules of D1221–D1226 — I did not want to guess.* | OK                                                                                                                                                      |
| 16  | What the assistant may do with a table.                                                             | As in the design note: words only. "Add a column" is answered with "I can only change the words in a table". Scenarios stay `@needs-decision` until the stand-in assistant has a table lens in the tests.                                                                                                     | OK                                                                                                                                                      |
| 17  | Which real documents?                                                                               | One regular and one irregular table from `test-documents` / your real files; please name two, or tell me to choose.                                                                                                                                                                                           | please choose and tell me which you chose                                                                                                               |

## C. How we run it (my proposals, to be agreed)

- **Tool.** `pytest-bdd` with Python Playwright in `tests/e2e/`: the servers' start, the skip with a reason and CI step
  `uv run pytest tests/e2e` are already there. The existing `web/e2e/*.cjs` stay. The `.feature` files in this
  directory are the single source; the step code is shared with later features. *Alternative: `playwright-bdd` in
  TypeScript, next to the `.cjs` scripts; it fits the web code better and fits the Python server's start worse.*
- **Browsers.** CI runs Chromium only today. I propose Chromium and Firefox for everything tagged `@firefox` (all
  `@core`), since Firefox is the browser you test with. In my workspace I have Chrome and can run Chromium-based
  runs, but not Firefox unless a download works; the first Firefox runs would then be CI's or yours. I will say so
  with every patch.
- **Cost of `@core`.** 43 + 8 scenarios is a lot for a first run: a table scenario takes 3–8 seconds, so about 5
  minutes, plus servers starting. Proposal: the whole `@core` set on every push to a branch's pull request, `@extended`
  nightly; and a rule that a scenario that needs more than ten steps is split.
- **Decision-log range.** The working agreement, the invariants rule and "scenarios are approved before coding" should be a
  decision (and the project instruction is already one). Please give me an id range if you want it in the log.
- **Where the specs live.** `claudiaoffice-log/specs/` as in the README of that folder; each story in `_tasks`
  gets a line "Specs: `specs/composes/tables.feature`" under its acceptance. I did not touch the stories yet.

I agree with all of these proposals. Please remind me / write me a file how I can run the e2e tests on my local computer; best would be a simple start script with parameters like "core-only" and "extended" etc. Script should explain itself on the command line.

## D. Second round (2026-11-19): your answers, what I checked, and what blocks

You answered all 17 and agreed with all of section C. Section A (B1–B4, Question 0) is still open; see below.

### D1. What I checked for your notes

- **Q8 (lost connection).** You are right: the web client already has the one concept, a banner for the whole page
  ("The connection was lost. Trying to get back… what you do now is not saved.", `DocumentFrame.vue`). **My per-box "not
  saved yet" is withdrawn**; no decision is needed for that part. The scenario now says: the banner is shown, what I type
  meanwhile is not saved, and after the return the table is as the server has it. What stays is the table's own small
  part, **N3**: commit what is in a box when the page is hidden (a reload while typing). Proposal: yes, as it costs
  nothing. (`@needs-decision`)
- **Q10 (last row or column removes the table).** This **contradicts D1213**, which says those entries are off ("no last
  row or column deleted"). It needs a decision that amends D1213: *deleting the last body row, or the only column, removes
  the table; one history entry "Removed a table"; one undo; no question.* **N1:** with a header row I mean the last
  *body* row (a table needs a body), so Q11 (header rows are not deleted as rows) and Q10 do not collide. Please confirm
  N1. I suggest the other agent writes the decision in its range D1201–D1220 (D1215–D1220 are free), because D1213 is its
  file and it is working on it now; I give it the two scenarios as acceptance.
- **Q13.** Consistent with D1225: `Del` removes the selected object without a question. The scenarios say "Delete table"
  in the table menu and `Del` on the selected table both give "Removed a table", one undo.
- **Q15 (checked against D1221–D1226 as I said I would).** They say nothing about a text selection that contains a table;
  they say `Del` on a selected object asks nothing. So "asked once" for a selection would be the one place that asks.
  **N4, a changed proposal:** a selection that contains the table deletes it with the text, no question, one undo brings
  all back. Please confirm or keep the question. (Backspace after the table stays as agreed.)
- **Q7** is now also D1224: `Esc` in a cell leaves the table completely, for the text.
- **Q17, chosen.** *Regular:* `test-documents/docx/beyond-claudia/table/source.docx` and its twin
  `odt/beyond-claudia/table/source.odt` (one table of two rows, no merges, two paragraphs around it). *Irregular:* a new
  fixture `tables-irregular` (a table inside a table, and a merge that is not a rectangle), to be added to
  `_build_fixtures.py` when we build the tests. Note: `docx/beyond-claudia/table/spec.py` still says claudia has no model
  for tables ("invisible"); since D1214 that is out of date, and the other agent presumably knows.
- **Section C.** Recorded as agreed. The runner script is in this patch (`./run-e2e.sh`, `scripts/run_e2e.py`,
  `specs/running.md`).
- **Decision ids.** `ranges.md` has D1201–D1220 (tables) and D1221–D1240 (object interaction, on its own branch). My
  proposal for this branch: **D1241–D1260**, "spec-first E2E: the working agreement, the shared invariants, decisions the
  table specs force". I have not written any decision yet. To be recorded in `ranges.md` in the commit of the first one.

### D2. What I found on the way, and what it does to the specs

1. **The other agent has found my symptoms.** D1224 says the object layer drew the table a second time over its own
   caption (the two frames, the dead "Options…" button), and that the default look drew no borders; its fix is a faint
   frame and cell lines always shown in the editor (B3 and "drawn twice"). **But the branch `object-interaction` holds only
   decisions, notes and mocks so far (`614cf6a`), no code**, so none of that can be seen yet. I built that branch and ran my
   throwaway script on it: B1 (words typed twice with Tab or Enter) and B2 (table after the wrong paragraph; D1213 says
   after the paragraph the caret is in) are there too, and the notes do not mention them. So B1, B2 and B4 are not on
   anybody's list that I can see.
2. **Scenarios that now wait for that branch** carry `@after:object-interaction` (the table menu, the editing aids, Delete
   table / `Del`). The Edit menu no longer carries Table options, Merge, Split and Sort (D1224).
3. **N2, a real gap.** D1224 says "Insert/delete and Height/width… stay on the row and column headers", and the note says
   composes' tables have *no header UI yet*. The old Edit ▸ Row and Column entries and their keys (D1208) are not
   mentioned. So today nobody has said where a person adds or deletes a row or a column in a composes table (Tab in the
   last box adds a row; that is all). The scenarios say what a person does, not where; that rule is `@needs-decision`.
4. **Overlap with `objects.cjs`.** The object-interaction note plans `web/e2e/objects.cjs`, one script for select, move,
   scale, the object menu and `Del`, for every kind of object. My invariants file overlaps a little ("I can work in it",
   "once"). Proposal: the Gherkin invariants own *being there once, reload, reconnect, undo, colleagues, files, names*;
   `objects.cjs` owns the pointer contract; the runner runs both.

### D3. Blocking items

**Blocking the first tests (needs you):**

| # | Item | What it blocks | Proposal |
|---|---|---|---|
| 1 | **N2** where row and column commands live in composes tables | the `@core` rule "I add and take away rows and columns" (5 scenarios) | decide with the other agent; the rest of the table specs does not wait for it |
| 2 | **Question 0** who owns B1, B2, B4 | nothing in the specs, but the tests will fail until somebody fixes them | the other agent gets them as acceptance tests, as soon as it is back; B1 is the one that matters most |
| 3 | **N1 + the amendment of D1213** (Q10) | two scenarios | confirm N1; the other agent writes the decision |
| 4 | **N4** selection delete: no question | one scenario | confirm |

**Waiting for the other agent's work, not for you:** everything tagged `@after:object-interaction`, and the code of D1224.

**Not blocking:** N3 (small), Q16 (the stand-in assistant needs a table lens first; those scenarios stay deferred), the
`tables-irregular` fixture (I build it with the tests), and the decision-id range (I only need it before I write the
first decision).

## E. Third round (2026-11-19, later): everything is merged, the owner answered, and it is built

**Answers (decided, recorded in D1241 to D1243):**

| # | Answer | Where it is now |
|---|---|---|
| Layout | "We'll take your own version": `specs/<app>/<feature>.feature`, `specs/objects/`, `specs/invariants/`. The flat `.md` files of the object-interaction branch were converted. | `specs/README.md` |
| Main | Work on main and push directly; nobody else is working. `@after:object-interaction` is gone. | tags in `tables.feature` |
| **N2** | The test comes first and fails; somebody else builds the header UI. | rule is `@pending:N2` (xfail, strict); keys of D1208 |
| **Q0** | B1, B2 and B4 are fixed in this work. | D1243; scenarios in "A table goes where my caret is…" and "I fill a table with the keyboard…" |
| **Q10** | D1213 stays: deleting the last body row or the only column does **not** remove the table. The owner wants to use it first. | two scenarios say "cannot be deleted"; rule is still `@needs-decision` for Q11 and the 100 and 10 limits |
| **N4** | Yes: a selection with a table in it is deleted without a question, one undo. | scenario no longer `@needs-decision`; no step code yet, so it skips |
| N1 | Not asked again: with a header, "the last body row" is meant. | the Q10 scenario |

**Still open for the owner:** Q11 (the header row is not deleted like a body row), N3, Q16, and what the "Options…" chip
and the faint frame should look like once you have used the table yourself.

**What runs:** `./run-e2e.sh core` runs the `@core` scenarios of this file that have step code; the others skip with the
missing step named. B3 ("drawn twice") is fixed on main (D1228): the "between" step looks again after a moment, and the
screenshots of every run are there to look at.
