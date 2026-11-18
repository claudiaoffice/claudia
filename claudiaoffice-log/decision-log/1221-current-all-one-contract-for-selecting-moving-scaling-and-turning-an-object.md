---
id: D1221
title: "One contract for selecting, moving, scaling and turning an object, written once and adapted per app"
status: current
applies-to: all
date: 2026-11-18
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1221 · One contract for selecting, moving, scaling and turning an object, written once and adapted per app

**A left press on an object selects it; moving the pointer more than 3 screen pixels moves it, and on release its anchor is repositioned; the handles scale it; the handle above it turns it; a right press selects it and opens the object menu, and nothing below it receives the press.** This is how creates behaves today and is the reference; computes and composes follow it. A gesture is previewed locally and is one command on release (D82), `Esc` during it puts the object back, and every kind of object that can be scaled or turned can be, in every app. An object that keeps an aspect (an image, a shape with `aspect`) shows corner handles only and keeps it, so the server never has to refuse (`_check_visual`).

**The code follows D177.** The gesture (press, threshold, move, handle, turn, release, cancel), the menu list and the frame with its handles are written once in the web client; each app supplies a small host adapter (`ObjectHost`: units of the pointer, where the frame is, its bounds, what a move commits) and nothing else. What the apps release to is their own: creates the slide position, computes the cell under the top-left corner, composes the paragraph and character nearest the drop plus the free offset (D1023).

**Notes.** The owner's request of 2026-11-18, after the new floating-object work left composes' objects and tables unusable and computes passing a right click through to the cells. Design in `notes/object-interaction-contract.md` with the mock-ups `object-interaction-states` and `object-interaction-architecture`. Right press elsewhere is unchanged: each app's own menu, and Shift+right button gives the browser's.
