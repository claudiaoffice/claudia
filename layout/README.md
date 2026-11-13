# @claudia/layout

The page layout of the Claudia office suite: one deterministic TypeScript library that turns a document into pages
and pages into a PDF, the same byte for byte on every machine, browser and operating system (D901, D910).

It is written once and shared by the three apps. Today composes uses it for its print preview (File ▸ Print…, D906);
computes and creates will reuse its parts with adapters of their own (D902).

## Parts

| Part | Module | What it does |
|---|---|---|
| Units | `units.ts` | Whole thousandths of a point (*mpt*), exact `mulDivRound`, CSS lengths and paper sizes to mpt |
| Fonts | `fonts/` | Reads sfnt tables; shapes and subsets with pinned HarfBuzz WebAssembly (D903); a `FontSet` of faces by SHA-256 and variation; CSS font matching over a catalogue (`FontResolver`, D905, D911) |
| Text | `text/` | A paragraph to lines (UAX #14 breaks, hyphenation by TeX's patterns, lines chosen for the whole paragraph by Knuth and Plass, alignment, justification); CSS to a paragraph style; boxes clipped at their border |
| Flow | `flow/` | Paper sizes, page geometry, pagination with orphans, widows, keep-with-next and collapsing margins (D909) |
| Display list | `display/` | Glyph runs, paths (colours, gradients), images and groups (clip rectangle or path, rotation, transform, opacity); deterministic trigonometry; shape outlines |
| SVG | `svg/` | Any SVG picture as display items: an XML reader of its own, styles, transforms, paths, gradients, clip paths, text in the server's fonts (D914) |
| Images | `image/` | PNG, JPEG, GIF and BMP decoders of its own |
| PDF | `pdf/writer.ts` | A PDF from a display list: embedded subset fonts (CID = GID, ToUnicode), images, gradients, clipping, transparency groups |
| Apps | `apps/composes.ts` | A composes text as the server sends it, to pages |

## Rules

- **Pure.** ES2022 only: no DOM, no Node API, no clock, no random numbers. `tsconfig.json` loads no type libraries,
  so using one does not compile. The caller fetches every byte and checks its hash.
- **Integers.** Every length is a whole number of mpt. `Math.sin`, `Math.cos`, `Math.atan2` and `Math.pow` are not
  used (their last digit differs between engines).
- **Versioned.** A display list carries `LAYOUT_VERSION` and the HarfBuzz build's id; a change to the output is a
  new version.

## Use

```ts
import { HarfBuzz, FontSet, FontResolver, Hyphenator, layoutText, writePdf } from '@claudia/layout'

const hb = await HarfBuzz.load({ shaping, subset }, sha256)  // the two wasm files; sha256: your hash function, checked against HARFBUZZ_PIN
const fonts = new FontSet(hb)
fonts.add(fontHash, fontBytes)                                // every face the document needs
const hyphenator = new Hyphenator(patternsHash, patternsText, exceptionsText)   // from GET /api/hyphenation
const pages = layoutText(textDocument, fonts, new FontResolver(catalogue), { hyphenator })
const pdf = writePdf(pages.list, fonts, id => imageBytes[id], { title, lang })
```

The web app's `app/lib/print/` shows the whole round trip: fetching `/api/fonts` and the wasm, painting a page as
SVG, and printing.

## Develop

```sh
npm ci
npm test             # vitest; fetches the starter fonts into .fonts/ once (checked by SHA-256)
npm run typecheck    # the library and the tests
npm run docs         # TypeDoc into docs-build/
npm run coverage
```

The tests read every PDF back with pdf.js, compare image decoding against Pillow (`tests/images/expected.json`), and
compare the SVG drawings with librsvg's where `rsvg-convert` and `pdftoppm` are installed.
`scripts/copy-wasm.mjs DIR` copies the two pinned HarfBuzz files into an app (the web app runs it before `dev` and
`build`).

An app that links the library with `file:../layout` gets only a symlink from npm, not the library's dependencies.
`scripts/ensure-deps.mjs` installs them in `layout/node_modules` when they are missing or out of date (without the
development tools, unless they were there already). The web app runs it after `npm ci`/`npm install` and before
`dev` and `build`, so an existing checkout needs no reinstall.
