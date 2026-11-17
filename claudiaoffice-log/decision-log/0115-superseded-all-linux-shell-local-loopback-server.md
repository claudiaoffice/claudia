---
id: D115
title: "The Linux shell shows a local server on the loopback address, which serves the frontend itself"
status: superseded
applies-to: all
date: 2026-11-03
round: "Native clients (eighteenth round)"
supersedes: []
superseded-by: [D504]
---

# D115 · The Linux shell shows a local server on the loopback address, which serves the frontend itself

**The Linux shell shows a local server on the loopback address, which serves the frontend itself** (`--host 127.0.0.1 --no-tls --web <frontend>` on a free port), so page and WebSocket share one origin and no `--allow-origin` is needed.

**Notes.** Replaces the custom-scheme plan, which cannot work with the unchanged web app because `OpenDialog.vue` derives the server address from `location.host`. Plain HTTP is acceptable because the socket never leaves the machine. **Side effect:** the port changes every start, so the page's `localStorage` does not survive a restart.

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Superseded by D504 as to the port (every Claudia server is on 8765, so `localStorage` survives a restart) and by D445 as to whose server it is (the desktop apps share one local server). A local server on the loopback address that serves the frontend itself is still how it works. Proposed in DOC-03 and confirmed by the code.
