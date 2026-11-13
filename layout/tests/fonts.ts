// Fonts for the tests: the starter set of claudia-fonts (packages/claudia-fonts/src/claudia_fonts/starter.lock.json),
// fetched once into layout/.fonts by tests/setup.ts and checked by SHA-256. No font file is committed (D93).
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { Hyphenator } from '../src/text/hyphenate'
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

/** The server's pinned hyphenation patterns (D913), fetched into the same cache. */
export const HYPHENATION_LOCK = join(here, '..', '..', 'packages', 'claudia-server', 'src', 'claudia_server', 'hyphenation.lock.json')
interface LockedLanguage {
  tag: string
  patterns: LockFile
  exceptions: LockFile | null
}
export const hyphenationLanguages = (): LockedLanguage[] => JSON.parse(readFileSync(HYPHENATION_LOCK, 'utf8')).languages
export const hyphenationLock = (): LockFile[] => hyphenationLanguages().flatMap((l) => [l.patterns, ...(l.exceptions ? [l.exceptions] : [])])

/** A hyphenator for a pinned language, from the cached files. */
export function hyphenatorFor(tag: string): Hyphenator {
  const language = hyphenationLanguages().find((l) => l.tag === tag)
  if (!language) throw new Error(`no pinned patterns for ${tag}`)
  const text = (f: LockFile) => readFileSync(join(CACHE, f.name), 'utf8')
  return new Hyphenator(language.patterns.sha256, text(language.patterns), language.exceptions ? text(language.exceptions) : '')
}

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
