---
id: D701
title: "New package claudia-file-writer: every file the server writes is written one way"
status: current
applies-to: all
date: 2026-11-16
round: "Code review follow-up: CODE-33 and CODE-34, the client package and how files are written"
supersedes: []
superseded-by: []
---

# D701 · New package claudia-file-writer: every file the server writes is written one way

**A new package, `claudia-file-writer` (`claudia_file_writer`), standard library only, is how a Claudia server writes
a file.** A file is written next to its place and moved there in one step (`write_atomically`, `atomic_file`): private
(0600) from the first byte unless a mode is given, and with `durable=True` on disk, folder included, before the call
returns. The move is retried on Windows (`Replacer`: waits that double from 0.05 s up to 1 s, ten attempts), where
antivirus scanning and indexing hold a file just written; when the last attempt is refused, the error names any file
of this process that still holds the file open. A file named by its contents, such as a web font named by its hash, is
written once (`write_once`): a file already there, or one another writer put there first, is success. Files pinned by a
lock (URL and SHA-256) are fetched with `fetch_pinned`, which refuses any other bytes and writes them readable by all.

Users: the document file and the journal (`claudia_container`, durable), the server's state, certificate and settings
(`claudia_server.state.write_private`, durable), the web fonts (`write_once`), the typeset results, the starter set of
fonts and the hyphenation patterns (both `fetch_pinned`).

**Notes.** The owner's answer of 2026-11-16 to CODE-34, which proposed the package: the name `claudia-file-writer`, and
the pinned download in the same patch. It is not in `claudia-core` because the kernel does no I/O at all (its purity
test forbids `os`, `tempfile` and `open`). The typeset cache writes with `write_atomically`, not `write_once`: a result
is put after a lookup missed, and a garbled file counts as missing, so it must be replaceable. The Linux shell's two
atomic writes (`settings.py`, `desktop_server.py`) stay its own: the shell runs on Python 3.12 without dependencies
(D116, D700), and Linux needs no retry.
