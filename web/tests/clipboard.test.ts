import { describe, expect, it } from 'vitest'
import { isPlainTextField, spliceSelection, type PlainTextField } from '~/lib/clipboard'

function field(value: string, start: number, end: number): PlainTextField & { calls: unknown[] } {
  const calls: unknown[] = []
  const f: PlainTextField & { calls: unknown[] } = {
    value,
    selectionStart: start,
    selectionEnd: end,
    calls,
    setRangeText(text, s, e, mode) {
      calls.push([text, s, e, mode])
      const from = s ?? 0
      const to = e ?? 0
      f.value = f.value.slice(0, from) + text + f.value.slice(to)
    },
  }
  return f
}

describe('isPlainTextField', () => {
  it('accepts an <input>-shaped object', () => {
    expect(isPlainTextField({ tagName: 'INPUT' })).toBe(true)
  })
  it('accepts a <textarea>-shaped object', () => {
    expect(isPlainTextField({ tagName: 'TEXTAREA' })).toBe(true)
  })
  it('rejects anything else, including null', () => {
    expect(isPlainTextField({ tagName: 'DIV' })).toBe(false)
    expect(isPlainTextField(null)).toBe(false)
  })
})

describe('spliceSelection', () => {
  it('replaces a selected range and leaves the caret after the inserted text', () => {
    const f = field('hello world', 6, 11)
    spliceSelection(f, 'there')
    expect(f.value).toBe('hello there')
    expect(f.calls).toEqual([['there', 6, 11, 'end']])
  })
  it('inserts at the end when there is no selection (both bounds null)', () => {
    const f = field('hello', null as unknown as number, null as unknown as number)
    spliceSelection(f, '!')
    expect(f.value).toBe('hello!')
  })
})
