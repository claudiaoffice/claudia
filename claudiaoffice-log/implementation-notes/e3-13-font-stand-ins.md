# E3.13 slices a and b: shipped same-width fonts, and stand-ins as data (2026-11-16)

Branch `font-server-ui`. Architecture: `notes/mockups/e3-13-architecture-slices-a-b.svg`. UI proposal and the later
slices: `notes/e3-3-font-management-ui.md`, backlog item E3.13.

## What changed

- **Shipped fonts (slice a).** Arimo, Tinos, Cousine and Gelasio join the starter set (`starter.lock.json`, pinned
  at the same google/fonts commit `35e77c38`, fetched with `claudia_fonts.fetch` and checked by SHA-256 into
  `builtin/`). Arimo, Tinos and Cousine have the advance widths of Liberation Sans, Serif and Mono glyph for glyph
  (checked with fontTools on printable ASCII), which are those of Arial, Times New Roman and Courier New; Gelasio
  is metric-compatible with Georgia by its designer's statement. The shipped set grows from 5.9 MB to 11 MB. Tinos
  has no `OFL.txt` at that commit: its licence is in each file's name table (ID 13), which the OFL allows and a test
  checks. Before, `substitutions.json` pointed at Liberation, which no server had unless its operator added it, so
  Arial fell through to the generic family (Inter) in print and PDF.
- **One table (slice b).** `claudia_fonts/stand_ins.json` (was `substitutions.json`) holds the `generics` (the
  font of `serif`, `sans-serif`, `monospace` and the `fallback`) and the `same_widths` stand-ins. Python reads it
  (`DEFAULT_GENERICS`, `DEFAULT_SUBSTITUTIONS`); the server sends both with `GET /api/fonts` (`generics` added,
  `FONTS_FORMAT` stays 1); `scripts/generate_font_stand_ins.py` writes `layout/src/fonts/stand-ins.generated.ts`,
  and `tests/test_font_stand_ins_generated.py` fails when it is stale. The layout library's `DEFAULT_GENERICS` and
  its test world come from the generated file; a catalogue's own `generics` win.
- **Closeness.** `claudia_fonts.CLOSENESS` (`same`, `same-widths`, `other`) is the vocabulary of the UI to come;
  `Resolution.closeness` in Python and `Resolution.closeness` in the layout library say it. The generated file holds
  the type for TypeScript.
- **Import.** `claudia_computes_io.cell_looks.font_family` writes the file's font and its generic family only
  (`Arial, sans-serif`): the twin it wrote second (`'Liberation Sans'`) was a second copy of the table, and wrote a
  stand-in into the document. Stacks of older imports still resolve the same (the first family's stand-in wins).
- **Print.** `web/app/lib/print/assets.ts` passes the listing's `generics` to the layout library.

## The shared sample

`test-documents/xlsx/stand-in-fonts/`: `source.xlsx` (one cell per font, made by `_build_fixtures.py` from
`stand-ins.json`) and `stand-ins.json`, which says what a server with the shipped fonts shows each font with and how
close it is. The tests that read it: the library case (`spec.py`: import, round trip, the exported names),
`claudia-computes-io` (`test_stand_in_fonts.py`: through ods), `claudia-fonts` (`test_fonts_stand_ins.py`: the
catalogue), `claudia-server` (`test_server_fonts.py`: the listing), `claudia-typeset` (`test_typeset_source.py`:
`\setmainfont`), and the layout library (`tests/stand-ins.test.ts`: print and PDF).

## Places a document is shown or written

| Place | State |
|---|---|
| xlsx import (computes) | done + test (sample, `spec.py`) |
| xlsx export | done + test (sample, `export_checks`: every name written, no stand-in) |
| ods import and export | done + test (sample through ods, `test_stand_in_fonts.py`) |
| print preview and PDF, all three apps (layout library) | done + test (sample, `stand-ins.test.ts`; `print-assets.test.ts` for the generics) |
| LaTeX formulas and pages (typesetting) | done + test (sample, `test_typeset_source.py`) |
| `GET /api/fonts` | done + test (sample, `test_server_fonts.py`) |
| docx and odt import (composes) | not affected, because the importers do not read a file's fonts at all (reported as a bug, see below) |
| pptx and odp import (creates) | not affected, for the same reason (reported as a bug) |
| docx and odt export (composes) | not affected: untouched styles keep the file's own names; styles written by Claudia name generic families as Liberation (reported as a bug) |
| pptx and odp export (creates) | not affected: fonts are not modelled |
| on-screen editors (composes text, computes grid, creates slides) | gap → E3.3 (`@font-face` for the editors is not built): they show text in the computer's own fonts, so screen and print can differ |
| the print preview's notes | gap → E3.13 c: a same-width stand-in is laid out but not named (pinned by a test, to flip with slice c) |
| desktop clients | not affected: they show the web page, and their local server reads the same `builtin/` (11 MB instead of 5.9 MB in each package) |
| AI, search, history | not affected: they do not read or write fonts |

## Known duplicates left

- `cell_looks._SERIF` / `_MONO` (Python: which office fonts are serif or monospaced) and `web/app/lib/fonts.ts`'s
  `kind` (TypeScript) say part of the same fact. Untouched here; the fixed list in `fonts.ts` goes with E3.13 c (the
  font field from the catalogue), and the classification should come with the catalogue then.
- Resolution itself is written twice (`Catalogue.resolve` in Python for typesetting, `FontResolver` in TypeScript for
  print, D905). Their answers for the sample are tested against the same `stand-ins.json`.
