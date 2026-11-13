---
id: D212
title: "Each app exports its own office format through one RPC, `export_office(format)`, and the File menu separates Claudia's own file from a foreign one"
status: current
applies-to: all
date: 2026-11-10
round: "Word, Excel and PowerPoint out of every app, and pictures in a PowerPoint (thirty-seventh round)"
supersedes: []
superseded-by: []
---

# D212 · Each app exports its own office format through one RPC, `export_office(format)`, and the File menu separates Claudia's own file from a foreign one

**Each app exports its own office format through one RPC, `export_office(format)`, and the File menu separates Claudia's own file from a foreign one.** composes answers `"docx"`, computes `"xlsx"`, creates `"pptx"`; anything else is a `bad_request`. The bytes come from the app's own `*_io` converter (`text_to_docx` with `track_suggestions=False`, `workbook_to_xlsx`, `slides_to_pptx`) and are wrapped once, in `claudia_server.office_export`, as `{format, content_type, data}` with `data` base64, because the wire is JSON text frames and has no binary channel (the mirror of `images.py`). Only the document as it stands: no history, no chat, no open suggestions. In the web client **File ▸ Download** is now Claudia's own JSON snapshot (`ExportDialog`, formerly File ▸ Manage ▸ Export…) in all three apps — so D123's disabled Download stubs in computes and creates are gone — and **File ▸ Manage ▸ Export…** opens `ExportFormatDialog`, which offers the app's formats; composes' Markdown is built locally from `state.blocks`, the rest ask the server. `claudia-server` now depends on the three `*_io` packages.

**Notes.** From the owner's local `xlsx-docx-pptx-additive-io` branch, where it was written as "D205"; that number had meanwhile been taken on `main` (chart figures), so it was renumbered when the branch was brought onto `main`. Considered and rejected: a separate HTTP download route next to the WebSocket — a second authenticated channel for one feature, when a base64 answer is a few lines and the files are small.
