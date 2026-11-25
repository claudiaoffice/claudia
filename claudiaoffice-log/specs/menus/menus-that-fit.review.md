# Review of `menus-that-fit.feature` (draft of 2026-11-25, E5.23 and E5.24)

How to answer: "ok" accepts my proposal; anything else replaces it. All scenarios are tagged `@pending:` with their
story: they are decided (D1600–D1648) and not built, so they fail until they are. `@core` is my proposal for what runs
on every delivery.

## A. What I found when I wrote the scenarios

| # | What | Size |
|---|---|---|
| M1 | **A key of a greyed entry says nothing today.** `menuShortcuts` (`web/app/lib/shortcuts.ts`) skips a disabled entry, so its key falls through to the browser. D1604 wants a notice. This is covered by the work. Reading the code only. | 3 |

## B. Questions (proposal first)

| Q | Question | Proposal | Answer |
|---|---|---|---|
| 1 | Where do menu specs live? | A new folder `specs/menus/`, because the menus are alike in all three apps and in every client. I added it to the README's layout table. | |
| 2 | **The words of a notice.** A condition such as "role: owner" covers many entries (Share…, Manage ▸ …). Should a notice be one sentence per condition, or per entry? | One sentence per condition, such as "Only an owner can do this." The definition may give an entry its own sentence where it reads much better: Copy (D1640, "Only editors and owners can copy from this document.") and Share… ("Only an owner can share this document."). "role: editor or owner" keeps today's "You can only look at this document." | |
| 3 | Which scenarios are `@core`? | The 11 tagged so: the menu titles, a viewer's empty Insert, Insert for the owner, Edit with and without a selection, a viewer's empty context menu, the paragraph and pivot table context menus, the key that says why, a viewer's Ctrl+C, the Shortcuts dialog, and the trial switched to grey. | |
| 4 | Copy through the browser's own menu cannot be driven from a test: Playwright cannot open that menu. | The step makes the same copy the browser's Copy makes, of the current selection, and checks the clipboard. Dragging out is driven for real. | |
| 5 | Reading the clipboard in Firefox asks the person ("Paste" prompt). | The steps never read it directly. They put words on it by copying from a field, and check it by pasting into a field, which needs no prompt. | |
| 6 | `@desktop`: which scenarios also go through the GTK client later? | Only the menu-bar ones (titles, a viewer's Insert), since the shells only draw the menu bar (D1645). Context menus and keys are the page's, so they are the same everywhere. | |
