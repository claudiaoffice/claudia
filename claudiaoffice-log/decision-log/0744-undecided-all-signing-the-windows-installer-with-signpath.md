---
id: D744
title: "Signing the Windows installer with SignPath"
status: undecided
applies-to: all
date: 2026-11-17
round: "The Windows installer (E8.1; branch `win-installer`)"
supersedes: []
superseded-by: []
---

# D744 · Signing the Windows installer with SignPath

**Proposal, not decided: SignPath Foundation's free certificate for open source.** The workflow has the whole path in and
switched off: with the repository variable `SIGNPATH_ORGANIZATION_ID` set, the unsigned installer is uploaded, SignPath signs
it (`signpath/github-action-submit-signing-request`), and the signed file is the artifact the tests install and the release
attaches. Without it the installer is unsigned, and Windows' SmartScreen warns on download.

The owner wants to read up first (2026-11-17); `packaging/windows/README.md`, "Signing", lists what has to be done and what
SignPath asks of a project. Open for the decision: whether the project meets the Foundation's conditions (an OSI licence; the
suite's licences are chosen per component, D14), the required signing policy and README credit, who approves a release, and
that the certificate names SignPath Foundation as the publisher.

**Notes.** Only the installer is signed; the programs inside (`claudia-server.exe`, the Neutralino binaries, `node.exe`) are
not, which antivirus heuristics sometimes mind. The uninstaller is not either. Follow-ups once an account exists.
