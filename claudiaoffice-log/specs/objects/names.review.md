# Review of `names.feature` (draft of 2026-11-19, E1.13)

How to answer: "ok" accepts my proposal; anything else replaces it. Scenarios tagged `@pending:e1.13` are decided and
not built; `@needs-decision` ones wait for the questions below. Suggested order: the `@core` scenarios first.

## A. What I found when I read the code (not run in a browser)

| # | What | Size |
|---|---|---|
| N1 | **Name & describe… has no name field.** The dialog behind the menu entry and the object menu is `ObjectDescriptionDialog.vue`, titled "Describe object"; it has a description and a *Decorative* tick, and no name, in all three apps. Reading the code only. | 2 |
| N2 | **The Back chip disappears after three seconds.** It is shown while `pointed.from` is set, and `pointed` is cleared after `POINT_MS` (3000) together with the highlight, so a person who reads the target for a moment can no longer go back. Reading the code only: to be confirmed in a browser. | 3 |
| N3 | **The Back chip lives in the chat form.** With History & Chat folded away there is no way back at all. | 3 |
| N4 | The dialog's own comment still says "Format ▸ Describe Object…", which the menus workbook removed (Edit ▸ Name & describe…). | 3 |

N1 and N2/N3 are covered by this work, as you said; they get failing scenarios first.

## B. Questions (proposal first)

| Q | Question | Proposal |
|---|---|---|
| 1 | Numbering: a paragraph inserted between "Paragraph 3" and "Paragraph 4"? | Gets the first free number (D550), so not "4". Names are stable, never renumbered. |
| 2 | Paragraph split and join? | Split: first part keeps the name, second gets a new one. Join: the survivor keeps its name; undo brings the other back. |
| 3 | **Headings.** Your menus workbook says a heading's name is its title, locked in the dialog. That conflicts with "every paragraph is Paragraph N". | Follow the workbook: a heading is called by its title; two equal titles become "Introduction" and "Introduction (2)" in the namespace, the text is not changed. |
| 4 | Name & describe… on a paragraph, a list, a table, a cell range? (workbook "To decide" #12, marked *discuss*) | One dialog; the description and *Decorative* only for floating objects (pictures, charts, shapes, text boxes). A paragraph, list, table or range gets the name only. |
| 5 | The `#` list with hundreds of generic names? | In-view paragraphs only (D551 already limits the list to the writer's view), each as "Paragraph 12 · first words of the text"; renamed things and headings always; typing filters the whole document. |
| 6 | Docx and odt export? | A bookmark only for a name a person gave, never for a generic one; import reads a bookmark that wraps one paragraph as its name when it fits the rules. |
| 7 | Old documents? | Pre-release: no migration (D308). `name_unnamed` now also names paragraphs, in one step. |
| 8 | What does Back restore? | The position of the view (container and the top visible place in it). A tag jump never moves the caret or the selection, so there is nothing else to restore. |
| 9 | How long does the chip stay? | Until used, or until she types or clicks into the document, or jumps again (not three seconds). |
| 10 | Back with the panel folded away? | **Menu entry (you decide the place):** View ▸ Back where I was, in all three apps, with a key from the free list in `keyboard-shortcuts.md`. I will check it against the workbook's clash column, and in Firefox: Alt+Left is the browser's own Back, so not that. |
| 11 | The Mac clash of Ctrl+Alt+D (workbook #19: Cmd+Option+D hides the Dock) | Out of this work; it is already on your list. |
