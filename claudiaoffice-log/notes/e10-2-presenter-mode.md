# Presenter mode in creates (E10.2): design, answers and what is still open

Written 2026-11-13. Mock-up: `mockups/presenter-mode.svg` (and `.png`), seven screens A–G. The story today is one line
(E10.2: full-screen mode, minimal transitions, speaker view, the same on web and desktop). D77 left presentation mode
out of the first draft; D917 left room for a notes page in print. The spike for the window and key questions is in
`spikes/e10-2-presenter-window/`.

## Answers of the owner, 2026-11-13

Recorded as D291–D299 (branch `presenter`; D291–D295 confirmed, D296–D299 proposed and `undecided`).

1. **Windows and screens (D296):** write the spike (done, not yet run in the shells; see below).
2. **Notes take Markdown.** The notes field of a slide holds Markdown, not plain text (D293; the subset D298).
3. **Frozen during the show (D292):** the show runs on the revision at its start; the presenter view reports "N changes since
   you started" and offers to update between slides; nothing changes on its own (D72's rule).
4. **Presence and rights (D291):** everyone who can open the document may present; one presence line; no locks.
5. **Keys (D295):** F5 and Shift+F5 with the browser's reload suppressed while the document is open; the key for "with
   presenter view" is settled after the spike. The mock-up's Alt+F5 is a placeholder.

New wish, same day, and the answer that the times live in the document: **a planned time per slide that is simple
to set, and a total that shows how long the whole talk will take** (D294, screen G below).

Defaults proposed earlier and not objected to but not confirmed (D297): the planned
duration is not a session setting any more but the sum of the slide times (see timing); no transitions beyond one
fade, no builds, no hidden slides; the audience view announces slide titles to screen readers; the letterbox is Ink
until templates exist; the docked panel is hidden and the AI is not used while presenting.

## What the design says

- **Starting (A).** A View group at the top of the View menu — Present from start, Present from this slide, Present
  with presenter view — plus one apricot "Present" button at the right end of the bar. Every entry gets a key.
- **Speaker notes (B).** One Markdown field per slide under the canvas, switched with View ▸ Speaker notes. It is in
  the document: a command, undoable, attributed like any other edit, visible in the history. The AI may write it as a
  suggestion (D265). Shown formatted in the presenter view only; never on the slide, never on a slide print page.
- **Audience screen (D).** The slide only, scaled to fit the 1600 × 900 space (D83), on Ink, no chrome, cursor hidden.
  A quiet pill (previous, 3 / 12, next, more) fades in on mouse movement and out after two seconds. Transitions: none,
  or one 150 ms fade; `prefers-reduced-motion` switches it off.
- **Presenter view (C).** Dark Ink surface: current slide, next slide, notes at reading size (Markdown rendered), the
  elapsed time against the planned total ("1:20 behind"), the time on this slide against its plan, the clock, and
  whether the audience window is open.
- **Overview (E).** `G` opens a grid of all slides with each slide's planned time; arrows, Enter, Esc; a number plus
  Enter jumps. Navigation is by slide id (D81), so connected thoughts (E10.11) can later show the chain as a path.
- **In-between states (F).** Blank (`B`), end of presentation, one screen with `P` swapping between audience view and
  presenter view, one presence line while someone presents.
- **Timing (G).** Each slide may carry a planned time, set from the ⏱ chip next to its notes, with `T`, or from the
  slide's context menu: a few chips (1, 2, 3, 5, 10 min), a `m:ss` field, `−`/`+`, Clear. The total is always in view
  (foot of the slide rail, overview, presenter view). Optionally the document has an "Available time" (D299; metadata, D71:
  never required); the total then reads "1:30 left" or "2:10 over". Nothing is enforced.
  *Proposal, not asked for yet (D299):* after the show the presenter view lists planned against actual time per slide, with
  "Use actual times as plan"; the actuals are kept in the browser only until the list is closed and are never written
  to the document unless the person chooses to use them as the plan.

Presenting itself is read-only and local: it takes no locks, writes no command and leaves nothing in the history. The
planned times and notes are document content and are written like any other edit.

## Still open

A. **Markdown subset and fidelity (D298).** Proposal: CommonMark without raw HTML and without images — paragraphs, emphasis,
   strong, lists, headings (shown as bold lines), links, inline code, block quotes — rendered from a parse tree, never
   by inserting HTML. ODP and PPTX notes pages carry text with runs and bullets, not Markdown: the writers map bold,
   italic, lists and headings to them, the readers map them back, and anything else is kept as plain text. A small
   Markdown parser is needed; its licence has to fit the GPL stance, like every component. Both formats' notes pages go
   into the same patch as the notes (project rule).
B. **How the times are stored (D294 settles that they are in the document).** Proposal: a planned time per slide (whole seconds, optional) in the slide model next to
   the notes — a command `SetSlideTime`, state schema 8 with notes — and the optional "Available time" as document
   metadata. ODP and PPTX have no planned-time field for this; PPTX has slide timings for auto-advance, which is
   something else and must not be confused with it, so the times are not exported as timings. They travel in Claudia's
   own format only, and the export dialog says so.
C. **Window and key choices after the spike** (question 1 and 5 above).
D. **Screens A–G** are not yet agreed; no code starts before they are.

## Not in the first version

Pointer or laser, ink on slides, builds, audience Q&A, remote viewers, recording, speaker notes in print (D917 keeps
room for the layout), automatic advance by the planned times.

## The spike (`spikes/e10-2-presenter-window/`)

Reading the code first gave two findings that are independent of any test. The GTK shell switches off
`javascript_can_open_windows_automatically` and loads a new-window request in the same view, so today no second window
is possible on Linux; it needs a `create` handler. The macOS and Windows shell pages show the web app in an `<iframe>`
without `allow="fullscreen"`, and their `nativeAllowList` has neither `window.setFullScreen` nor `window.create`, so
neither the page nor the shell can go fullscreen or open a window today. The spike measures what then works: fullscreen
and a second window in Firefox, in the GTK shell as it is and with the changes, and in the Neutralino shells with and
without the frame attribute; the three ways two windows can talk (BroadcastChannel, `postMessage`, `storage`) and their
round trip; which keys reach the page; the Window Management API; the Screen Wake Lock. The author ran the page in
headless Chrome only: both windows hear each other on all three channels within about a millisecond. Everything else
is for the owner's machines (README of the spike).

## Where it will touch

`SlideCanvas.vue` rendered read-only and scaled (the same renderer as the editor, so charts show live although they
are not printed yet); `SlideWorkspace.vue` for the View entries and the notes field; `SlideModel` for notes and times
(state schema 8) and the wire methods; the ODP and PPTX writers and readers for notes; the three desktop shells for
fullscreen and the second window (a contract message each); gettext entries for every label; an e2e test in Firefox.

## What was built (2026-11-13, branch `presenter`)

The decisions D291–D295 are implemented, in this order and with this result:

- **Model and wire.** `SlideModel` state schema 8: `notes` (Markdown, at most `MAX_NOTES_LENGTH`) and `times` (whole
  seconds 1 to `MAX_SLIDE_SECONDS`, 86 400), commands `SetSlideNotes` and `SetSlideTime` (one step each, with an exact
  inverse), events `slide_notes` and `slide_time`, server methods `set_slide_notes` and `set_slide_time`; `slides`
  answers `seconds` and `has_notes`, `slide` answers `notes` and `seconds`. The AI may write notes, not times.
- **Files.** PPTX: the notes slide of every slide, bold, italic, bullets and numbers as the Markdown subset of D298, also
  from files made by LibreOffice (which puts the notes in a plain text box). ODP: `presentation:notes` with its notes
  frame. Both patch an existing file in place. Features the subset has no counterpart for are flattened and reported
  as losses; planned times are not exported (`planned-time` loss for ODP, which says how many slides had one).
- **Web.** `lib/show.ts` (the show's rules: slide, overview, blank, end, typed number, clock, pace; no DOM, tested in
  Node), `lib/frozen.ts` (the deep copy a show runs on, D292), `lib/show-time.ts` (`2`, `2:30`, `90s`, `1h`),
  `lib/notes-markdown.ts` (notes as lines of spans, never HTML), `lib/present-keys.ts`; components `PresentShow.vue`
  (audience view, presenter view, overview), `SlideView.vue` (one frozen slide), `NotesText.vue`, `SlideNotes.vue`
  (the field under the slide and the ⏱ chip with its popover). The View menu has Present from the first slide, Present
  from this slide and Speaker notes; Edit has Plan the time of this slide…; the tool bar has the apricot Present button
  (also for a viewer: showing writes nothing, D291); every slide tab carries its time and the bar below adds them up
  ("Planned 3:30 · 1 without a time").
- **Desktop shells.** The menu manifest has the same entries and accelerators, so the macOS and Windows menus
  (`src/generated/menu.creates.json`) and the GTK menu show them; the page does the work (kind `page`).
- **Text.** 70 new strings in `po/claudia.pot` with German in `po/de.po`.
- **Tests.** Python: model, server, AI list, PPTX and ODP round trips, real LibreOffice conversions both ways. Web:
  `show`, `frozen`, `show-time`, `notes-markdown`, `present-keys`, session. Browser: `e2e/present.cjs`
  (`npm run e2e:present`; `BROWSER=firefox` for Firefox), which writes notes and times, runs the show with every
  key, and checks that `F5` does not reload.

### Safari on macOS (the owner's run of the spike)

Fullscreen, a second window, three message channels at 1 ms, wake lock: all fine. **Window Management API absent. F5
combinations are system keys on a Mac**, which led to the second chord of D295. Details in D296.

### Not in this round

The second audience window and shell fullscreen (D296, waiting for Firefox, GTK, Neutralino); the presence line while
presenting (it needs the server to take a "presenting" flag with the presence); the Edit-menu time entry in the slide's
context menu; a message in the export dialog that times travel only in Claudia's own format; per-slide timing
against actual (D299, still undecided: the pace shown is the plain schedule difference).
