---
id: D520
title: "Every dialog and the search panel can be moved: drag the title bar, or Alt+arrow keys"
status: current
applies-to: all
date: 2026-11-15
round: "The search panel and movable dialogs (branch `search-ui`)"
supersedes: []
superseded-by: []
---

# D520 · Every dialog and the search panel can be moved: drag the title bar, or Alt+arrow keys

**Decision.** A dialog (`Modal.vue`, so every dialog of the three apps: Edit styles, Names, Export, Random numbers, …) and the search panel (D282) have a title bar with a grip. Dragging the bar moves the box; **Alt+arrow keys** move it from the keyboard, **Alt+Shift+arrow keys** in bigger steps (20 and 100 px). The keys are left alone while the cursor is in a text field, where Alt (Option on a Mac) and the arrows already move by word. A box cannot be lost: it stays inside the window, and at least a strip of its title bar stays reachable even when the window is smaller than the box. The position is remembered per dialog while the page is open and forgotten on reload; nothing is saved in the document or sent to the server. When the window shrinks the box is brought back in. A drag that ends over the backdrop does not close the dialog, and Esc still closes it (D128).

**Notes.** Reported by the owner on 2026-11-15, who believed moving had been started somewhere; neither the code nor this log had it, so it is built here, once, for all of them. The offset is applied to the box's own insets (`--dx`, `--dy`), not as a CSS transform: a transform makes the box the containing block of the fixed-position popovers inside it (the "Look in" list, the ⋯ menu) and they would open in the wrong place. Rejected: moving by the whole body of the dialog (it would fight with every field in it) and remembering positions across reloads (a position that was right on one screen is wrong on another). The desktop shells frame the web page, so they need nothing. Code: `web/app/lib/dragging.ts` (where a box may go; tested without a browser) and `lib/use-draggable.ts` (the pointer and key wiring).
