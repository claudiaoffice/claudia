---
id: D2001
title: "The server's own certificate is not an authority; one made before is replaced"
status: current
applies-to: all
date: 2026-11-24
round: "Bug eater, batch 1 (branch batch-1): SEC-06"
supersedes: []
superseded-by: []
---

# D2001 · The server's own certificate is not an authority; one made before is replaced

**Decided 2026-11-24** (batch 1 of the bug eater, approved by the owner; SEC-06).

The certificate a server makes for itself (`claudia_server/certs.py`) is an end certificate: `BasicConstraints(ca=False)`,
critical, and its key usage no longer includes signing certificates. Before, it was an authority (`ca=True,
path_length=0`, `key_cert_sign`), so a person who installed it in her system's trust store (which "trust this
certificate" instructions invite) trusted whoever stole the key file to sign a certificate for *any* site.

Nothing needs it to be an authority: the Linux shell pins the certificate's SHA-256 fingerprint (`trust.py`) and does not
build a chain, and a client that is given exactly this certificate as its only trusted one (OpenSSL 3, Python's `ssl`)
accepts a directly trusted self-signed end certificate. A test checks both: a certificate for another name signed with
the server's key is refused by a verifier that trusts the server's certificate, and a TLS client that trusts exactly the
server's certificate connects.

**A certificate of ours made before this decision is replaced** at the next start, like an expiring one. Its
fingerprint changes once, so a client that pinned the old one asks again whether to trust the server (the same prompt as
after a renewal). A certificate the administrator gives with `--tls-cert` is never touched.

**Not chosen:** a critical `NameConstraints` extension limited to the certificate's own names. It keeps an authority
that nothing needs, and not every TLS library honours name constraints on a root.
