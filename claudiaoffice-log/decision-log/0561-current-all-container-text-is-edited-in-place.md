---
id: D561
title: "The text of a container is edited in place; clicking out draws it"
status: current
applies-to: all
date: 2026-11-15
round: "Rendered text containers: the screens (branch containers)"
supersedes: []
superseded-by: []
---

# D561 · The text of a container is edited in place; clicking out draws it

**Double-click, Enter or F2 on a container opens its text in a monospace editor named for its type; Ctrl+Enter or clicking elsewhere draws it, Escape leaves the text as it was, and Enter is a new line.** A formula or a diagram has many lines, so Enter must not finish. The container shows its picture when not edited; before there is one it says "Drawing…" politely, and a failure (or a tool the administrator has not set up) is an alert with the tool's lines. The type is always written on the corner, never colour alone. The same two components (`RenderedFace`, `RenderedEditor`) are used by the slide canvas, the sheet and the text.
