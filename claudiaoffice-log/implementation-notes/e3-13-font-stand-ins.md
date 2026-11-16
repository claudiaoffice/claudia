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
- **One table (slice b).** `claudia_core.stand_ins` (was `claudia_fonts/substitutions.json`; in 0004 briefly
  `claudia_fonts/stand_ins.json`, moved to the kernel with CODE-42 below) holds `GENERIC_FONTS` (the font of `serif`,
  `sans-serif`, `monospace` and the `fallback`), `GENERIC_ALIASES` (every CSS name for a generic family) and
  `SAME_WIDTHS`. `claudia_fonts` builds on it (`DEFAULT_GENERICS`, `DEFAULT_SUBSTITUTIONS`); the server sends both with `GET /api/fonts` (`generics` added,
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

## CODE-42: exports named a generic family by a font Claudia does not show (fixed 2026-11-16)

composes wrote a style whose font is `serif`, `sans-serif` or `monospace` into docx and odt as Liberation Serif, Sans
and Mono (`_style_look._GENERIC`, a third copy of the generic families, disagreeing with the other two), skipped
`system-ui` to name the next family, and wrote `ui-monospace` as a font name; computes wrote the first family of the
list as it was, so `serif` or `system-ui` became the name of a font in xlsx and ods. Claudia shows and prints those
styles in Fraunces, Inter and JetBrains Mono, so the exported file looked different from what the person saw.

Now both exporters call `claudia_core.stand_ins.file_font`: the first family, or the font a generic family (or a CSS
name for one) is shown with. The table moved into the kernel because `claudia-composes-io` and `claudia-computes-io`
must read it and depend on the kernel only; the kernel does no I/O, so it is Python data, not a file.
`claudia-fonts` now depends on `claudia-core`. The generated TypeScript copy gained `GENERIC_ALIASES`, which replace
the layout library's own alias table (same entries). Tests on the shared sample's `generic_families`: `claudia-core`
(`test_stand_ins.py`), composes docx and odt (`test_composes_generic_fonts.py`), computes xlsx and ods
(`test_computes_generic_fonts.py`), and the layout library (`stand-ins.test.ts`), which checks that print uses the
same font the files name.

## Bugs 1 and 2: the importers of the text and slide apps read the file's fonts (fixed 2026-11-16, CODE-43, CODE-44)

Before, `docx_to_text`, `odt_to_text`, `pptx_to_slides` and `odp_to_slides` did not read a font at all: every style
kept the app's own font, so an imported Word or PowerPoint file showed in Inter and Fraunces, and the import reported no
loss. A run or span that named a font was reported as `formatting`, as if the font were something the model could not
hold.

Now each importer finds the font where the program that wrote the file finds it (diagram:
`notes/mockups/e3-13-import-fonts.svg`):

| Format | Where the font comes from | Where it goes |
|---|---|---|
| docx | a style's `w:rFonts` (a theme reference such as `minorHAnsi` wins over `w:ascii`), along `w:basedOn`, then `w:docDefaults`; theme fonts from the theme part (`claudia_opc_io.ThemeFonts`) | Body text, Title, Heading 1 and 2, Quote (`_docx_fonts.py`) |
| odt | a paragraph style's `style:font-name` (through `office:font-face-decls`) or `fo:font-family`, along the parent styles, then the default paragraph style (`claudia_odf_io.font_faces`, `font_of`) | the same styles (`_odt_fonts.py`) |
| pptx | a run's `a:latin`, else the theme's heading font for a title placeholder, else its body font; `+mj-lt` and `+mn-lt` are the theme's | Body text takes the body font; a box in another font gets a style of its own (`_pptx_fonts.py`) |
| odp | a span's text style, else the paragraph style, else the box's presentation or graphic style, else the default style of drawn things | as for pptx (`_odp_fonts.py`) |

A font comes in as the CSS list `claudia_core.stand_ins.css_family` makes (`'Times New Roman', serif`): the name the
file says, never a stand-in, so it goes back out the same (`file_font`). In the slides app, a box whose words are in
another font than Body text gets a style based on Body text (or Shape label), named "Body text · Georgia" and marked
`to_name`, made once per font: the way an import names a look it cannot place. The exporters write the fonts back:
docx and odt through the styles (as before), pptx into the theme's body font and each run, odp into the default style
of drawn things and a box's paragraph style (only where it differs from the body font).

Losses: a font is no loss. `formatting` is still reported for words in two fonts in one box (only one font per box is
modelled) and for a span that says more than a font.


`test-documents/stand-in-fonts.json` (moved from `xlsx/stand-in-fonts/stand-ins.json` with bugs 1 and 2, as five
formats read it now) and one file per format made from it by `_build_fixtures.py`: `xlsx/stand-in-fonts` (one cell per
font), `docx/` and `odt/stand-in-fonts` (the styles of `text_styles`, the body font through the defaults and the theme),
`pptx/` and `odp/stand-in-fonts` (the body and title fonts of `slides`, one box per font). The table says what a server with the shipped fonts shows each font with and how
close it is. The tests that read it: the library case (`spec.py`: import, round trip, the exported names),
`claudia-computes-io` (`test_computes_stand_in_fonts.py`: through ods), `claudia-fonts` (`test_fonts_stand_ins.py`: the
catalogue), `claudia-server` (`test_server_fonts.py`: the listing), `claudia-typeset` (`test_typeset_source.py`:
`\setmainfont`), the layout library (`tests/stand-ins.test.ts`: print and PDF), and for bugs 1 and 2 the library
cases of the four new files (import, an edit, the round trip, no stand-in written), `test_composes_file_fonts.py`,
`test_creates_file_fonts.py` (a file written from nothing keeps every font; no loss), `test_theme_fonts.py` and
`test_odf_fonts.py`.

## Places a document is shown or written

| Place | State |
|---|---|
| xlsx import (computes) | done + test (sample, `spec.py`) |
| xlsx export | done + test (sample, `export_checks`: every name written, no stand-in; CODE-42 for generic families) |
| ods import and export | done + test (sample through ods, `test_computes_stand_in_fonts.py`; CODE-42 for generic families) |
| print preview and PDF, all three apps (layout library) | done + test (sample, `stand-ins.test.ts`; `print-assets.test.ts` for the generics) |
| LaTeX formulas and pages (typesetting) | done + test (sample, `test_typeset_source.py`) |
| `GET /api/fonts` | done + test (sample, `test_server_fonts.py`) |
| docx and odt import (composes) | done + test (CODE-43: samples `docx/` and `odt/stand-in-fonts`, `test_composes_file_fonts.py`: no loss) |
| pptx and odp import (creates) | done + test (CODE-44: samples `pptx/` and `odp/stand-in-fonts`, `test_creates_file_fonts.py`) |
| docx and odt export (composes) | done + test (CODE-42: a generic family is written as the font it is shown with; CODE-43: a file written from nothing keeps the sample's fonts) |
| pptx and odp export (creates) | done + test (CODE-44: written from nothing and patched, the sample keeps every font; no stand-in written) |
| pptx placeholders (titles, body placeholders) | gap → reported as a bug: they are not imported at all, so their fonts cannot be either (the sample's title is a text box) |
| a docx run with its own font | gap → stays `formatting` (the model holds fonts per style, not per run); comes with direct formatting |
| on-screen editors (composes text, computes grid, creates slides) | gap → E3.3 (`@font-face` for the editors is not built): they show text in the computer's own fonts, so screen and print can differ |
| the print preview's notes | gap → E3.13 c: a same-width stand-in is laid out but not named (pinned by a test, to flip with slice c) |
| desktop clients | not affected: they show the web page, and their local server reads the same `builtin/` (11 MB instead of 5.9 MB in each package) |
| AI, search, history | not affected: they do not read or write fonts |

## Known duplicates left

- `claudia_core.stand_ins.SERIF_FONTS` / `MONOSPACE_FONTS` (Python: which office fonts are serif or monospaced; moved
  from `cell_looks._SERIF` / `_MONO` with bugs 1 and 2, so the three importers share them) and `web/app/lib/fonts.ts`'s
  `kind` (TypeScript) say part of the same fact. Untouched there; the fixed list in `fonts.ts` goes with E3.13 c (the
  font field from the catalogue), and the classification should come with the catalogue then.
- Resolution itself is written twice (`Catalogue.resolve` in Python for typesetting, `FontResolver` in TypeScript for
  print, D905). Their answers for the sample are tested against the same `stand-ins.json`.
