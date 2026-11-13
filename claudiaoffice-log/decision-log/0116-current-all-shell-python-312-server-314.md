---
id: D116
title: "The shell runs on the distribution's Python (3.12 or newer, never forced), the server on 3.14"
status: current
applies-to: all
date: 2026-11-03
round: "Native clients (eighteenth round)"
supersedes: []
superseded-by: []
---

# D116 · The shell runs on the distribution's Python (3.12 or newer, never forced), the server on 3.14

**The shell runs on the distribution's Python (3.12 or newer, never forced), the server on 3.14.** The shell is outside the uv workspace and has its own ruff and mypy targets.

**Notes.** Consequence: `claudia-client` needs 3.14 and cannot be imported by the shell, so TLS trust for remote servers is not available to it yet.
