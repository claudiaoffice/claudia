---
id: D761
title: "What the Python models own reaches TypeScript through one generated or shared name, and a test refuses a second spelling"
status: current
applies-to: all
date: 2026-11-17
round: "Stabilisation of main, second round (CODE-58, CODE-60, PROC-27)"
supersedes: []
superseded-by: []
---

# D761 · What the Python models own reaches TypeScript through one generated or shared name, and a test refuses a second spelling

Three facts were written in Python and again by hand in the layout library and the web app (CODE-60): the default style
of each app (`'body-text'` eleven times), the kinds of floating object (the layout lacked `rendered`, so the web mapped it
twice), and the geometry of a dot leader (0.3 em in one component, 0.4 em in another, 0.4 em in two layout files).

The rule, in the order to try:

1. **A generated file** when the Python value is a name or a number (`scripts/generate_style_ids.py` writes
   `layout/src/styles.generated.ts`; `tests/test_style_ids_generated.py` fails when it is not what the models say, as
   `generate_keys.py` does for the key table). The web reads it through `@claudia/layout`, which it uses already.
2. **One TypeScript name** when the fact is about drawing and the layout is where it is drawn (`ObjectKind`,
   `leaderCss`, `LEADER_GAP_EM`); the web imports it and does not spell it again.
3. **A test** that refuses the second spelling: `tests/test_object_kinds_agree.py` (the layout's `ObjectKind` equals
   `claudia_core.OBJECT_KINDS`, and no client writes the list out again), the literal check of
   `tests/test_style_ids_generated.py`, and the older `tests/test_one_source_of_headings.py`.

**Not done:** a server flag per style view (built-in, called-out, for a shape's words). It is the cleaner end for the
Format menu's groups (`TextWorkspace.vue`), which still name `quote`, `remark` and `definition`; a test checks they are
built-ins of composes. See CODE-63.
