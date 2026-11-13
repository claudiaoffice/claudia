---
id: D175
title: "New `--danger`/`--danger-dark` tokens are added to the design system,"
status: current
applies-to: all
date: 2026-11-07
round: "Server settings, frontend half (thirtieth round)"
supersedes: []
superseded-by: []
---

# D175 · New `--danger`/`--danger-dark` tokens are added to the design system,

**New `--danger`/`--danger-dark` tokens are added to the design system,** reserved for the settings pages' one or two consequential actions (rotating the access secret) and exposed as a global `.btn.danger` pair.

**Notes.** Distinct from `DeleteDocumentDialog.vue`'s existing scoped `.btn.danger` (which uses `--rose` for an ordinary document delete) — Vue's `<style scoped>` keeps the two from colliding.
