---
id: D902
title: "`@claudia/layout` is a top-level TypeScript package, pure ES2022, made of parts the three apps share"
status: current
applies-to: all
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D902 · `@claudia/layout` is a top-level TypeScript package, pure ES2022, made of parts the three apps share

**The layout library lives in `layout/` at the top of the repository as the npm package `@claudia/layout`, written in plain ES2022 with no DOM, no Node API and no clock** (its compiler settings load neither type library, so using one does not compile). Its parts are separate modules with their own interfaces, so that computes and creates take what they need: *fonts and shaping* (`fonts/`), *paragraph to lines* (`text/paragraph`), *box clipping* (`text/box`), *flow pagination* (`flow/`), the *display list* (`display/`), the *PDF writer* (`pdf/`) and image decoders (`image/`). What is particular to one app is an adapter beside them (`apps/composes.ts`: a text as the server sends it, to pages). The caller loads every byte (fonts, WebAssembly, images) and checks its hash with its own platform; the library only computes. The web app links it as `file:../layout`.

**Notes.** Not under `packages/`, because that folder is the uv workspace and every member there must be a Python package. Tests run with vitest and read every PDF back with pdf.js, an independent reader; TypeDoc generates the API documentation from the source (`npm run docs`). The quality gate has two checks of its own (`layout types`, `layout tests`), and CI a `layout` job. Grid pagination (computes) and slide pages (creates) are the next parts; they reuse fonts, paragraphs, boxes, the display list and the PDF writer unchanged.
