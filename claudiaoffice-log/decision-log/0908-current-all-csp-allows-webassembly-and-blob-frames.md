---
id: D908
title: "The web app may compile WebAssembly and show a PDF it made in a frame"
status: current
applies-to: all
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D908 · The web app may compile WebAssembly and show a PDF it made in a frame

**The Content-Security-Policy of every page allows `'wasm-unsafe-eval'` in `script-src` and has `frame-src 'self' blob:`.** The first lets the page compile the HarfBuzz WebAssembly it fetched from its own server (D903) and allows no `eval()` of JavaScript, which only `'unsafe-eval'` would; the second lets the print preview hand the PDF it made to the browser's print dialog in a frame (D906).

**Notes.** Extends SEC-13's policy (`claudia_server.security_headers`). Nothing else changes: scripts still come only from the server and the start page's inline scripts by hash, `object-src 'none'` stays.
