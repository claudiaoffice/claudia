---
id: D562
title: "A complete fenced block (```latex … ```) of a type the server makes becomes a container"
status: current
applies-to: all
date: 2026-11-15
round: "Rendered text containers: the screens (branch containers)"
supersedes: []
superseded-by: []
---

# D562 · A complete fenced block (```latex … ```) of a type the server makes becomes a container

**In creates, when a text box is finished and its words are exactly one fenced block, the box becomes a container of that type in the same place and size; in composes, pasting such a block makes a container at the caret.** Only a type the server can make is taken; any other fence stays text. The conversion is two steps in the history (container added, box removed), so undo brings the text back. Typing the closing fence in composes is not converted yet (the paragraphs are written one request at a time); the paste path is the first step. Computes has no text object to convert.

**Assumption.** The owner asked "like in markdown" and did not answer which fence; backticks (three or more) were taken.
