# Printing slides, and one print preview for both apps (E10.18; D917, D918)

Branch `layouting`, 2026-11-13, on top of the hyphenation and SVG round (`e9-hyphenation-and-svg.md`). The owner's
ask: File ▸ Print in creates, with everything it needs, reusing what composes has, and the printing UI "as consistent
as possible" across the two apps. Four questions were asked first; the owner took every recommended answer: the
print settings live in the document (a command in the history), slides plus handouts (2, 3 with lines, 4, 6, 9), a
slide-sized page by default, and a language shared with composes. The design was again left to Claude; it is recorded
as screenshots: `mockups/print-preview-creates-slides.png`, `…-handouts-6.png`, `…-handouts-3.png`.

## What moved where

| Before | Now | Why |
|---|---|---|
| `claudia_composes.page` (`PageSetup`, `PAPERS`) | `claudia_core.page`, re-exported by composes | creates sets up a page the same way |
| `claudia_composes.language`, `composes.SetLanguage` | `claudia_core.language`, `core.SetLanguage` | one command, one event, one wire method pair for every app |
| composes' `language`/`set_language` in `claudia_server.composes` | `claudia_server.printing.add_language_methods` | both apps' tables call it |
| composes' object drawing in `layout/src/apps/composes.ts` | `layout/src/apps/objects.ts` (`drawObject`, `Styles`, `objectFonts`, `pageNumberItems`) | slides are made of the same objects |
| `PrintPreview.vue` reading a `TextSession` | `PrintPreview.vue` reading a `PrintSource` (`lib/print/source.ts`) | one component, one bar |
| Ctrl+P, the printing flag, the creator's language in `TextWorkspace.vue` | `lib/print/use-print.ts` (`usePrint`, `useCreatorLanguage`) | the same in `SlideWorkspace.vue` |

Logs that wrote `composes.SetLanguage` keep replaying: composes registers an alias command under that kind
(`_SetLanguageAsFirstWritten`; the compatibility test rewrites a log's kind and replays it).

## The creates side

- `claudia_creates.printing.PrintSetup(layout, page)`, `SetPrintSetup`, event `print_setup`; `SlideModel` state
  schema 7 adds `print_setup` and `language` and falls back to the defaults for older states.
- Server: `print_setup`, `set_print_setup(setup)` (the assistant cannot change it: `people_only`, D63), `language`,
  `set_language`.
- `layout/src/apps/creates.ts`, `layoutSlides(doc, fonts, resolver, {hyphenator})`: a slide (1600 × 900 px) is drawn
  once at 1200 × 675 pt and placed through a group `matrix` (scale in millionths) with the slide rectangle as clip.
  Grid per layout and orientation: `gridOf`. With 3 per page the slide takes 55 % of the width (portrait) or half
  the height (landscape) and the rest is ruled every 8 mm (400 mpt lines). A thin grey frame (500 mpt) unless the
  slide fills the page edge to edge (slide paper, no margins: scale exactly 800000). Page numbers keep a band of
  8 mm when the bottom margin is smaller (`PAGE_NUMBER_BAND`).

## Consistency choices (D918)

- Same bar, same order, same `data-testid`s; creates adds Layout in front. The e2e test asserts the order.
- Same status line, extended: "7 slides on 2 pages · A4 portrait".
- Paper list: creates lists `Slide size` first; composes does not list it. Margins: creates adds None.
- Choices that belong together are made together, one step each: a handout layout on the slide paper → A4 portrait,
  narrow margins; Slides → landscape; the slide paper → landscape, no margins.
- Drawn the same: shape labels inset 8 px and vertically centred (creates' screen rule, now also composes' print),
  page numbers 9 pt in both. `LAYOUT_VERSION` 3.

## Tests

- Python: `claudia-core/tests/test_page_and_language.py`, `claudia-creates/tests/test_printing.py`, the composes
  compatibility test, server tests for the four methods; `claudia-composes/tests/test_text_rebasing.py` covers the
  text commands' rebasing rules (composes' coverage ratio fell below its floor when the well-tested page and
  language modules moved to the kernel).
- Layout: `layout/tests/creates.test.ts` (edge to edge, frames, grids, lines, labels, notes, SVG, a deterministic PDF
  read back by pdf.js), with creates' built-in styles and shapes as the server sends them.
- Web: `tests/print-slides.test.ts` (the session's print setup and language, the bar's helpers, both print sources,
  `usePrint`, `useCreatorLanguage`); `e2e/print-creates.cjs` drives it in a browser, `e2e/print.cjs` still passes.

## Left for later

- Speaker notes (no model yet): a notes-page layout is one more `layout` value.
- Charts on slides (as in composes, D907): the preview draws a dashed frame and says so.
- Printing from the desktop shells (E9.23), and computes (E6.19) as a third print source.
