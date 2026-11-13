/**
 * Hyphenation: where a word may be broken, by Frank Liang's algorithm and the patterns TeX uses (hyph-utf8).
 *
 * A {@link Hyphenator} is made from the text of one language's pattern file (`hyph-de-1996.pat.txt`) and its list of
 * exceptions (`.hyp.txt`), which the server hands out by SHA-256 (D913). It answers only "where may this word be
 * broken"; how many letters must stay on each side, how short a word may be and how many lines in a row may end in a
 * hyphen are the line breaker's rules ({@link HYPHENATION}). It uses `String.prototype.toLowerCase`, which does not
 * depend on the locale, so every engine finds the same points.
 *
 * @module
 */

/** The fixed rules hyphenation follows (D912). Part of the layout's version: changing one changes every page. */
export const HYPHENATION = {
  /** words shorter than this are never hyphenated */
  minWord: 5,
  /** at least this many letters stay before the hyphen, and after it */
  left: 2,
  right: 3,
  /** at most this many lines in a row end in a hyphen */
  maxConsecutive: 2,
} as const

/** Where a word may be broken, for one language. */
export class Hyphenator {
  private readonly patterns = new Map<string, Uint8Array>()
  private readonly exceptions = new Map<string, number[]>()
  private readonly longest: number

  /**
   * `id` names the pattern set (the SHA-256 of its files, as the server lists them) and is what a layout records;
   * `patterns` is the text of a `.pat.txt` file (patterns separated by white space), `exceptions` that of a
   * `.hyp.txt` file (words with their hyphens: `as-so-ciate`).
   */
  constructor(
    readonly id: string,
    patterns: string,
    exceptions = '',
  ) {
    let longest = 0
    const words = (text: string) => text.replace(/%[^\n]*/g, ' ').split(/\s+/).filter(Boolean)
    for (const token of words(patterns)) {
      const letters: string[] = []
      const values: number[] = [0]
      for (const ch of token) {
        if (ch >= '0' && ch <= '9') values[values.length - 1] = ch.charCodeAt(0) - 48
        else {
          letters.push(ch)
          values.push(0)
        }
      }
      if (!letters.length) continue
      const key = letters.join('')
      this.patterns.set(key, Uint8Array.from(values))
      longest = Math.max(longest, letters.length)
    }
    this.longest = longest
    for (const token of words(exceptions)) {
      const points: number[] = []
      let n = 0
      for (const ch of token) {
        if (ch === '-') points.push(n)
        else n++
      }
      this.exceptions.set(token.replace(/-/g, '').toLowerCase(), points)
    }
  }

  /** How many patterns were read (for a sanity check after loading). */
  get size(): number {
    return this.patterns.size
  }

  /**
   * The places `word` may be broken, as the number of characters (UTF-16 code units) before each break, ascending.
   * `word` should be letters only. No limits are applied: the patterns assume the language's own minimum of letters
   * on each side, so a point one letter from either end is not a real one ({@link HYPHENATION} is stricter anyway).
   */
  points(word: string): number[] {
    const lower = word.toLowerCase()
    const exception = this.exceptions.get(lower)
    if (exception) return exception.filter((p) => p > 0 && p < word.length)
    const letters = ['.', ...lower, '.']
    // the length of each letter in UTF-16 units, to answer in the word's own offsets
    const units = letters.map((l) => l.length)
    const values = new Uint8Array(letters.length + 1)
    for (let i = 0; i < letters.length; i++) {
      let key = ''
      for (let j = i; j < letters.length && j - i < this.longest; j++) {
        key += letters[j]
        const pattern = this.patterns.get(key)
        if (!pattern) continue
        for (let k = 0; k < pattern.length; k++) if (pattern[k]! > values[i + k]!) values[i + k] = pattern[k]!
      }
    }
    const out: number[] = []
    let offset = 0
    // values[k] is the value between letters[k-1] and letters[k]; a break between word letters p-1 and p is k = p+1
    for (let p = 1; p < letters.length - 2; p++) {
      offset += units[p]!
      if (values[p + 1]! % 2 === 1) out.push(offset)
    }
    return out
  }
}

/** One language's patterns as a server lists them (`GET /api/hyphenation`). */
export interface HyphenationEntry {
  /** BCP 47 tag the patterns are for: `de`, `en-US` */
  tag: string
  /** other tags they stand for: `en` for `en-US` */
  aliases?: readonly string[]
  name: string
  patterns: { sha256: string; size: number }
  exceptions: { sha256: string; size: number } | null
  licence: string
}

/**
 * The patterns for `language` (a BCP 47 tag) among `entries`: the entry with that tag or alias, otherwise the first
 * (by tag) whose language part is the same (`de-AT` → `de`, `en-AU` → `en-GB` or `en-US`, whichever sorts first);
 * `null` if none.
 */
export function pickHyphenation(entries: readonly HyphenationEntry[], language: string | undefined): HyphenationEntry | null {
  if (!language) return null
  const want = language.toLowerCase()
  const sorted = [...entries].sort((a, b) => (a.tag < b.tag ? -1 : a.tag > b.tag ? 1 : 0))
  const exact = sorted.find((e) => e.tag.toLowerCase() === want || (e.aliases ?? []).some((a) => a.toLowerCase() === want))
  if (exact) return exact
  const primary = want.split('-')[0]!
  return (
    sorted.find((e) => (e.aliases ?? []).some((a) => a.toLowerCase() === primary)) ??
    sorted.find((e) => e.tag.toLowerCase().split('-')[0] === primary) ??
    null
  )
}
