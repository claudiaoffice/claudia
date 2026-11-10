---
id: D245
title: "Trusting a server's certificate: one pinned certificate per origin"
status: undecided
applies-to: all
date: 2026-11-10
round: "E5.8 Linux client: three apps, other servers, HTTPS"
supersedes: []
superseded-by: []
---

# D245 · Trusting a server's certificate: one pinned certificate per origin

**Proposed: a certificate that no authority vouches for can be trusted by the person, as the SHA-256 pin of that one certificate for that one origin; a different certificate at the same origin is asked about again; an expired or not-yet-valid certificate is never offered.**

**Notes.** Proposed with the mock-up `notes/mockups/connect-and-trust.svg` (dialogs A and B, messages 1–6, order of checks). The owner agreed that the dialog is wanted and must be mocked first; the mock-up itself is not agreed yet, so the GTK dialog is not built and nothing is trusted unasked. Built so far: `x509.py` (reads the facts shown), `trust.py` (pins in `shell.json`), `connection.check` (offers `NeedsTrust`), `WebPage` (accepts exactly the pinned certificate with `NetworkSession.allow_tls_certificate_for_host`, only for `UNKNOWN_CA` and `BAD_IDENTITY`). Deviation from the mock-up's panel D: whether the server is a Claudia server of the right app is decided **before** the person is asked about the certificate, so nobody is asked about a server they could not use. Open: removing a trusted certificate (proposed as "Remove" on a server in the list).
