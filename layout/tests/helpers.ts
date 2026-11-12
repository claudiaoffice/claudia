import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { HARFBUZZ_PIN, HarfBuzz } from '../src/fonts/harfbuzz'

export const here = dirname(fileURLToPath(import.meta.url))
export const sha256 = (b: Uint8Array | string): string => createHash('sha256').update(b).digest('hex')
const wasmDir = join(here, '..', 'node_modules', 'harfbuzzjs', 'dist')
export const wasm = {
  shaping: new Uint8Array(readFileSync(join(wasmDir, HARFBUZZ_PIN.shaping.file))),
  subset: new Uint8Array(readFileSync(join(wasmDir, HARFBUZZ_PIN.subset.file))),
}
let loaded: Promise<HarfBuzz> | undefined
export const harfbuzz = (): Promise<HarfBuzz> => (loaded ??= HarfBuzz.load(wasm, sha256))
