---
id: D1373
title: "The desktop apps hand the setup code of their own server to their own page, in the shell contract's welcome"
status: current
applies-to: all
date: 2026-11-20
round: "SEC-12: the first administrator needs a setup code (branch sec-12-setup-code)"
supersedes: []
superseded-by: []
---

# D1373 · The desktop apps hand the setup code of their own server to their own page, in the shell contract's welcome

**Decided 2026-11-20** (mock-up panel 5).

- The shells already start the desktop server with its state folder (`--state-dir`). At each `welcome` they read
  `admin/setup-code` there and send it as `setup_code` (a new optional field of `welcome`: additive, so contract
  version 1 stays). They read it at each welcome rather than once, because the shared server (D445) may have been
  restarted by another window and have a new code.
- **Only for their own server:** the field is sent only when the window's page comes from the shell's local origin
  (`book.local_origin` / `localOrigin`), never to a server the window was connected to (`connect`).
- The page keeps it as a code "from the app"; when the server accepts it, the setup page shows **no code field at all**:
  the screen is today's optional one with "Skip for now". If it is refused (the server restarted in between), the field
  appears with the sentence of D1371.
- Linux (GTK) and the Neutralino shells (Windows, macOS, one code base since D660) do the same.
