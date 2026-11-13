---
id: D903
title: "HarfBuzz as WebAssembly shapes text and subsets fonts; its build is pinned by hash and named in every layout"
status: current
applies-to: all
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D903 · HarfBuzz as WebAssembly shapes text and subsets fonts; its build is pinned by hash and named in every layout

**Text is shaped by HarfBuzz compiled to WebAssembly (the `.wasm` files of harfbuzzjs 1.6.4, pinned by SHA-256 in `layout/src/fonts/harfbuzz.ts`), and fonts are subset and instanced for the PDF by HarfBuzz's subsetter from the same release.** The library talks to the two files directly, with bindings of its own, so that the bytes it runs are exactly the ones it checked; the build's id (`harfbuzzjs-1.6.4+6eeed8e1`) is part of every display list and every cache key, so a layout made with another build is never taken for this one. fontkit is not used.

**Notes.** The spike started with fontkit and found it laid out two words of the sample (`567,89`, `0,125` in Inter) 1.2–1.5 pt narrower than Chrome and Firefox, because it applied a kerning pair at twice HarfBuzz's strength; with HarfBuzz the browsers' own rendering agreed with the layout to 0.06 pt (Chrome), 0.04 (Firefox) and 0.01 (Safari, which shapes with CoreText). fontkit also could not subset WOFF2 and called `Math.log` in its subsetter. HarfBuzz's subsetter keeps glyph ids (so a PDF needs no remapping) and pins variation axes, which is what makes variable fonts printable (D911). The two files are copied into the web app by `npm run build` (`layout/scripts/copy-wasm.mjs`, which checks the hashes) and checked again by the page before use (D908).
