---
id: D1431
title: "What objects show and the document keeps (images, shape outlines, charts, containers, tables) is held in one asset store with one set of commands"
status: current
applies-to: all
date: 2026-11-21
round: "Architecture improvements and the glossary words in the code (branch architecture-improvements)"
supersedes: []
superseded-by: []
---

# D1431 · One asset store for what objects show

**An asset is what an object shows that the document keeps once, by id, so that several objects (or a chart tab) can
show it:** an image, a shape's outline, a chart, a container's definition, a table. "Asset" is a word of the code,
not of the glossary; people never see it.

**The five kinds share one store and one set of commands.** `claudia_core/assets.py` holds:

- `AssetKind` — what differs between the kinds, as data: how one is read from plain data (a chart through the app),
  whether it can be changed in place (charts, containers, tables), an extra check (a container's picture must be in
  the document, a table must hold together), who else uses one (an image is also used by a container's picture), and
  how redaction blanks one (a chart, through the app).
- `AssetStore` — one per kind on the object model: define, forget (refused while something uses it), replace, the
  ids of its users, the stored form and its restore.
- `AssetsChanged` — one event; on the wire it keeps the form the four events had (`type` is the kind).
- `DefineAsset`, `UpdateAsset`, `ForgetAsset` — replace the ten command classes `Define`/`Forget`/`Update` of shapes,
  images, diagrams and renderings. Stored command kinds change (`core.DefineShape` → `core.DefineAsset`); claudia is
  pre-release (E1.18), so documents from before are not read.

Tables join the store (registry, users, stored form, restore) but keep their own commands (`table_commands.py`),
since a table is edited box by box.

**Why:** the five copies made every new kind of object about eight edits in one 2500-line file, and the glossary
renames (diagram → chart, rendered → container, D1430) would have had to be made five times over. The clients see no
change from this decision. Moving the naming of things out of `ObjectModel` is left to E1.15/E1.17, which rework names.
