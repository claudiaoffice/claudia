import { describe, expect, it } from 'vitest'
import { encodeTag, hashAt, matches, plainChat, splitTags, tagIds, withTag, type Thing } from '~/lib/tags'

const thing = (id: string, name: string, kind: Thing['kind'] = 'text'): Thing => ({ id, name, kind })

describe('a tag in the text of a message', () => {
  it('stores the id and the name it had, and reads back as the same', () => {
    const text = `Look at ${encodeTag('o7', 'Figure 1')} please`
    expect(splitTags(text)).toEqual([
      { type: 'text', text: 'Look at ' },
      { type: 'tag', id: 'o7', name: 'Figure 1' },
      { type: 'text', text: ' please' },
    ])
  })
  it('survives brackets, backslashes and a hash in the name', () => {
    const name = 'Q[1] \\ #2 (draft)'
    expect(splitTags(encodeTag('x1', name))).toEqual([{ type: 'tag', id: 'x1', name }])
  })
  it('leaves a plain #1 and anything that only looks like a tag as text', () => {
    for (const text of ['see #1', '[#1](http://example.org)', '[#1](thing:)', '[#1(thing:a)', 'a [b](thing:c)']) {
      expect(splitTags(text)).toEqual([{ type: 'text', text }])
    }
  })
  it('finds every tag, in order', () => {
    const text = `${encodeTag('a', 'A')} and ${encodeTag('b', 'B')} and ${encodeTag('a', 'A')}`
    expect(tagIds(text)).toEqual(['a', 'b', 'a'])
    expect(splitTags(text).filter((s) => s.type === 'tag')).toHaveLength(3)
  })
  it('is written for somebody who cannot see tags as the name behind a hash, the name it is now', () => {
    const text = `Check ${encodeTag('o7', 'Figure 1')}.`
    expect(plainChat(text)).toBe('Check #Figure 1.')
    expect(plainChat(text, (id) => (id === 'o7' ? 'Revenue chart' : undefined))).toBe('Check #Revenue chart.')
    expect(plainChat(text, () => undefined)).toBe('Check #Figure 1.')
  })
})

describe('typing a hash', () => {
  it('opens at a # that starts a word, with what was typed after it', () => {
    expect(hashAt('see #fig', 8)).toEqual({ start: 4, query: 'fig' })
    expect(hashAt('#', 1)).toEqual({ start: 0, query: '' })
    expect(hashAt('see #text b', 11)).toEqual({ start: 4, query: 'text b' })
  })
  it('is closed when the # is in the middle of a word, behind the caret, or a line away', () => {
    expect(hashAt('issue#12', 8)).toBeNull()
    expect(hashAt('see #fig', 3)).toBeNull()
    expect(hashAt('see #fig\nnext', 13)).toBeNull()
    expect(hashAt('no hash here', 12)).toBeNull()
  })
  it('is closed when the query has grown longer than any name', () => {
    expect(hashAt(`#${'x'.repeat(61)}`, 62)).toBeNull()
  })
  it('uses the last # before the caret', () => {
    expect(hashAt('#a and #b', 9)).toEqual({ start: 7, query: 'b' })
  })
})

describe('what the list offers', () => {
  const all = [thing('1', 'Figure 2', 'image'), thing('2', 'Revenue figure'), thing('3', 'Slide 1', 'slide'), thing('4', 'Figure 1', 'image'), thing('5', 'Text box 1')]
  it('is every thing for an empty query, by name', () => {
    expect(matches(all, '').map((t) => t.name)).toEqual(['Figure 1', 'Figure 2', 'Revenue figure', 'Slide 1', 'Text box 1'])
  })
  it('puts names that start with the query before names that only contain it, ignoring capitals and spaces', () => {
    expect(matches(all, 'FIG').map((t) => t.name)).toEqual(['Figure 1', 'Figure 2', 'Revenue figure'])
    expect(matches(all, '  figure   1 ').map((t) => t.name)).toEqual(['Figure 1'])
  })
  it('knows "1" matches the things with a 1 and nothing else', () => {
    expect(matches(all, '1').map((t) => t.name)).toEqual(['Figure 1', 'Slide 1', 'Text box 1'])
  })
  it('is short', () => {
    const many = Array.from({ length: 30 }, (_, i) => thing(`i${i}`, `Item ${i}`))
    expect(matches(many, '', 5)).toHaveLength(5)
  })
})

describe('picking a thing', () => {
  it('puts the tag where the #… was, and the caret behind it and the space that follows', () => {
    const typed = 'look at #fig now'
    const hash = hashAt(typed, 12)!
    const done = withTag(typed, hash, 12, thing('o7', 'Figure 1'))
    const tag = encodeTag('o7', 'Figure 1')
    expect(done.text).toBe(`look at ${tag} now`)
    expect(done.caret).toBe(`look at ${tag} `.length)
  })
  it('adds a space at the end of the text, so that writing goes on', () => {
    const done = withTag('see #fi', hashAt('see #fi', 7)!, 7, thing('o7', 'Figure 1'))
    expect(done.text).toBe(`see ${encodeTag('o7', 'Figure 1')} `)
    expect(done.caret).toBe(done.text.length)
  })
  it('adds no second space when one follows already', () => {
    const typed = '#fig '
    const done = withTag(typed, hashAt(typed, 4)!, 4, thing('o7', 'Figure 1'))
    expect(done.text).toBe(`${encodeTag('o7', 'Figure 1')} `)
  })
})
