# E7.12 architecture: the action catalog, and a check that the ai keeps up with it

Story: [[e7.12-ai-action-catalog|E7.12 AI action catalog]] · branch `e7-12-ai-action-catalog` (to be created when you say so) · status: **proposal, for you to agree or change**.

Diagrams: `mockups/e7-12-architecture-01-catalog.svg` (where things go) and `mockups/e7-12-architecture-02-seeing.svg` (how "can the ai see it" is checked).

## 1. The rule that decides where things go

**The catalog is data, written by whoever knows the app, next to the app. One checker, in development only, reads that data against the running code. Nothing about it runs in the server.**

This is the same rule as for `skills.md` (E7.2), for the same reason: the person who adds a feature to an app is the person who knows what the ai should do with it, so the line goes into the app's own package, in the commit that adds the feature. The server does not load the catalog; the model still gets its requests from `MODEL_METHODS` and its recipes from `skills.md`. The catalog only checks that those two agree with what a person can do. So there is no change to run-time behaviour in the first part of the story, and the risk of the checker breaking a running server is nil.

## 2. What I checked in the code

- A person's action is a protocol method: `methods_for(model_cls).describe()` lists them with their parameters and a `write` flag. Counts today: computes 152 (72 write), composes 159 (89 write), creates 130 (66 write). **50 of each are the core's**, shared by all three apps.
- Offered to a model today (look and change, for an owner who acts): computes 11, composes 25, creates 14. Of the changes: computes 5, composes 20, creates 8. The creates changes are `add_slide`, `set_slide_notes`, `add_object`, `set_text`, `set_paragraph_style`, `move_object`, `resize_object`, `remove_object`. `rotate_object` exists for people and is not offered.
- Many methods are not an action of a person at all: `hello`, `ping`, `presence`, `snapshot`, `set_locale`, the subscriptions. They are the wire between a client and the server. They get the kind **plumbing**, so a new one still has to be classified, but nobody asks what the ai does with them.
- Menus: `claudia-menus.xlsx` has 97 menu rows and 25 context-menu rows with a column per app, and no column that says which method an entry calls. The Linux client's `manifest.py` and the web's `menu-dispatch.ts` carry the menus in code; the existing check "menus neutralino" keeps the native menus in line with the workbook. No test reads the workbook today.
- What a model is told about a thing comes from the lens (`slide_lens.describe_object`, the document and workbook lenses). In creates, an object's rotation is printed only when it is not zero (`if data.get("rotation")`), the shapes list names a shape and nothing else, and a shape file (`builtin_shapes/triangle.json`) has an outline and no description of how it looks.
- The ai's reach is bounded by the asker's rights (E7.4). A viewer cannot read the history or the chat, so whatever the ai may read of them, a viewer's ai gets nothing.
- Shared objects (pictures, text boxes, shapes) have one body in the core (`ObjectBody`) in all three apps: the properties are listed once.

## 3. Where each piece goes, and why

### 3.1 The files (diagram 1, left)

One `ai/action-catalog.md` in each of `claudia_computes`, `claudia_composes`, `claudia_creates` and one in `claudia_server` for the 50 core methods and the list of **reasons** (a short id and a sentence each). The app's own line wins over the core's for a method both list (`search_replace` is one). A file looks like this:

```
---
app: composes
not_yet: 31
---
## Actions
| method        | kind    | ai       | note                              |
|---------------|---------|----------|-----------------------------------|
| replace_words | does    | yes      |                                   |
| make_list     | does    | not yet  | slice 1                           |
| undo          | does    | reserved | own-history                       |
| log           | looks   | not yet  | E7.13                             |
| ping          | plumbing|          |                                   |

## Seen
| thing.property | ai       | note                    |
| paragraph.style| yes      |                         |
| paragraph.list | not yet  | slice 1                 |
```

Plain words, no glossary entry: **yes** (the ai can), **reserved** (left to people, with a reason id from the core file), **not yet** (a person can, the ai cannot). *does* is a change, *looks* is a read, *plumbing* is nobody's action.

Why a table in Markdown: it reads and diffs well in review, and `skills.md` is Markdown already. Why `not_yet:` in the header: see 3.4.

### 3.2 The checker (diagram 1, middle)

`scripts/action_catalog.py`, beside `scripts/api_surface.py`, which has the same job for the public API (a file kept in step with the code, regenerated with `--write`, checked by a test). Classes: `Entry`, `Seen` (frozen), `Catalog` (parse, merge core and app, overview), `MenuMap` (the workbook). Then plain functions, one per rule, so each rule is one test and one message that names what to fix. It lives in `scripts/` and not in a package, because it must see the three apps and the server at once and no app may import another.

### 3.3 The rules (diagram 1, bottom middle)

1. **Every method is classified.** The methods of the table and the lines of the file are the same set, in both directions: a new method fails until it has a line, a removed one fails until its line goes.
2. **The kind matches the table:** a write method is *does*, a read is *looks*; *plumbing* may be either and is a deliberate line.
3. **yes means offered, and taught.** A *does* line with `yes` is in `MODEL_METHODS[app]` and not in `NOT_FOR_A_MODEL`, and at least one skill's `Uses:` names it. A *looks* line with `yes` is in the lens's `look_methods`; no skill is needed, the orientation says how to look.
4. **reserved has a reason** from the core file, and **no `yes` line is reserved**: the two cannot both be true.
5. **The `not yet` count equals `not_yet:` in the header** (the ratchet, 3.4).
6. **Menu entries name methods:** every row of *Menus* and *Context menus* that has a place in an app names, in a new column for that app, one or more methods of that app, or `view only`; every named method exists. This is how a feature a person can see in a menu cannot be missing from the catalog.
7. **Properties** (3.5): every property of a thing has a `Seen` line, and `yes` is backed by output.
8. **The overview is current:** `notes/ai-action-catalog.md` is exactly what the checker generates.

### 3.4 The ratchet

`not_yet: N` in each header must equal the number of `not yet` lines. Closing a gap lowers it in the same commit; **adding one cannot happen without editing the number**, which is a visible line in review. It is a convention the test makes visible, not a lock: a hurried commit can still raise N. I would add one sentence to `CONTRIBUTING.md`: a new `not yet` needs the owner's OK. (The checker cannot look at git history; I did not want it to.)

### 3.5 Seeing (diagram 2)

For each **thing** (creates: slide, object; composes: paragraph, table, floating object, page, suggestion; computes: cell, sheet, chart), the properties are the fields of its model class, listed once in a small table in `tests/ai_samples.py` (a thing, its class). Each property needs a `Seen` line. A `yes` is verified without a model: a **rich sample document** per app (`ai_samples.py`, every property set to a value other than its default) is asked the look request, one value of the answer is changed, and `lens.show` is run again; if the text did not change, the lens does not show that property and the check fails with its name. If the property is not in the sample's answer, the check fails with "the sample is too poor", so a `yes` can never pass by default.

Limit, said plainly: this proves that the text depends on the property, not that the words are useful. The rotation case is exactly the one it would not catch (a rotation of 0 prints nothing, and the sample has 270). That is why slice 2 has a test of its own for it and for the look of each shape.

### 3.6 The menu column (diagram 1, bottom right)

Three columns, **Methods computes / composes / creates**, at the end of *Menus* and *Context menus*. A pure view entry (zoom, palette, language) says `view only`. The test reads the workbook with `openpyxl`, which the repository already uses. **I fill the columns in as a draft by reading the web and Linux menu code; the workbook is yours, so you review the sheet.** The checker finds a wrong name, a missing column and a method that does not exist; it cannot find a plausible but wrong mapping.

### 3.7 The overview

`notes/ai-action-catalog.md`, generated by `scripts/action_catalog.py --write`, checked by rule 8, never edited by hand. One table per menu, a row per menu entry, a cell per app: *yes / not yet / reserved / view only*, and below it the methods no menu entry names, then the things and their properties, then the counts. It is the checklist you asked for.

## 4. Closing the first gaps (the slices after the catalog)

1. **Lists in composes.** Offer `make_list`, `continue_list`, `list_start`, `indent_item`, `set_style_numbering` to the model; add a skill "Make a list" with a worked example (the skill tests run every example on a real document, which is what caught four wrong examples in E7.2); the paragraph's list state is shown in the lens. The catalog lines move from `not yet` to `yes`, `not_yet:` goes down.
2. **Rotating in creates.** Offer `rotate_object`; always print `turned N°`; add to each shape file a one-line `looks` ("points up", "a circle", "a rectangle wider than high") and show it in the shapes list; add a skill "Build a figure from shapes" with the arrow recipe (triangle and rectangle, rotate, until E10.7 gives an arrow). A local model will not think of the recipe on its own, so it is in the skill.

Both are **bugs** with a failing test first (CONTRIBUTING rule 1), see section 7.

## 5. Tests: the seams (to agree with you under /tdd)

| Seam | What it catches | What it misses |
|---|---|---|
| `Catalog.parse` on text | a bad line, a missing reason, a duplicate | nothing about the code |
| the rules against the real method tables and lenses | a new method or request without a line, a `yes` that is not offered or not taught | whether a skill is any good |
| the workbook, read as it is | a menu entry without methods, a method that does not exist | a plausible wrong mapping |
| the seeing check on the rich samples | a property the lens does not show | whether the words help |
| the overview regenerated and compared | a catalog changed without its overview | — |
| the existing prompt and skill tests (E7.2), unchanged | the slices: what a model is offered and told, every example executed | the model's behaviour |

**Where the model is in the loop:** nowhere in these tests. "Use it before delivery" is run by me by hand against a model with a real key (and, if you have one, the local model), the result reported in the done message and not part of any gate. That is what your concern about Gherkin comes to: the feature file `specs/server/ai-action-catalog.feature` says in plain sentences what the checks guarantee, and every scenario is bound to a pytest with an `@unit:` tag, as for E7.2. It describes no model behaviour.

## 6. Order of work (vertical slices, each red then green)

1. Parse and classify the **creates** methods only (a tracer through every rule on one app).
2. Computes and composes, the core file, the reasons.
3. Yes means offered and taught.
4. The workbook columns and the menu rule.
5. The overview and its check.
6. Seeing, one thing at a time: creates object first.
7. The ratchet header.
8. Slice 1 (lists), slice 2 (rotating).

The size is mostly in step 2: about 440 lines to classify, most of them quick. The judgement calls (what is `reserved`, what is `not yet`) go in one list I show you before they are final.

## 7. Decisions for you

1. **The reasons.** Yours from the grilling: permissions and ownership, own history (undo, restore, setting a checkpoint), redaction, installing or running code, view-only state. I would add three, which you decide: **leaving** (export, print, download, anything that sends the document out: it goes into the exit record and is a person's act), **account** (password, recovery key, deleting a document, handing on ownership), **ai itself** (the ai's consent and mode). Add, drop or rename?
2. **The place:** `ai/action-catalog.md` per app plus one in the server for the core; the checker in `scripts/`, tests in the top-level `tests/`. Agreed?
3. **The ratchet** as in 3.4, a visible number and a sentence in `CONTRIBUTING.md`, not a lock. Agreed?
4. **"yes" for a change means offered and named in a skill's `Uses:`;** for a look only offered. Agreed?
5. **The workbook columns,** filled in by me as a draft, reviewed by you. Agreed?
6. **Bugs to log** (size 1 = huge … 3 = small), as the first commit on the branch, each closed by its slice: **UX-76** (2): the ai in composes cannot make or change a list, though the menu and the server have seven list actions; **UX-77** (2): the ai in creates cannot turn an object and is not told which way a shape points (rotation is shown only when not zero, shapes have no description). Log them with those IDs, or fix them now?
7. **Decision range:** D1580–D1599 is free in `ranges.md` (D1560–D1579 is E7.2). I suggest D1580–D1599 for this story. Agreed? Then I push the reservation to `main` and to the branch.

## 8. Not verified, and risks

- I have not run the 440 classifications; the counts above are from the method tables and `MODEL_METHODS` as they are on `main` today.
- The seeing check depends on each look result having a shape the perturbation can reach (nested dicts and lists); a lens that formats a whole result with one `json.dumps` would pass anything. The three lenses today pick fields one by one, which I read, not ran.
- `openpyxl` rewriting the workbook may drop features it does not know (data validation, comments). I will edit the two sheets and diff the cells before and after; if anything else changed I stop and ask.
- E6.31 (on `backlog`) adds slide objects in computes. If it merges first, the creates catalog and the computes catalog will have new things to classify; the rules will tell me, which is the point.
- Real-model behaviour after the two slices is not covered by any test (see 5).

## 9. Next

On your agreement: the Gherkin file for you to review, then the branch name and range reservation (pushed to `main` and to the branch), then coding when you say so.
