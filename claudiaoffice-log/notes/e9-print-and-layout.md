# Print preview and the layout library (E9.4, E9.6, E9.14, E3.3; D901–D911)

Branch `layouting`, 2026-11-12. The owner's ask: File ▸ Print… for composes with a page preview, and on the way the
TypeScript layout library the three apps will share — fonts and shaping, paragraph to lines, box clipping for
floating objects, flow pagination on any paper, and a PDF writer fed by a display list of glyph runs, paths and
images — in the client only for now. Added on the owner's answer to the opening questions: make the font server
reachable by clients. Mock-up agreed first: `mockups/print-preview.svg`.

## The shape of it

```
server catalogue ──/api/fonts──▶ PrintAssets (web) ──bytes, sha256-checked──▶ FontSet (layout)
composes server ──blocks, styles, page, objects, images, shapes──▶ textDocument()
                                         │
                           layoutText()  (layout/src/apps/composes.ts)
            FontResolver ─▶ paragraphStyleFromCss ─▶ layoutParagraph ─▶ paginate ─▶ flowItems / boxItems
                                         │
                              display list (pages of items, mpt)
                         ┌───────────────┴───────────────┐
                 pageSvg() → preview               writePdf() → Print… / Download PDF
```

The display list is the contract: everything above it is layout, everything below it is painting, and the screen and
the PDF are painted from the same list. A display list carries `LAYOUT_VERSION` and the shaper id, so two lists
compare only if they were made by the same code with the same HarfBuzz build.

## The library, part by part (`layout/src/`)

| Part | Module | Reused by computes / creates |
|---|---|---|
| units, canonical JSON | `units.ts`, `canonical.ts` | yes |
| font files: sfnt tables, HarfBuzz bindings, a set of faces, CSS matching | `fonts/` | yes |
| paragraph to lines, CSS to a paragraph style, boxes | `text/` | cell text, labels, slide frames |
| flow pagination, paper sizes | `flow/` | paper sizes; computes needs a grid paginator beside it |
| display list, text/decoration items, deterministic trig, SVG path to outline | `display/` | yes |
| PNG, JPEG, GIF, BMP decoders | `image/` | yes |
| PDF writer | `pdf/writer.ts` | yes |
| composes adapter | `apps/composes.ts` | no: computes and creates get adapters of their own |

The library compiles with `lib: ES2022` and `types: []`, so a DOM or Node call does not compile; the tests have a
second tsconfig with both. Nothing in it reads a clock or a random number.

## Choices made while building

- **Raw WebAssembly, own bindings.** harfbuzzjs 0.4.x's glue had to be replaced: 1.6.x loads its wasm itself and
  cannot be given checked bytes. The library instantiates `harfbuzz.wasm` (shaping; emscripten imports satisfied by
  stubs) and `harfbuzz-subset.wasm` (no imports) itself; `layout/scripts/copy-wasm.mjs` copies both into `web/public/wasm`
  before `npm run dev`/`build` and refuses a file whose hash is not the pinned one. Vite could not resolve
  `?url` imports of the package's wasm, which is why it is a copy step.
- **`npm ci` in `web/` installs the library's dependencies too** (fixed the day after: the first patch built only
  where `npm ci` had also been run in `layout/`). A `file:` link gives the app a symlink and nothing else, and the
  library's imports resolve from `layout/node_modules`. `layout/scripts/ensure-deps.mjs` runs as web's
  `postinstall`, `predev` and `prebuild`; it does nothing when the locked versions are there, and otherwise runs
  `npm ci` in `layout/` (without the development tools unless they were installed). The Docker image copies the
  library's sources only, never a `node_modules` of the build machine.
- **Subset with glyph ids kept** (`RETAIN_GIDS`, `NO_HINTING`, `NOTDEF_OUTLINE`, layout tables dropped): CID = GID in
  the PDF, no remapping; the `W` array comes from the instanced subset's own `hmtx`, so widths match the outlines.
- **The preview SVG is written in points, not mpt.** Browsers cap font sizes (Chrome at about 10 000 px), so text
  at 12 000 "units" was drawn too small; the SVG's user unit is the point, with three decimals.
- **The letters inside a word are drawn by the browser** (`<text>` with `x` per word, the same font bytes registered
  as a `FontFace`, `font-variation-settings` set explicitly). Positioning every glyph would be exact but slow and
  unselectable; per word, the browsers measured within 0.06 pt of the layout in the spike.
- **Print through a hidden frame.** The PDF goes into an `<iframe>` from a `blob:` URL and its `contentWindow.print()`
  is called; where that throws (or the browser will not print a PDF in a frame) it opens in a tab. Headless Chrome
  crashes on printing a PDF frame, so the e2e test intercepts the bytes through `globalThis.__claudiaPrintDialog`.
- **A race fixed:** the preview relays out 150 ms after a setup change; Print and Download first await the pending
  layout (`settled()`), or they printed the old paper.
- **Objects are placed, not wrapped around** (D907). Wrapping is a bigger change to `paginate` (line widths per
  band) and waits until objects are visible in the editor too.
- **Page numbers are two runs** ("1 /" and "6"): UAX #14 allows no break before the slash, so the text is joined
  back before shaping. Worth knowing when reading a display list.

## Fonts for clients (E3.3, D905)

`claudia_server.fonts.FontService` serves the catalogue's redistributable fonts. `claudia_fonts.starter` fetches the
pinned starter set (`starter.lock.json`, google/fonts at `35e77c38…`), ~6 MB; `scripts/start.py` does it once into
`.state/fonts` and only warns if offline, and the Dockerfile does it in the Python stage. Liberation was left out:
its GitHub release assets were not reachable from the build sandbox. Only TrueType outlines are used for layout yet.

## Measured

- 139 A4 pages of the sample text: layout 155 ms, PDF 449 ms (Node 22, vitest `perf.test.ts`; a guard, not a
  benchmark).
- The PDF reads back in pdf.js with the same words and positions as the display list; poppler draws it line for
  line like the preview; `pdffonts` lists embedded subsets named `Fraunces…-opsz30wght500`, `Inter…-opsz14wght400`.
- e2e (`web/e2e/print.cjs`, Chrome headless): three A4 pages; the downloaded PDF is the same bytes on a second
  download; Letter landscape with page numbers gives four pages and a history entry; a custom 100 × 150 mm page;
  Ctrl+P prints the bytes Download saves; Esc returns; a viewer sees pages with the controls disabled.

## Not done, and where it went

- The desktop shells' native menus and their local servers' fonts: **E9.23**.
- The page view on the real layout, editable: **E9.24**.
- Print for computes (**E6.19**, needs a grid paginator) and creates (**E10.18**, boxes only; done 2026-11-13, `e10-print-slides.md`).
- Named page styles, sections, headers/footers: the rest of **E9.14**.
- SVG pictures and charts in print: a dashed placeholder and a note (D907).
- Hyphenation, text wrapping around objects, bidi and vertical text: nothing yet.
- Not run: the preview in Firefox and Safari (the library was, in the spike), and the Docker build.
- `npm audit` of `web/` still reports deepmerge (GHSA-gcqx-w48m-w2h4) through nuxt; it is on `main` too.
