import { describe, expect, it } from 'vitest'
import { anchorMark, wordAt } from '~/lib/anchor-mark'

describe('the word the label names (D1352)', () => {
  it('is the word right before the place', () => {
    expect(wordAt('In the allotment the pumpkins', 16)).toEqual({ word: 'allotment', within: false })
    expect(wordAt('In the allotment the pumpkins', 17)).toEqual({ word: 'allotment', within: false })
    expect(wordAt('year: kale', 6)).toEqual({ word: 'year:', within: false })
  })
  it('is the whole word the place is inside of', () => {
    expect(wordAt('has enough words in it', 12)).toEqual({ word: 'words', within: true })
  })
  it('is nothing at the start of a paragraph or after spaces only', () => {
    expect(wordAt('Kale', 0)).toBeNull()
    expect(wordAt('   Kale', 3)).toBeNull()
  })
  it('cuts a very long word', () => {
    expect(wordAt('x'.repeat(40), 40)?.word).toBe(`${'x'.repeat(23)}…`)
  })
})

describe('where the mark and its dotted line go', () => {
  it('stands at the character, as high as the line', () => {
    const mark = anchorMark({ left: 77, top: 119 }, 20, { x: 120, y: 150, w: 200, h: 96 })
    expect([mark.left, mark.top, mark.height]).toEqual([77, 119, 20])
  })
  it('the line goes from its foot down to the top edge and along it to the corner', () => {
    expect(anchorMark({ left: 77, top: 119 }, 20, { x: 120, y: 150, w: 200, h: 96 }).line).toBe('77,139 77,150 120,150')
  })
  it('an object above the mark: the line goes up from the top of the bar', () => {
    expect(anchorMark({ left: 77, top: 300 }, 20, { x: 40, y: 100, w: 200, h: 96 }).line).toBe('77,300 77,100 40,100')
  })
})
