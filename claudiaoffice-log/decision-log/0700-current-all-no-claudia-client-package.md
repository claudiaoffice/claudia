---
id: D700
title: "There is no claudia-client package: each client trusts servers with its own platform's TLS"
status: current
applies-to: all
date: 2026-11-16
round: "Code review follow-up: CODE-33 and CODE-34, the client package and how files are written"
supersedes: []
superseded-by: []
---

# D700 · There is no claudia-client package: each client trusts servers with its own platform's TLS

**`packages/claudia-client` is removed.** It held one module, `TlsPolicy` (SSH-like trust in a self-signed server
certificate, remembered per `host:port` in `known_servers.json`), and no client imported it. Each client decides about
a server's certificate with what its platform has: the web app leaves it to the browser; the Linux shell asks the person
and remembers the certificate per origin in `shell.json` (`claudia_shell_gtk.trust`, `x509.py`, the "Trust this
server?" dialog); the macOS and Windows client checks with Node's TLS and does not ask yet (`certificate_invalid`).

**Notes.** The owner's answer of 2026-11-16 to CODE-33: "let's get rid of claudia-client". The other way was to drop
its unused `claudia-core` dependency, target Python 3.12 and let the Linux shell use it. It was not taken: the two trust
models differ (what is remembered, where, in which fingerprint form, and who does the TLS), so sharing would have meant
rewriting the shell's trust and migrating the pins people have, and the shell would have gained its first dependency
(the `.deb` and the Flatpak). The shell stays without dependencies (D116). A future Python client that connects itself
(a command line, a scripted agent) can bring `TlsPolicy` back from the history (`packages/claudia-client/` before this
decision).
