---
id: D133
title: "The gate never reports \"clean\" over a skipped check"
status: current
applies-to: all
date: 2026-11-06
round: "Quality gate truthfulness (twentieth round)"
supersedes: []
superseded-by: []
---

# D133 · The gate never reports "clean" over a skipped check

**The gate never reports "clean" over a skipped check**, and a `--ci` flag turns an unlisted skip into a failure. `check_debt.py`'s `verdict()` prints `clean except skipped: …` whenever anything skipped, even under `--ci` with the skip allow-listed — an allowed skip still must be named, never folded silently into "clean." CI now calls `check_debt.py --ci`, explicitly allow-listing the three checks the Python job's own OS/toolchain cannot run (`web tests`, `web types`, `linux client tests`), which the separate `web` and `linux-client` jobs cover for real. `ruff format --check .` joins the gate as its own named check (CODE-08). Three new repo-scanning tests close the rest: every `D<number>` cited in source resolves to exactly one row in this log (DOC-01); no `.rej` or `.orig` file is ever tracked (CODE-07); and a note under `claudiaoffice-log/` may say "built" about a path only if that path is actually in the tree (PROC-03) — the guard `e4-e6-formulas-notes.md`'s own false claim should have tripped.

**Notes.** Fixes PROC-02 (the gate's false "clean"), DOC-01 (D70–D82/D97–D99 each allocated twice across `claudia-container`/`claudia-server`, resolved by this log's D100–D119 renumbering — citations in source updated to match), CODE-07 (`uv.lock.rej` deleted, lock regenerated, `cryptography` floor corrected `>=43`→`>=44`), CODE-08 (`ruff format --check .` added to the gate). PROC-03's underlying feature (point-and-click cell references, E6.3) was already rebuilt and committed by the owner before this review; this round added only the guard and the note correction.
