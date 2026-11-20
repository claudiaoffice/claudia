# Stale tests, the caret at the edges of a text, dragging objects to another paragraph (D1350–D1352, branch `fix-stale-tests-caret-drag`)

Specs: `specs/composes/caret.feature`, `specs/composes/object-anchor.feature`. Mock:
`notes/mockups/composes-object-anchor-drag.svg`.

## The stale tests, and the two bugs two of them had found

| Test | What it was | What was done |
|---|---|---|
| `tests/e2e/test_things_have_names.py` | stale: renamed a heading, which D1311 no longer allows | a heading is shown to follow its words and to refuse a rename; the rename is checked on an ordinary paragraph |
| `web/e2e/keys.cjs` | stale: the View menu before View ▸ Back where I was (D1319) | the entry is in the expected list |
| `web/e2e/describe.cjs` | stale: Format ▸ Describe Object…, which became Name & describe… (D1317) | the new entry |
| `web/e2e/dock-text.cjs` | **a bug**: a paragraph made a heading was offered in the `#` list as "Paragraph 1" until a reload | `TextModel.settle` tells the clients the name of a heading when it changes (`ThingRenamed`): a paragraph becoming a heading, a heading retyped, a heading becoming a paragraph again. The clients already took `thing_renamed`. The server had the right name (`name_thing`); only nobody told the page. |
| `web/e2e/grid-a11y.cjs` | **a bug**: the line that announces a turn (`role=status`, D1230) was inside the computes grid, where only rows may be | the line is teleported to the body |

## The caret at the edges (D1350)

`TextEditor.keepsCaretInText`: Up on the first line of the text puts the caret at its start, Down on the last line at its
end, Shift extends the selection; the browser does not get these keys. In Firefox the browser moved the caret out of the
first paragraph into the editing area, drawn above the text (the owner's report); Chromium does not, so the scenario
passes there with and without the fix, and is tagged `@firefox`.

**What failed in Chromium, and was fixed too.** Words just typed are drawn over the paragraph until they are sent (on a
word end, or 700 ms later). The paragraph does not have them yet, so in it "before them" and "after them" are one place.
Home right after typing put the caret in front of them on the page, but the session saw no move, and once they were sent
the caret was behind them again: "Start" came out after "First". Now the editor tells the session when the caret is
inside the unsent words (`TextSession.caretInUnsent(index)`), and the session sends them and puts the caret there.

## Dragging to another paragraph (D1351, D1352)

**Kernel.** `ObjectModel.objects_change_container` (composes only), `rehang_object` (out of the old stack, on top of the
new one, or at `at`), `place_regions` (composes: the character dropped on). `MoveObject` across containers emits the old
paragraph's stack (no `removed`, so the page keeps the object selected) and the object for the new one; its inverse
carries `at`, so undo puts it back at its place in the old stack. A move within its paragraph is as before.

**Page.** `TextContainers` draws the anchor mark for the selected object (`lib/anchor-mark.ts`): at the place it hangs,
and, while it is moved (not while it is resized), at the place a drop would take (the same `placeAt` as the commit),
with the old place faint and a label (`Paragraph 3 · after “allotment”`, `· in “…”` inside a word, `· at its start`).
The selected object is described for screen readers ("Hangs from …", `aria-describedby`). The table's name tab used the
same `move_object` and works now too.

## Assumptions

- The anchor shown is the place the layout hangs the object from (`spotOf`), which for words that go above and below an
  object can be at the top of the paragraph rather than in the line the words were moved to.
- The label names a paragraph by its name, or "Paragraph n" by its position when it has none.
- A selection someone holds on an object still names the paragraph it was in after the object moved; the same is true
  where text edits move objects between paragraphs, and was left as it is.

## What could not be run

- Firefox (no Firefox here: Ubuntu has it only as a snap, and Playwright's own cannot be downloaded); the `@firefox`
  scenarios ran in Chromium only.
- The two-person scenario of `object-anchor.feature` skips: sharing a document with a second person is not automated
  in the step code yet.
- `web/e2e/objects.cjs` still fails on the three app bugs reported on 2026-11-20 (left out of this batch).
- The GTK, Windows and macOS shells were not started; they show the same web app.
