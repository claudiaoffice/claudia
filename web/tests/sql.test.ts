import { describe, expect, it } from 'vitest'
import { insertAt, previewCell, previewSummary, queryOfFormula } from '~/lib/sql'

describe('the query in a cell', () => {
  it('reads a formula that is only a query', () => {
    expect(queryOfFormula('=SQL("SELECT 1")')).toBe('SELECT 1')
    expect(queryOfFormula('= sql ( "SELECT Region FROM Sales" ) ')).toBe('SELECT Region FROM Sales')
  })
  it('takes the doubled quotes of the string back', () => {
    expect(queryOfFormula('=SQL("SELECT ""Unit price"" FROM Sales")')).toBe('SELECT "Unit price" FROM Sales')
  })
  it('keeps a query over several lines', () => {
    expect(queryOfFormula('=SQL("SELECT 1\nFROM t")')).toBe('SELECT 1\nFROM t')
  })
  it('leaves other formulas alone', () => {
    expect(queryOfFormula('=SQL("SELECT ?", A1)')).toBeNull()
    expect(queryOfFormula('=SUM(A1:A3)')).toBeNull()
    expect(queryOfFormula('=1+SQL("SELECT 1")')).toBeNull()
    expect(queryOfFormula(null)).toBeNull()
    expect(queryOfFormula(undefined)).toBeNull()
  })
})

describe('typing words into the query', () => {
  it('puts a word at the caret and moves the caret behind it', () => {
    expect(insertAt('SELECT  FROM Sales', 7, 'Region')).toEqual({ text: 'SELECT Region FROM Sales', caret: 13 })
  })
  it('replaces a selection', () => {
    expect(insertAt('SELECT * FROM Sales', 7, 'Region', 8)).toEqual({ text: 'SELECT Region FROM Sales', caret: 13 })
  })
  it('keeps the caret in the text', () => {
    expect(insertAt('ab', 99, 'c')).toEqual({ text: 'abc', caret: 3 })
    expect(insertAt('ab', -4, 'c')).toEqual({ text: 'cab', caret: 1 })
  })
})

describe('what the preview says', () => {
  it('counts rows and time', () => {
    expect(previewSummary(1, 0.4, false)).toBe('1 row · < 1 ms')
    expect(previewSummary(12345, 12.6, false)).toBe('12,345 rows · 13 ms')
    expect(previewSummary(100000, 1000, true)).toBe('100,000 rows+ · 1000 ms')
  })
  it('writes each kind of value', () => {
    expect([null, true, false, 3, 'x'].map(previewCell)).toEqual(['', 'TRUE', 'FALSE', '3', 'x'])
  })
})
