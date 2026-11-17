---
id: D44
title: "Windows and macOS"
status: superseded
applies-to: all
date: 2026-11-02
round: "Web views and the panel (fourth round)"
supersedes: []
superseded-by: [D120]
---

# D44 · Windows and macOS

On **Windows and macOS** the shell uses the **OS title bar and the OS-native menu**, generated from the shared menu and action manifest. The structure File, Edit, Tools, Help is kept. On Linux the GTK shell shows it as header-bar menu buttons.

**Notes.** On macOS, About, Preferences and Quit belong in the application menu, and Edit needs the standard Cut, Copy and Paste items for the shortcuts to reach web content. **Seen on a Mac, 2026-11-07:** the items must also carry the Cocoa action and a shortcut or the keys do nothing (D158).

**Checked against the code, 2026-11-17 (`main` at `6814bac`).** Superseded by D120 as to the structure: seven menus, the same in every app and shell, not File, Edit, Tools and Help. The OS title bar and native menu on Windows and macOS, generated from the shared manifest, stand (D158, D660). Proposed in DOC-03 and confirmed by the code.
