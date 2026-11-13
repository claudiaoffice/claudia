---
id: D171
title: "The \"Manage this server…\" link is always shown, not gated on whether the viewer actually holds admin rights"
status: current
applies-to: all
date: 2026-11-07
round: "Server settings, frontend half (thirtieth round)"
supersedes: []
superseded-by: []
---

# D171 · The "Manage this server…" link is always shown, not gated on whether the viewer actually holds admin rights

**The "Manage this server…" link is always shown, not gated on whether the viewer actually holds admin rights.** The alternative — checking admin status before showing the link — would need the cross-origin fetch D170 forbids; the settings pages' own login is the real gate, and a settings-gear link that merely exists leaks nothing.

**Notes.** Differs from the canvas mock-up's sticky note ("hidden for everyone else"), which assumed a same-origin check was free. Flagged here rather than silently diverging from the agreed design.
