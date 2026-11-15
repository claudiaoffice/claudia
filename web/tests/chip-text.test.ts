import { describe, expect, it } from 'vitest'
import { messageOf, offsetOf, placeOf, textOf, type Piece } from '../app/lib/chip-text'
import { encodeTag } from '../app/lib/tags'

const words = (text: string): Piece => ({ type: 'text', text })
const tag = (id: string, name: string): Piece => ({ type: 'tag', id, name })
const TAG = encodeTag('o7', 'Figure 1') // 17 characters or so; the tests use its length, not a number

describe('the message a box holds', () => {
  it('writes words as they are and a chip as the tag it stands for', () => {
    expect(textOf(words('see '))).toBe('see ')
    expect(textOf(tag('o7', 'Figure 1'))).toBe(TAG)
    expect(messageOf([words('see '), tag('o7', 'Figure 1'), words(' please')])).toBe(`see ${TAG} please`)
  })

  it('writes the name a chip was written with, escaped, as every tag is', () => {
    expect(textOf(tag('o1', 'a]b'))).toBe('[#a\\]b](thing:o1)')
  })
})

describe('places in the box and in the message', () => {
  const pieces = [words('see '), tag('o7', 'Figure 1'), words(' please')]

  it('counts a chip as the whole tag', () => {
    expect(offsetOf(pieces, { index: 0, inner: 4 })).toBe(4)
    expect(offsetOf(pieces, { index: 1, inner: 0 })).toBe(4)
    expect(offsetOf(pieces, { index: 1, inner: 1 })).toBe(4 + TAG.length)
    expect(offsetOf(pieces, { index: 2, inner: 3 })).toBe(4 + TAG.length + 3)
  })

  it('finds the place of every position and is the inverse of offsetOf where a caret can be', () => {
    for (const place of [
      { index: 0, inner: 0 },
      { index: 0, inner: 2 },
      { index: 1, inner: 1 },
      { index: 2, inner: 0 },
      { index: 2, inner: 7 },
    ]) {
      const offset = offsetOf(pieces, place)
      expect(offsetOf(pieces, placeOf(pieces, offset))).toBe(offset)
    }
  })

  it('puts a position inside the text of a chip after the chip', () => {
    expect(placeOf(pieces, 4 + 3)).toEqual({ index: 1, inner: 1 })
    expect(placeOf(pieces, 4)).toMatchObject({ index: 0, inner: 4 })
  })

  it('knows the end, and an empty box', () => {
    expect(placeOf(pieces, 999)).toEqual({ index: 2, inner: 7 })
    expect(placeOf([], 0)).toEqual({ index: 0, inner: 0 })
    expect(offsetOf([], { index: 0, inner: 0 })).toBe(0)
    expect(placeOf([tag('o7', 'x')], 99)).toEqual({ index: 0, inner: 1 })
  })
})
