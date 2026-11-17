---
id: D743
title: "The server can be installed as a Windows service, as an option"
status: current
applies-to: all
date: 2026-11-17
round: "The Windows installer (E8.1; branch `win-installer`)"
supersedes: []
superseded-by: []
---

# D743 · The server can be installed as a Windows service, as an option

**Optional component, off in the standard install**, available where the installation is for all people (administrator
rights). WinSW (MIT, pinned) wraps `claudia-server.exe` as the service `ClaudiaServer` (`service/claudia-service.xml`):
automatic start, restart on failure, runs as `NT AUTHORITY\LocalService` (set with `sc config`, which may write only
`%ProgramData%\Claudia`), listens on `127.0.0.1:8765` without TLS, has its documents and state in `%ProgramData%\Claudia`, logs
rolling in `...\state\service`. No `--exit-when-idle`. The configuration is the person's once installed: an update does not
replace it.

**Consequence the person must know.** The desktop apps use a Claudia server they find on port 8765 (D504), so with the service
running they use *its* documents (`%ProgramData%\Claudia\documents`), not those of their own server
(`%LOCALAPPDATA%\Claudia\documents`). Both stay when the service is removed. That is why it is off by default: it is meant for
a computer that serves documents to others, and for administrators.

**Open.** Listening on the network needs `--host` and a certificate; the service file is the one place and nothing in the
wizard sets it. Whether the apps should refuse a service whose documents they have not been told about is not decided.
