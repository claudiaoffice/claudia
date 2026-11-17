---
id: D732
title: "The Windows installer is built with Inno Setup and tested by installing it"
status: current
applies-to: all
date: 2026-11-17
round: "The Windows installer (E8.1; branch `win-installer`)"
supersedes: []
superseded-by: []
---

# D732 · The Windows installer is built with Inno Setup and tested by installing it

**Inno Setup** (`packaging/windows/claudia.iss`) makes one `claudia-office-<version>-windows-x64.exe`: wizard in English and
German (the languages of `po/`), Start menu entries for the three apps, optional desktop icons, per person or for all people
(the person is asked), upgrade over an existing installation (a fixed `AppId`), uninstall that removes what was installed,
stops a running server first and leaves the documents (it says where they are). The Microsoft WebView2 Runtime, which shows
the windows, is installed from Microsoft's bootstrapper where it is missing (Windows 11 and Edge have it; the bootstrapper must
be signed by Microsoft, which the build checks). Open source, free, scripted, and the owner's choice (2026-11-17).

**What the build downloads is pinned by SHA-256** (`packaging/windows/third-party.json`): WinSW. Not pinnable: Microsoft's
bootstrapper (replaced in place by Microsoft; checked for its signature).

**The installer is tested by installing it** (`.github/workflows/windows.yml`, job `test`, on two Windows images): install with
the service, check the files and the Start menu, check the service (running, automatic, LocalService, answers on 8765, passes
`packaging/smoke_server.py`: a document in each of the three apps and their help topics), stop and start it, run the client's
`--version` with a PATH of Windows only, uninstall and check that no service, process or program is left and the documents are
not; then the same with the standard install, with the installed server started on its own and a real window started, which
brings its own server up. The Debian package is tested the same way (`deb.yml`). The window step is allowed to fail the first
time: whether a runner can show a WebView2 window is not known.

**Releases.** A tag `v1.2.3` attaches the installer to the release of the tag (the version is the tag). The Debian workflow
checks that the tag equals `clients/linux/.../_version.py`; the Windows installer takes the tag as its version and checks
nothing else, so a release needs the Linux client's version set to the tag first (open: one version for the suite).

**Notes.** MSI is for later (the owner, 2026-11-17); WiX since 6 asks an Open Source Maintenance Fee for revenue-generating
use, which does not concern an MSI built from an own recipe by a free project, but must be read again then.
