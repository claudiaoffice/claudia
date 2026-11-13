import { describe, expect, it } from 'vitest'
import { HYPHENATION, Hyphenator, pickHyphenation, type HyphenationEntry } from '../src/text/hyphenate'
import { hyphenatorFor } from './fonts'

/** A word with its hyphenation points marked. */
const marked = (h: Hyphenator, word: string) => {
  const points = h.points(word).filter((p) => p >= HYPHENATION.left && word.length - p >= HYPHENATION.right)
  let out = ''
  for (let i = 0; i < word.length; i++) out += (points.includes(i) ? '-' : '') + word[i]
  return out
}

describe('Hyphenator', () => {
  it('finds the points of German words by the 1996 patterns', () => {
    const de = hyphenatorFor('de')
    expect(de.size).toBeGreaterThan(30000)
    expect(marked(de, 'Silbentrennung')).toBe('Sil-ben-tren-nung')
    expect(marked(de, 'Rechnung')).toBe('Rech-nung')
    expect(marked(de, 'Ergebnis')).toBe('Er-geb-nis')
    expect(marked(de, 'Übersetzung')).toBe('Über-set-zung')
  })

  it('finds the points of English words, and takes exceptions as they are written', () => {
    const us = hyphenatorFor('en-US')
    expect(marked(us, 'hyphenation')).toBe('hy-phen-ation')
    expect(marked(us, 'associate')).toBe('as-so-ciate')
    expect(marked(us, 'Philanthropic')).toBe('Phil-an-thropic')
  })

  it('reads patterns given inline, and ignores comments', () => {
    const h = new Hyphenator('test', '% a comment\n1ba 1be\n', 'ta-ble')
    expect(h.points('abababe')).toEqual([1, 3, 5])
    expect(h.points('table')).toEqual([2])
    expect(h.size).toBe(2)
  })

  it('has fixed limits that the line breaker applies', () => {
    expect(HYPHENATION).toEqual({ minWord: 5, left: 2, right: 3, maxConsecutive: 2 })
  })
})

describe('pickHyphenation', () => {
  const entry = (tag: string, aliases: string[] = []): HyphenationEntry => ({
    tag,
    aliases,
    name: tag,
    licence: 'MIT',
    patterns: { sha256: tag, size: 1 },
    exceptions: null,
  })
  const listing = [entry('en-US', ['en']), entry('de'), entry('en-GB')]

  it('matches a tag, an alias, then the language part', () => {
    expect(pickHyphenation(listing, 'de')?.tag).toBe('de')
    expect(pickHyphenation(listing, 'de-AT')?.tag).toBe('de')
    expect(pickHyphenation(listing, 'en')?.tag).toBe('en-US')
    expect(pickHyphenation(listing, 'en-gb')?.tag).toBe('en-GB')
    expect(pickHyphenation(listing, 'en-AU')?.tag).toBe('en-US')
    expect(pickHyphenation(listing, 'fr')).toBeNull()
    expect(pickHyphenation(listing, undefined)).toBeNull()
    expect(pickHyphenation([entry('en-GB'), entry('en-US')], 'en-NZ')?.tag).toBe('en-GB')
  })
})
