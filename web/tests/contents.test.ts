// What the clients work out about a table of contents (E9.31): the options kept in bounds, what a table shows and the
// styles it is drawn in.
import { describe, expect, it } from 'vitest'
import { entryWords, looksOf, MAX_LEVEL, shows, withOption, type ContentsEntry, type Toc } from '~/lib/contents'

const DEFAULT_TOC: Toc = { kind: 'toc', first: 1, last: 3, numbers: true, places: true, leader: 'dots' }

const entry = (target: string, level: number, number: string | null = null): ContentsEntry => ({ target, level, number, text: `Heading ${target}`, style: `contents-${level}`, place: null })

describe('the options', () => {
  it('keep the levels between 1 and the deepest, and move the other end along', () => {
    expect(withOption(DEFAULT_TOC, 'last', 12).last).toBe(MAX_LEVEL)
    expect(withOption(DEFAULT_TOC, 'first', 0).first).toBe(1)
    expect(withOption(DEFAULT_TOC, 'first', 5)).toMatchObject({ first: 5, last: 5 })
    expect(withOption({ ...DEFAULT_TOC, first: 3, last: 4 }, 'last', 2)).toMatchObject({ first: 2, last: 2 })
    expect(withOption(DEFAULT_TOC, 'leader', 'none')).toEqual({ ...DEFAULT_TOC, leader: 'none' })
  })
})

describe('what a table shows', () => {
  it('reads an entry with its number, counts the entries and their levels, and names their looks once each', () => {
    expect(entryWords(entry('a', 1, '2.1'))).toBe('2.1 Heading a')
    expect(entryWords(entry('a', 1))).toBe('Heading a')
    const entries = [entry('a', 2), entry('b', 1), entry('c', 2)]
    expect(shows(entries)).toEqual({ count: 3, levels: [1, 2] })
    const styles = [{ id: 'contents-1', name: 'Contents 1' }, { id: 'contents-2', name: 'Contents 2' }]
    expect(looksOf(entries, styles)).toEqual(['Contents 1', 'Contents 2'])
  })
})
