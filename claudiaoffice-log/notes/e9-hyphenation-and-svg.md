# Hyphenation and SVG to PDF (E9.25, E9.26; D912–D916)

Branch `layouting`, 2026-11-12, on top of the print preview round (`e9-print-and-layout.md`). The owner's ask:
hyphenation and SVG → PDF, both built "with the other two apps in mind, abstract and general". The questions asked
before starting and the owner's answers ("excellent suggestions"; pick the design yourself, no mock-up review this
time) are the basis of D912–D916. The screens were therefore not agreed beforehand; they are recorded as screenshots
of what was built: `mockups/print-preview-language.png` and `mockups/style-hyphenate.png`.

## Line breaking: from greedy to Knuth–Plass

`layout/src/text/paragraph.ts` turns a paragraph into TeX's boxes, glue and penalties and finds the breaks with the
least demerits. What is worth knowing when reading it:

- **Elements.** A word (a UAX #14 piece) is one box, or several where it may be hyphenated, with a flagged penalty
  of 50 and the width of a hyphen between them. Spaces are glue (justified: stretch ½ space, shrink ⅓ space; ragged:
  none). A break after a piece with no space (after `-`, `/`, between ideographs) is a penalty of 0, or 50 and
  flagged after a hyphen of the text's own. A newline and the end of the paragraph are infinite glue and a forced
  break.
- **Passes.** Tolerance 100 without pattern hyphens; 200 with them; 200 with 1.5 em extra stretch per line; finally
  anything, with a rescue that breaks where nothing fits any more (an overfull line) rather than giving up. A ragged
  line has 3 em of slack at little cost, which is what makes ragged text even too.
- **Demerits.** TeX's: (10 + badness)², plus or minus the penalty², 10 000 for two flagged lines in a row, 10 000
  for adjacent lines of very different tightness. Two rules are hard: no more than 2 flagged lines in a row, and
  (as good as hard: 1 000 000 demerits) not the end of a hyphenated word alone on the last line.
- **Integers.** Badness is TeX's integer approximation of 100·(t/s)³; all widths are mpt. Two equal totals are
  decided by the order of the active list, which is fixed (sorted keys), so ties break the same way everywhere.
- **Soft hyphens.** UAX #14 already breaks *after* U+00AD, so a word with soft hyphens arrives as several pieces;
  a piece ending in one gets a hyphen-drawing penalty, and its pieces on one line are merged back into one word.
  With `hyphens: none` the piece is glued to the next instead. Soft hyphens are never shaped or drawn.
- **Widths at a break.** A word is shaped once; the width of its part before a hyphenation point is the sum of its
  clusters, and only cluster boundaries are candidates. The hyphen is shaped separately and appended. Kerning
  across the break is therefore not applied — the same simplification TeX makes with discretionaries.
- **What changed for callers.** `PlacedWord` gained `length` (the source characters it stands for; `text` is what is
  drawn, with the hyphen and without soft hyphens), `Line` gained `hyphenated`. `locate` uses `length`.
  `layoutParagraph(…, options)` and `layoutBox(…, options)` take `{ hyphenator }`. `LAYOUT_VERSION` is 2.

Cost: 137 A4 pages of justified German body text with hyphenation lay out in about 0.5 s (Node 22, `perf.test.ts`;
the greedy breaker took 0.16 s for the same pages), 578 of their lines end in a hyphen.

A long German compound on a narrow measure (150 pt at 10 pt) is the case that needs the third pass: a line that is
only part of a word has no space to stretch, so no strict solution exists. With the emergency stretch the result is
what LaTeX gives with `\emergencystretch`; spaces on a 250 pt measure stay below twice their width (tested).

## Patterns

`Hyphenator` is about 100 lines: patterns into a map from letter strings to digit arrays, exceptions as words with
their points. Points are returned in UTF-16 offsets of the word; the breaker applies the minimums in code points.
Patterns may give a point one letter from either end (they rely on TeX's `\lefthyphenmin`), which is why the tests
filter by the minimums before comparing.

The server side (`claudia_server/hyphenation.py`) is deliberately the same shape as the fonts: a lock file in the
package, a `fetch` that checks each file, a service that reads the files once at start and checks them again, and
two routes. It lives in `claudia_server`, not `claudia_fonts`, because patterns are not fonts.

## SVG

`layout/src/svg/`: `xml.ts` (the reader), `style.ts` (presentation attributes, `<style>` with simple selectors,
`style` attributes, inheritance), `geometry.ts` (transforms, lengths, path data, shapes, `preserveAspectRatio`),
`render.ts` (`parseSvg`, `svgFonts`, `drawSvg`). The output is one group per picture, in page coordinates,
clipped to its box. Choices:

- **Paths in page coordinates.** Every point goes through the full transform and is rounded to mpt, so a path's
  stroke is drawn in page space with its width scaled by √|det|. That is exact for rotation and uniform scaling and
  an approximation for a squashed stroke (rare in pictures; noted nowhere).
- **Text and pictures in a local frame.** Glyph runs and images cannot be skewed in the display list, so they sit in
  a group with a `matrix`: the transform divided by its scale, with lengths multiplied by the scale (about mpt, so
  whole numbers keep their precision).
- **Gradients** carry their own `matrix` the same way, so an object-bounding-box gradient (coordinates 0…1) keeps its
  precision. PDF: a shading pattern whose matrix includes the transforms of the groups it sits in (the writer keeps
  track); if the stops' opacities differ, a luminosity soft mask with the same shading in grey.
- **Group opacity** is a PDF transparency group (a form XObject); all pages and forms share one resource dictionary.
- **`spreadMethod` reflect/repeat** are drawn as pad, and said so.
- **Arc flags written together** (`a5 5 0 015 5`, what svgo writes) are read digit by digit: the path parser is a
  scanner, not a tokenizer.

The comparison test renders the four fixtures with `rsvg-convert` and our PDF with `pdftoppm` at 216 dpi: mean
difference per colour value 0.09–0.34 for the drawings and 1.18 for the formula (edge smoothing of small glyphs),
values more than 96 apart in at most 0.02 % of them. It is skipped where the two programs are not installed.

## Web

- `PrintAssets` loads `/api/hyphenation` with the fonts and makes a `Hyphenator` per language on demand (files
  checked by SHA-256). `layOut` passes it to `layoutText`.
- `paint.ts` draws gradients, group matrices, clip paths, fill rules, stroke details and layer opacity, the PDF's way
  round; the preview shows SVG pictures from the display list, not as `<image>`.
- The text's language is in the session (`language`, event `language`, `setLanguage`). `TextWorkspace` sets it to
  the interface language once, for the person who has just created the text.
- The bar wraps (`flex-wrap`) instead of scrolling: with the history panel open at 1360 px, Print… had moved out of
  sight.

## Not done

- A language per paragraph style and a person's own hyphenations: **E9.27**.
- Filters, masks, patterns, markers, text on a path, external pictures in SVG.
- Kerning across a hyphenation point; hyphenation in the flow view (deliberately not, D912).
- Not run: Firefox and Safari for the preview; the Docker build. The e2e test ran in Chromium (headless shell).
