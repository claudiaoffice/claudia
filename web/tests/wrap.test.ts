import { describe, expect, it } from 'vitest'
import { DEFAULT_WRAP_GAP, MAX_WRAP_GAP, WRAPS, grabbable, nextWrap, wrapAnnouncement, wrapLabel, wrapOf, wrapParams } from '~/lib/wrap'

describe('how the text flows round an object (D1061)', () => {
  it('knows the four modes in the order the key cycles through them (D1064)', () => {
    expect(WRAPS).toEqual(['over', 'around', 'above-below', 'behind'])
  })
  it('reads an anchor that says nothing as floating over the text, with the usual gap', () => {
    expect(wrapOf({ kind: 'paragraph', holder: 'b1', offset: 0 })).toEqual({ wrap: 'over', gap: DEFAULT_WRAP_GAP })
    expect(wrapOf({ kind: 'paragraph', holder: 'b1', offset: 0, wrap: 'around', gap: 20 })).toEqual({ wrap: 'around', gap: 20 })
  })
  it('steps from one mode to the next and from the last back to the first', () => {
    expect(nextWrap('over')).toBe('around')
    expect(nextWrap('around')).toBe('above-below')
    expect(nextWrap('above-below')).toBe('behind')
    expect(nextWrap('behind')).toBe('over')
  })
  it('names each mode, and says which one an object has now when the key moves it', () => {
    expect(WRAPS.map(wrapLabel)).toEqual(['Over the text', 'Around the object', 'Above and below the object', 'Behind the text'])
    expect(wrapAnnouncement('behind')).toBe('Text wrap: Behind the text')
  })
  it('sends the gap only when one was asked for, and never more than the server allows', () => {
    expect(wrapParams('around')).toEqual({ wrap: 'around' })
    expect(wrapParams('around', 12)).toEqual({ wrap: 'around', gap: 12 })
    expect(wrapParams('around', 9999)).toEqual({ wrap: 'around', gap: MAX_WRAP_GAP })
    expect(wrapParams('around', -3)).toEqual({ wrap: 'around', gap: 0 })
  })
  it('lets go of the words that run over an object only for the object behind them, and only with Ctrl held (D1063)', () => {
    expect(grabbable('behind', true)).toBe(true)
    expect(grabbable('behind', false)).toBe(false)
    for (const wrap of ['over', 'around', 'above-below'] as const) expect(grabbable(wrap, false)).toBe(true)
  })
})
