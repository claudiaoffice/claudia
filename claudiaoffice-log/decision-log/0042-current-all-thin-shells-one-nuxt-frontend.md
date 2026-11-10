---
id: D42
title: "thin shells around one shell-agnostic Nuxt frontend"
status: current
applies-to: all
date: 2026-11-02
round: "Web views and the panel (fourth round)"
supersedes: []
superseded-by: []
---

# D42 · thin shells around one shell-agnostic Nuxt frontend

The desktop clients are **thin shells around one shell-agnostic Nuxt frontend**. Everything inside the window is web content. **Linux: GTK 4 with libadwaita and WebKitGTK 6.0. Windows and macOS: a web shell around the system web view; Neutralino is the candidate.** A small **shell contract** (a JSON bridge) defines what a shell offers.

**Notes.** Supersedes the plan of a GTK client on all three OSes and the embedding part of D41. Risks: Neutralino's maturity, Wayland, input methods and accessibility are **not verified**; the adapter must stay thin so Tauri or pywebview can replace it. **Evidence, 2026-11-07:** Neutralino 6.8.0 was run on macOS and Windows 11 and passed the automatic checks (D156–D159, `notes/e0-3-neutralino-windows-macos.md`); maturity, Wayland, screen readers and a clean Windows 10 are still not verified.
