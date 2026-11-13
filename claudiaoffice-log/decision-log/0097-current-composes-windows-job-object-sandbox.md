---
id: D97
title: "The sandbox works on Windows: a Job Object replaces the refusal"
status: current
applies-to: composes
date: 2026-11-03
round: "Fonts and typesetting services (sixteenth round)"
supersedes: []
superseded-by: []
---

# D97 · The sandbox works on Windows: a Job Object replaces the refusal

**The sandbox works on Windows: a Job Object replaces the refusal.** Every process is put into a Job Object with memory, CPU-time and process limits and kill-on-close, started with its own small environment. A watchdog also enforces a total output size and entry count on every system.

**Notes.** *Reverses the refusal in D90/D96.* **Written from the documentation and never run on Windows**; the first real run is the Windows CI job. A small gap exists between starting the process and putting it into the job. macOS has no address-space limit.
