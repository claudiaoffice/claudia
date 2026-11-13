---
id: D173
title: "The AI-model and typesetting settings pages omit every mock-up control with no backing field in the real settings API"
status: current
applies-to: all
date: 2026-11-07
round: "Server settings, frontend half (thirtieth round)"
supersedes: []
superseded-by: []
---

# D173 · The AI-model and typesetting settings pages omit every mock-up control with no backing field in the real settings API

**The AI-model and typesetting settings pages omit every mock-up control with no backing field in the real settings API** — an engine selector and a "remote model" toggle (`AiSettings` has only `model_dir`, `device`, `max_tokens`, `timeout`); `kpsewhich`/`biber` diagnostic rows and a file-browse button (`TypesetSettings` covers only `xelatex`/`pdftocairo`, and there is no file-browse integration). Typesetting's two paths are plain editable text inputs instead.

**Notes.** Building the omitted controls would have produced UI that looks functional but does nothing — judged worse than a visibly smaller page. Revisit once E3.10's engine work (remote model, biber) lands.
