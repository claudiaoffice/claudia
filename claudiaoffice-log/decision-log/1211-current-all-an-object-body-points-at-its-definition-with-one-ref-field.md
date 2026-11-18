---
id: D1211
title: "An object body points at its definition with one field, ref, and the kind says where it is looked up"
status: current
applies-to: all
date: 2026-11-18
round: "Tables in composes (branch tables-in-composes)"
supersedes: []
superseded-by: []
---

# D1211 · An object body points at its definition with one field, ref, and the kind says where it is looked up

**`ObjectBody` has one field `ref` instead of one field per kind** (`shape`, `image`, `diagram`, `rendered`, `table`). The kind names the document's table of definitions that `ref` is looked up in: a shape's outline, an image's asset, a diagram's definition, a rendered container's text, a table's definition; a text box has none. Every kind already needed exactly its own pointer and none of the others, so the five fields could never hold more than one value between them, and each new kind (tables were the fifth) added a field, a generation of field sets that old documents still had to read, and a changed wording in the checks and tests of three apps.

**What stays.** `body.shape`, `body.image`, `body.diagram`, `body.rendered` and `body.table` stay as read-only properties that answer when the body is of that kind, so every reader keeps working; `imported` (an image's import record) is not a pointer and stays. The plain data of a body has `ref` and none of the five names.

**Documents are forever.** A body written the old way (any of the five generations) still reads: the pointer of the body's kind becomes `ref`, and a body with a pointer of another kind is refused, as no checked body ever had one. `core.AddObject` is schema 6 with an upcaster from 5; the state schemas of creates (16), computes (15) and composes (15) went up, so a snapshot is rebuilt from the log. The clients read `ref` (`pointer(object, kind)` in `lib/objects.ts`); the layout library keeps its own `shape` and `image` inputs, which the web fills from `ref`.

**Notes.** Raised as a size-3 smell while building tables (D1201); the owner asked for it to be fixed directly (2026-11-18). A new kind of object, from now on, adds an entry to `OBJECT_KINDS`, a check and a table of definitions, and no field.
