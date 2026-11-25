---
id: D1643
title: "The one menu definition lives in clients/contract, as a package of its own"
status: current
applies-to: all
date: 2026-11-25
round: "Menus architecture (branch `menus`, 2026-11-25)"
supersedes: []
superseded-by: []
---

# D1643 · The one menu definition lives in clients/contract, as a package of its own

**The menu definition (today `clients/linux/src/claudia_shell_gtk/manifest.py`) moves to `clients/contract/`, beside the shell contract, as a small Python package of its own: pure data, no dependencies, Python 3.12 like the Linux client. The Linux client, the Neutralino generator and the web's generator read it from there. What only GTK needs (turning the definition into GTK's menu XML) stays in the Linux client.**

**Notes.** The owner chose this over leaving the file in the Linux client: the definition belongs to every client, and its place should say so. The move comes first, on its own, with no change of behaviour. It reaches the Debian package (`packaging/debian/build-deb.sh` copies the package too), `start-linux-client.sh`, the Linux client's `pyproject.toml`, the generators, `scripts/menu_audit.py`, `scripts/extract_i18n.py` and the CI paths. Details: `notes/menus-architecture.md`.
