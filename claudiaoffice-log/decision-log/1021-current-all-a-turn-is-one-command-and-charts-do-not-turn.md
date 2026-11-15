---
id: D1021
title: "A turn is one command that carries its final values, and charts do not turn"
status: current
applies-to: all
date: 2026-11-15
round: "Rotation in the three apps (branch rotation-ui)"
supersedes: []
superseded-by: []
---

# D1021 · A turn is one command that carries its final values, and charts do not turn

**Turning an object is one `RotateObject` command, made by `ObjectModel.turn_command(id, rotation)`; the command carries the rotation (whole degrees, 0–359, taken modulo 360) and, only when the turn moves the object, its new anchor.** Its inverse carries the old rotation and the old anchor, so one undo puts back both turn and place. A command holds final values only (deterministic replay): whatever has to be decided — here, the nudge of D1022 — is decided when the command is made, never when it is applied. The key `anchor` is written only when set, so logs written before this decision replay unchanged and no schema version moves.

**A chart (kind `diagram`) does not turn** (owner, 2026-11-15). `turn_command` refuses it with "A chart does not turn"; the command itself does not, so an old log that holds one still replays. Clients grey out the Rotate entries for a chart and show no handle.

**Notes.** The servers of creates and computes had `rotate_object` that executed a bare `RotateObject`; they now call `turn_command`, and composes' server gained `rotate_object` (not for the assistant, as every composes edit, D63). Rotation turns about the centre of the frame, clockwise, as D177 says; the anchor is the unturned frame's top left in all three apps.
