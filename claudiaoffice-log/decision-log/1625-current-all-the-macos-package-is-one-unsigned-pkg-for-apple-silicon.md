---
id: D1625
title: "The macOS package: one unsigned .pkg for Apple Silicon and macOS 14, the apps and an optional service, its server on a relocatable CPython"
status: current
applies-to: all
date: 2026-11-26
round: "E8.5 macOS installer, part 3: the package (branch `mac-installer`); designed 2026-11-25, built on Linux in CI by the owner's answers of 2026-11-26"
supersedes: []
superseded-by: []
---

# D1625 · The macOS package: one unsigned .pkg for Apple Silicon and macOS 14, the apps and an optional service, its server on a relocatable CPython

**`claudia-office-<version>-macos-arm64.pkg`** installs for every person of the Mac: **claudia composes, computes and
creates** in `/Applications`, **uninstall claudia** in `/Applications/Utilities`, and the runtime they share in
`/Library/Application Support/Claudia/runtime` (Node, Python with the server, the client, the web frontend). The
**claudia service** (D1627) is a second part, offered under "Customize" and not chosen unless asked for. A Mac with an
Intel processor or macOS older than 14 is told "claudia needs a Mac with Apple Silicon and macOS 14 or newer." and gets
nothing. The installer is in English and German (title, welcome and licence pages, the parts' names). An update
closes the apps that are open (of every person, as the Windows installer does; the welcome page says so), removes the
old runtime and apps, so no file of an older version stays, and keeps the service running. The Mac's own folders
(`/Applications` and the rest) keep their owners and modes.

**The package is not signed** (that needs Apple's developer membership, which the owner does not take now, 2026-11-25):
macOS asks for "Open Anyway" in Privacy & Security for a downloaded one. Apple Silicon runs no code without a signature,
but an ad-hoc one is enough, and every binary in the package was built on a Mac and carries one (D1629).

**The server is a relocatable CPython 3.14** (python-build-standalone, what uv installs) with the server and its
dependencies installed into it for macOS from the lock file (`uv pip install --python-platform aarch64-apple-darwin
--only-binary :all:`), started by `runtime/server/claudia-server` (`python -I -m claudia_server`): PyInstaller, which
the Windows server uses (D740), cannot build for a Mac on Linux.

**Alternatives.** A signed and notarised package: needs the membership; later. A `.dmg` with a dragged app: no place for
the service and the shared runtime. Intel Macs: the owner chose Apple Silicon only (2026-11-25).
