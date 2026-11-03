import { describe, expect, it } from 'vitest'
import { alignment, cellLabel, columnIndex, columnName, formulaOf, inputOf, parseCell, rangeLabel, show } from '~/lib/cells'

describe('labels', () => {
  it('names columns like a spreadsheet', () => {
    expect([0, 25, 26, 27, 51, 52, 701, 702].map(columnName)).toEqual(['A', 'Z', 'AA', 'AB', 'AZ', 'BA', 'ZZ', 'AAA'])
    expect(['A', 'z', 'AA', 'AAA'].map(columnIndex)).toEqual([0, 25, 26, 702])
  })
  it('labels cells and ranges', () => {
    expect(cellLabel(2, 1)).toBe('B3')
    expect(rangeLabel(3, 2, 0, 0)).toBe('A1:C4')
    expect(rangeLabel(1, 1, 1, 1)).toBe('B2')
  })
  it('reads a cell label', () => {
    expect(parseCell('b3')).toEqual([2, 1])
    expect(parseCell(' AA10 ')).toEqual([9, 26])
    expect(parseCell('A0')).toBeNull()
    expect(parseCell('hello')).toBeNull()
    expect(parseCell('A9999999')).toBeNull()
  })
})

describe('showing values', () => {
  it('shows each kind', () => {
    expect(show(null)).toBe('')
    expect(show({ t: 'int', v: 42 })).toBe('42')
    expect(show({ t: 'float', v: 3.5 })).toBe('3.5')
    expect(show({ t: 'float', v: 0.1 + 0.2 })).toBe('0.3')
    expect(show({ t: 'bool', v: true })).toBe('TRUE')
    expect(show({ t: 'text', v: 'hi' })).toBe('hi')
  })
  it('aligns numbers right, text left, booleans in the middle', () => {
    expect(alignment({ t: 'int', v: 1 })).toBe('right')
    expect(alignment({ t: 'text', v: 'a' })).toBe('left')
    expect(alignment({ t: 'bool', v: false })).toBe('center')
    expect(alignment(null)).toBe('left')
  })
})

describe('inputOf', () => {
  it('gives back what typing would need', () => {
    expect(inputOf(null)).toBe('')
    expect(inputOf({ t: 'int', v: 7 })).toBe('7')
    expect(inputOf({ t: 'bool', v: false })).toBe('FALSE')
    expect(inputOf({ t: 'text', v: 'plain' })).toBe('plain')
  })
  it('protects text that would be read as something else', () => {
    for (const text of ['007', 'true', ' ', "'quoted", '1e3', '-2.5', '']) {
      expect(inputOf({ t: 'text', v: text })).toBe(`'${text}`)
    }
  })
})

describe('formulas', () => {
  it('shows the value a formula gave, and edits the formula', () => {
    const sum = { t: 'int', v: 42, f: '=SUM(A1:A2)' } as const
    expect(show(sum)).toBe('42')
    expect(alignment(sum)).toBe('right')
    expect(inputOf(sum)).toBe('=SUM(A1:A2)')
    expect(formulaOf(sum)).toBe('=SUM(A1:A2)')
    expect(formulaOf({ t: 'int', v: 1 })).toBeNull()
    expect(formulaOf(null)).toBeNull()
  })
  it('shows an error by its code, in the middle', () => {
    const broken = { t: 'error', v: '#DIV/0!', f: '=1/0' } as const
    expect(show(broken)).toBe('#DIV/0!')
    expect(alignment(broken)).toBe('center')
    expect(inputOf(broken)).toBe('=1/0')
  })
  it('keeps text that looks like a formula as text', () => {
    expect(inputOf({ t: 'text', v: '=1+1' })).toBe("'=1+1")
    expect(inputOf({ t: 'text', v: '  =x' })).toBe("'  =x")
  })
})
