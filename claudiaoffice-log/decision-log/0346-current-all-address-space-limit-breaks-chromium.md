---
id: D346
title: "An address-space limit cannot be applied to Chromium-based tools"
status: current
applies-to: all
date: 2026-11-13
round: "Rendered text containers (branch containers)"
supersedes: []
superseded-by: []
---

# D346 · An address-space limit cannot be applied to Chromium-based tools

**`Limits.address_space=False` lets a plugin ask for no `RLIMIT_AS`; time, CPU, file size, open files and the job-folder watchdog still apply.** V8 reserves large virtual ranges, so Mermaid's browser cannot start under an address-space limit.

**Notes.** A manifest asks for it by name and the administrator's policy can still refuse. Found with the real tool; a test runs it. A second finding: Chromium needs a socket path under 107 characters, so the job folder has a short path (`MAX_JOB_PATH`) or falls back to the system temp folder.
