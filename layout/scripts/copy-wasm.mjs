// Copies the two HarfBuzz WebAssembly files from harfbuzzjs into a folder (default: layout/wasm), checking each
// against the pin in src/fonts/harfbuzz.ts, so an app can serve exactly the bytes the library expects.
// harfbuzzjs is looked up from the folder the command runs in (an app that installed this package), then from here.
// Usage: node node_modules/@claudia/layout/scripts/copy-wasm.mjs public/wasm
import { createHash } from 'node:crypto'
import { copyFileSync, mkdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(join(here, '..', 'src', 'fonts', 'harfbuzz.ts'), 'utf8')
const pins = [...source.matchAll(/file: '([^']+)', sha256: '([0-9a-f]{64})'/g)].map((m) => ({ file: m[1], sha256: m[2] }))
if (pins.length !== 2) throw new Error('cannot read the pins from src/fonts/harfbuzz.ts')
const find = (base) => {
  try {
    return dirname(createRequire(base).resolve('harfbuzzjs/dist/harfbuzz.wasm'))
  } catch {
    return null
  }
}
const from = find(join(process.cwd(), 'package.json')) ?? find(import.meta.url)
if (!from) throw new Error('harfbuzzjs is not installed: run `npm ci` (in web/ this also installs the layout library\'s dependencies)')
const to = resolve(process.argv[2] ?? join(here, '..', 'wasm'))
mkdirSync(to, { recursive: true })
for (const { file, sha256 } of pins) {
  const got = createHash('sha256').update(readFileSync(join(from, file))).digest('hex')
  if (got !== sha256) throw new Error(`${file}: SHA-256 ${got}, the pin says ${sha256}`)
  copyFileSync(join(from, file), join(to, file))
  console.log(`${file} -> ${to}`)
}
