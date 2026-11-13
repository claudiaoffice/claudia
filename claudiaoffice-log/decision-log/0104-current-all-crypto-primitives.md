---
id: D104
title: "Primitives"
status: current
applies-to: all
date: 2026-11-02
round: "Document container and encryption (seventeenth round)"
supersedes: []
superseded-by: []
---

# D104 · Primitives

**Primitives:** Argon2id (password to key), HKDF-SHA256 (one secret to several keys) and AES-256-GCM (encryption), from the Python `cryptography` package; the file records the algorithm ids so they can be replaced. No home-made constructions.

**Notes.** Argon2id first appears in `cryptography` 44, so the floor is `>=44`; a `>=43` floor is still declared somewhere and allows an install that cannot open a document (CODE-07).
