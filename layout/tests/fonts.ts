// Fonts for the tests: the starter set of claudia-fonts (packages/claudia-fonts/src/claudia_fonts/starter.lock.json),
// fetched once into layout/.fonts by tests/setup.ts and checked by SHA-256. No font file is committed (D93).
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { here } from './helpers'

export const LOCK = join(here, '..', '..', 'packages', 'claudia-fonts', 'src', 'claudia_fonts', 'starter.lock.json')
export const CACHE = join(here, '..', '.fonts')

export interface LockFile {
  name: string
  url: string
  sha256: string
  size: number
}
export interface LockCollection {
  name: string
  folder: string
  files: LockFile[]
}
export const lock = (): LockCollection[] => JSON.parse(readFileSync(LOCK, 'utf8')).collections

/** Short names for the fixtures the tests use. */
const NAMES: Record<string, string> = {
  InterVariable: 'Inter[opsz,wght].ttf',
  InterItalicVariable: 'Inter-Italic[opsz,wght].ttf',
  FrauncesVariable: 'Fraunces[SOFT,WONK,opsz,wght].ttf',
  'Carlito-Regular': 'Carlito-Regular.ttf',
  'Carlito-Bold': 'Carlito-Bold.ttf',
  'Carlito-Italic': 'Carlito-Italic.ttf',
  'Caladea-Regular': 'Caladea-Regular.ttf',
  JetBrainsMonoVariable: 'JetBrainsMono[wght].ttf',
}

const cache = new Map<string, Uint8Array>()
/** The bytes of a fixture font by its short name. */
export function fixture(name: string): Uint8Array {
  const file = NAMES[name] ?? name
  let bytes = cache.get(file)
  if (!bytes) {
    bytes = new Uint8Array(readFileSync(join(CACHE, file)))
    cache.set(file, bytes)
  }
  return bytes
}
