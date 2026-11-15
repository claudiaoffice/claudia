---
id: D552
title: "A named range is a thing: it can be tagged, and it shares the name space of objects, sheets and slides"
status: current
applies-to: computes
date: 2026-11-15
round: "The dock: names, scrubbing and tags (branch dock)"
supersedes: []
superseded-by: []
---

# D552 · A named range is a thing

The owner asked for named ranges to be things one can tag with `#`, with a simple collision rule: **no object can be
named like a range and no range like an object.**

**What counts.** Named ranges, tables and the results of a SQL query (all are `NamedRange` in the workbook) get a
stable **id** and the kind `range`. They share the one name space of D550 with objects, sheets, chart tabs and slides,
compared the same way (cleaned, case-folded). Ranges among themselves keep their old rule: the same text may be used
in two different scopes (a sheet's own name hides the workbook's).

**Ids.** A new range gets `r` and 8 random hex digits. A range from an old log has none stored; it gets `r` and 8 digits
of a hash of its scope and name, so it has the same id on every replay. A rename keeps the id (so a tag survives it).
A range redefined with `DefineName` keeps the id of the one it replaces.

**Renaming.** A range is renamed only through the Names dialog (`RenameName`), because that also rewrites the formulas
that use the name. `RenameThing` refuses a range with a sentence that says where to go. The `names` request returns each
range's `id`, and the web client lists ranges among the things `#` offers; picking one writes a tag that jumps to the
sheet and selects the range. Edit ▸ Reference in Chat writes a tag for a range when the selection is exactly one.

**Documents are forever.** `DefineName` and `RenameName` go to schema 2, `AddSheet` and `AddChart` to 3, `AddObject` to
5, `RenameThing` to 2; the new flag `legacy_names` (set by the upcasters) says "written before this rule" and skips the
new check on replay. A range already in an old log that clashes with an object is therefore left alone, and is only
held to the rule when it is redefined or renamed. Workbook state schema 13.

**Not decided here.** Whether a range's name should also be refused when a sheet is added whose name equals a range's:
it is (it is a thing like any other), but a legacy range does not block it.
