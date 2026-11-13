# Implementation notes: presenter mode in creates (E10.2)

Written 2026-11-13, branch `presenter`. The design and the answers are in `notes/e10-2-presenter-mode.md`; the decisions are
D291–D299. This file keeps what the code does not say.

## Things that were not obvious

- **Frozen means a JSON copy.** The session's state is reactive; a reactive object is a view of the live one, so
  `freeze()` round-trips through JSON. Pictures are copied too (they are data URLs in the state), which is the cost of a
  show that cannot change under the audience.
- **The show hears every key first.** `PresentShow.vue` listens in the capture phase on `window` and calls
  `stopImmediatePropagation()`, otherwise the workspace's shortcuts (Undo, Delete) would act on the document under the
  show. F5 is cancelled even when the show has no use for it.
- **Class names.** The root element of the show must not carry the class of the view it is showing (`presenter`) — the
  inner element has the same name and the styles of both applied to the root. They are `view-audience` and
  `view-presenter` now.
- **Enter and blur are one change.** The planned-time field commits on Enter and again on blur; without a memory of
  what was last sent that wrote two steps into the history. `SlideNotes.vue` remembers it until the document says
  something else.
- **`[role=tab]` is not unique.** The side panel has tabs too; the slide tabs are `[aria-label=slides] [role=tab]`.
- **Orphaned servers.** `scripts/start.py` leaves its server child running when it is killed; a stale server on the port
  serves the old build with the old Content-Security-Policy hashes, and the page stays empty with "Executing inline
  script violates…". Kill `claudia_server` too before restarting the e2e server.
- **Notes in files.** LibreOffice writes a notes page's text into a plain text box, not a `body` placeholder, so the PPTX
  reader finds the notes frame by its placeholder and falls back to the first text frame that is not a slide image or
  slide number (`_notes_frame`).

## Keys

See D295. The F5 chords are the habit; the Ctrl+Alt letters are the ones that reach a page on every system. A chord that
is a letter is matched by `code`, not by `key`: Option+P types a different character on a Mac. Ctrl+Alt+T would have been
natural for the time and is a terminal on GNOME, hence Ctrl+Alt+D.

## Known limits

- F5 and the letter chords are not taken while the focus is in a field, except F5 in the notes field (which the field
  forwards itself): the window's key handler leaves text fields alone, so Ctrl+Alt+P typed in the notes field does
  nothing.
- Pace is the plain difference to the schedule of the planned times (D299 is undecided); a slide without a time
  contributes nothing.
- `requestFullscreen` is asked for when the show opens and refused silently where the browser or a shell frame does not
  allow it; the show then fills the window.
- The wake lock is released when the show ends; a browser that has none is not told.
