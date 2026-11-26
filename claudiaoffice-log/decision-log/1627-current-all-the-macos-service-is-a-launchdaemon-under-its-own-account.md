---
id: D1627
title: "The macOS service is a LaunchDaemon under its own hidden account _claudia"
status: current
applies-to: all
date: 2026-11-26
round: "E8.5 macOS installer, part 3: the package (branch `mac-installer`); designed 2026-11-25, built on Linux in CI by the owner's answers of 2026-11-26"
supersedes: []
superseded-by: []
---

# D1627 · The macOS service is a LaunchDaemon under its own hidden account _claudia

The claudia service of a Mac is the LaunchDaemon `de.claudia-office.server` (`/Library/LaunchDaemons`): the runtime's
server on `127.0.0.1:8765` without TLS, its documents in `/Library/Application Support/Claudia/shared/documents`, its
state in `…/shared/state`, its log in `/Library/Logs/Claudia/server.log`, started at every start of the Mac before
anyone logs in and again if it ends (`KeepAlive`). It runs as **`_claudia`**, a hidden account and group the
service's postinstall makes with a free number below 500 (`dscl`), which owns `shared/`. The Mac's administrators may
read its setup code through an inherited ACL on `shared/state/admin` (D1624). The installer writes the service file
`/Library/Application Support/Claudia/service.json`, which only root may write, so every person's apps list it as
"Shared on this computer" (D1622). It mirrors the Windows service (D743).

**Alternatives.** A LaunchAgent per person: no place shared by all. Running as root: more rights than a document server needs.
