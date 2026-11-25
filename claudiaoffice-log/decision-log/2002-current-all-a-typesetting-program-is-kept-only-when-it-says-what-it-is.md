---
id: D2002
title: "A typesetting program is kept in the settings only when it says what it is"
status: current
applies-to: all
date: 2026-11-24
round: "Bug eater, batch 1 (branch batch-1): SEC-16"
supersedes: []
superseded-by: []
---

# D2002 · A typesetting program is kept in the settings only when it says what it is

**Decided 2026-11-24** (batch 1 of the bug eater, approved by the owner; SEC-16).

`PUT /api/admin/settings/typeset` used to store any path, and the server then ran that file for every formula and
picture it typeset. Since SEC-12 an administrator is someone who knew the setup code, but a stolen administrator session
still became "run this file on the server, again and again".

Now a setting that names a program (a path, its folder or a name on the PATH, as before) is kept only after the program,
run once in the typesetter's sandbox with a clean environment and short limits, names itself: `xelatex --version` must
answer with a line that begins `XeTeX`, `pdftocairo -v` with one that begins `pdftocairo version`. Otherwise the answer is
400 with a sentence that names the program and what it should have said, and the earlier setting stays.

**What changes for a person:** a program that is not there yet can no longer be saved ahead of installing it; she installs
LaTeX first, then saves the path. An empty setting is still accepted and means "look on the PATH when needed", and the
page still says whether the programs are found.

**Not built:** showing on the settings page what the program answered. The page shows the server's sentence when a
setting is refused; showing the banner of an accepted program is left for the settings page's next change.
