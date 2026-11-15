---
id: D1024
title: "Turning by hand: a handle on the object, Format ▸ Rotate and three keys"
status: current
applies-to: all
date: 2026-11-15
round: "Rotation in the three apps (branch rotation-ui)"
supersedes: []
superseded-by: []
---

# D1024 · Turning by hand: a handle on the object, Format ▸ Rotate and three keys

**A held object shows a round handle on a stem above it. Dragging it turns the object about its centre; the angle shows in a chip (0–359, whole degrees); nothing reaches the server until the pointer is released (D82), then one command and one history entry.** Shift snaps to 15° steps; within 3° of 0°, 90°, 180° or 270° the object snaps upright; Alt switches snapping off. Escape during the drag puts the object back. The visible handle is 19 px, its hit area 32 px. It can be focused, has `role="slider"` and takes the arrow keys (±1°, Shift ±15°), and a live region announces the angle (BITV).

**Format ▸ Rotate**, in this order and in every app and every client (shell menus included):

| Entry | Key |
|---|---|
| Rotate Right 90° | Ctrl+Alt+. |
| Rotate Left 90° | Ctrl+Alt+, |
| Rotate By… | Ctrl+Alt+Shift+Z |

The same three entries are in the object's context menu. All three are greyed for a chart (D1021), when the document is only to be looked at, and when nothing is held. **Rotate By…** is a popover beside the object with an angle field, a dial, the quick buttons −15°, +15°, 90°, 180°, 270° and Upright, and Done and Cancel; everything previews, Esc puts it back, Done sends one command.

**Notes.** *Rotate By… was first drawn with Ctrl+Alt+Z, and the owner said to keep it (2026-11-15). That key is Replay History's in all three apps, which the mock-up note had missed* — two entries must not share a chord in one app, so Rotate By… takes Ctrl+Alt+**Shift**+Z, the nearest free chord. Ctrl+Alt+R is Random Generator's; E, M and Q are AltGr characters on a German keyboard; Ctrl+Alt+T and L are taken by Linux desktops. German: Drehen, Nach rechts drehen (90°), Nach links drehen (90°), Drehen um…, Winkel, Aufrecht.

**Where it is built (2026-11-15).** The handle, the popover, the context menu and the keys are built for creates on the web. Format ▸ Rotate is in the shared manifest for creates only — the Linux, macOS and Windows shells get it from there — and a test keeps it out of composes and computes until those two draw a turned object (E9.29, E6.17). Esc during the drag, and Esc in the popover, put the angle back. The Rotate keys are matched by the physical key (`code`) as well as the character, because `.` and `,` need different modifiers on a German layout. Entries are spelled "Ctrl+Shift+Alt+Z" where a client shows the chord as text.
