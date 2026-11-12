---
id: D911
title: "Variable fonts are used as they are: weight from the wght axis, optical size from the font size"
status: current
applies-to: all
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D911 · Variable fonts are used as they are: weight from the wght axis, optical size from the font size

**A variable font is laid out at the weight a style asks for on its `wght` axis (clamped to the axis' range) and at its `opsz` axis set to the font size in points (clamped); every other axis stays at its default.** The axis values are whole numbers and part of the face's identity (`<sha256>@opsz=12,wght=500`), of every display list and of the PDF font's name; the PDF embeds a static instance made by HarfBuzz's subsetter. A static family is matched by the CSS weight rules (nearest weight, lighter first below 400, heavier first above 500).

**Notes.** The starter set's Inter, Fraunces and JetBrains Mono are variable fonts (google/fonts ships them so); with this they need no static copies. Optical size in points follows typographic practice; browsers use CSS pixels for `font-optical-sizing: auto`, which is why the preview sets the variations explicitly.
