// Builds claudia-front-page.penpot: tokens first, then the library, then the front page made of it.
import * as penpot from '@penpot/library'
import { writeFileSync, mkdirSync } from 'node:fs'
import { buildTokens, TYPE, fontSpecOf } from './src/tokens.mjs'
import { createMeasurer } from './src/measure.mjs'
import { configure, emit, layout, newId, parseColorText } from './src/model.mjs'
import { buildLibrary } from './src/library.mjs'
import { foundations, frontPage, librarySheets } from './src/pages.mjs'

const REPO = process.env.CLAUDIA_REPO ?? '/home/claude/claudia'
const OUT = process.argv[2] ?? 'out/claudia-front-page.penpot'
const URL_ = process.env.CLAUDIA_URL ?? 'http://127.0.0.1:8765/'

const measurer = await createMeasurer({ url: URL_, cacheFile: 'out/measure-cache.json' })
mkdirSync('out', { recursive: true })

// 1. tokens (line-height: normal is what the browser says for the font, so measure it)
const normal = new Map()
for (const [name, t] of Object.entries(TYPE)) if (t.lh === 'normal') normal.set(t, await measurer.lineHeight({ ...fontSpecOf(name), lh: 'normal' }))
const T = buildTokens({ cssFile: `${REPO}/web/app/assets/tokens.css`, lineHeightOf: (t) => normal.get(t) })
const tokens = T.resolver()

const ctx = configure({ tokens, measurer, fileKey: 'claudia-front-page', fileId: null })

// 2. the trees
const lib = buildLibrary()
// the names the file's owner gave these layers in Penpot (after the ids were made, which come from the names)
for (const [k, n] of [['filter', 'Atoms / Filter'], ['search', 'Atoms / Search field'], ['dashed', 'Atoms / Dashed button'], ['wordmark', 'Atoms / Wordmark'], ['summary', 'Molecules / Document summary']]) lib[k].name = n
const ch52 = (await measurer.text({ ...fontSpecOf('body') }, '0'.repeat(52))).width
const found = foundations(T)
const front = await frontPage(lib, { tokens, ch52 })

const stack = async (nodes, gap = 48, x = 0) => {
  let y = 0
  for (const n of nodes) {
    const r = await layout(n, x, y)
    y += r.h + gap
  }
  return nodes
}
const pages = {
  Foundations: await stack(found),
  Icons: await stack([lib.appIcon, lib.glyph]),
  Components: await stack([lib.button, lib.rowAction, lib.field, lib.search, lib.dashed, lib.filter, lib.wordmark, lib.place, lib.docRow, lib.summary, lib.kind]),
  'Front page': await stack([front]),
}
void librarySheets

// 3. the file
const c = penpot.createBuildContext()
c.addFile({ name: 'Claudia: front page' })
ctx.fileId = c.currentFileId
c.addTokensLib(T.doc)

for (const [name, raw] of Object.entries(T.coreColors)) {
  const col = parseColorText(raw)
  c.addLibraryColor({ name, path: 'Claudia', color: col.hex, opacity: col.opacity })
}
for (const [name, t] of Object.entries(TYPE)) {
  const f = fontSpecOf(name)
  const lh = t.lh === 'normal' ? normal.get(t) / t.size : t.lh
  c.addLibraryTypography({
    name,
    path: 'Claudia',
    fontId: f.fontId,
    fontFamily: f.family,
    fontVariantId: f.weight === 400 ? 'regular' : String(f.weight),
    fontSize: String(f.size),
    fontWeight: String(f.weight),
    fontStyle: 'normal',
    lineHeight: String(Math.round(lh * 1000) / 1000),
    letterSpacing: String(f.ls),
    textTransform: f.transform,
  })
}

for (const [name, nodes] of Object.entries(pages)) {
  c.addPage({ name })
  for (const n of nodes) emit(c, n)
  c.closePage()
}
c.closeFile()
const bytes = await penpot.exportAsBytes(c)
writeFileSync(OUT, bytes)
await measurer.close()
console.log('wrote', OUT, bytes.length, 'bytes')
void newId
