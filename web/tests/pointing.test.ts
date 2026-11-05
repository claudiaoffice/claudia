import { describe, expect, it } from 'vitest'
import { pointTo, referencesIn, refOf, sheetPrefix, slotAt } from '~/lib/pointing'

const SIZE = { rows: 100, cols: 50 }
const end = (text: string) => slotAt(text, text.length)

describe('where a picked reference may go', () => {
  it('after an opening bracket, a comma, an operator or the equals sign', () => {
    for (const text of ['=', '=SUM(', '=SUM(A1,', '=A1+', '=A1-', '=2*', '=A1/', '=2^', '="a"&', '=IF(A1>', '=IF(A1>=', '=IF(A1<>', '=-']) {
      expect(end(text), text).toEqual({ start: text.length, end: text.length })
    }
  })
  it('after spaces that follow such a character', () => {
    expect(end('=SUM( ')).toEqual({ start: 6, end: 6 })
  })
  it('replaces the reference just before the caret, whatever its shape', () => {
    expect(end('=SUM(A1')).toEqual({ start: 5, end: 7 })
    expect(end('=SUM(A1:B2')).toEqual({ start: 5, end: 10 })
    expect(end('=SUM($A$1:B$2')).toEqual({ start: 5, end: 13 })
    expect(end('=SUM(B:B')).toEqual({ start: 5, end: 8 })
    expect(end('=SUM(2:3')).toEqual({ start: 5, end: 8 })
    expect(end('=A1+Other!B2:B3')).toEqual({ start: 4, end: 15 })
    expect(end("=A1+'My sheet'!B2")).toEqual({ start: 4, end: 17 })
  })
  it('nowhere after a name, a number, a closing bracket, a percent sign or a finished text', () => {
    for (const text of ['=SUM', '=SUM(A1)', '=12', '=12%', '="a"', '=A1 ', '=TRUE']) expect(end(text), text).toBeNull()
  })
  it('nowhere inside a text', () => {
    expect(end('="a,')).toBeNull()
    expect(end('=A1&"(')).toBeNull()
    expect(end('="a""(')).toBeNull() // (a doubled quote stays inside the text)
    expect(end('="a"&')).not.toBeNull()
  })
  it('nowhere unless it is a formula', () => {
    expect(end('SUM(')).toBeNull()
    expect(end("'=SUM(")).toBeNull()
    expect(end('')).toBeNull()
  })
  it('in the middle of the text, between brackets', () => {
    expect(slotAt('=SUM()', 5)).toEqual({ start: 5, end: 5 })
    expect(slotAt('=SUM(A1,)', 8)).toEqual({ start: 8, end: 8 })
    expect(slotAt('=SUM(A1)+B1', 7)).toEqual({ start: 5, end: 7 })
  })
  it('not in the middle of a name or reference', () => {
    expect(slotAt('=SUM(A1)', 6)).toBeNull() // between A and 1
    expect(slotAt('=(A1)', 2)).toBeNull() // before A1: the caret is directly in front of a reference
  })
})

describe('putting a picked reference in', () => {
  it('inserts, and leaves the caret behind it', () => {
    expect(pointTo('=SUM(', 5, 'B2:B5')).toEqual({ text: '=SUM(B2:B5', caret: 10 })
  })
  it('replaces the previous pick when the mouse moves on or is clicked again', () => {
    expect(pointTo('=SUM(B2', 7, 'B2:B5')).toEqual({ text: '=SUM(B2:B5', caret: 10 })
    expect(pointTo('=SUM(B2:B5', 10, 'C1')).toEqual({ text: '=SUM(C1', caret: 7 })
  })
  it('keeps what follows the caret', () => {
    expect(pointTo('=SUM()+1', 5, 'A1:A3')).toEqual({ text: '=SUM(A1:A3)+1', caret: 10 })
  })
  it('works for the second argument', () => {
    expect(pointTo('=SUMIF(A1:A9,"x",', 17, 'B1:B9')).toEqual({ text: '=SUMIF(A1:A9,"x",B1:B9', caret: 22 })
  })
  it('does nothing where nothing may go', () => {
    expect(pointTo('=SUM(A1)', 8, 'B1')).toBeNull()
  })
})

describe('how a pick is written', () => {
  it('writes a cell, a range from any corner, a whole column and a whole row', () => {
    expect(refOf({ row: 1, col: 1, row2: 1, col2: 1 }, SIZE)).toBe('B2')
    expect(refOf({ row: 4, col: 2, row2: 1, col2: 1 }, SIZE)).toBe('B2:C5')
    expect(refOf({ row: 0, col: 1, row2: 99, col2: 1 }, SIZE)).toBe('B:B')
    expect(refOf({ row: 0, col: 1, row2: 99, col2: 3 }, SIZE)).toBe('B:D')
    expect(refOf({ row: 2, col: 0, row2: 3, col2: 49 }, SIZE)).toBe('3:4')
  })
  it('does not write the whole sheet', () => {
    expect(refOf({ row: 0, col: 0, row2: 99, col2: 49 }, SIZE)).toBeNull()
  })
  it('names the sheet when asked to', () => {
    expect(refOf({ row: 0, col: 0, row2: 1, col2: 0 }, SIZE, 'Budget!')).toBe('Budget!A1:A2')
  })
  it('quotes a sheet name only when it needs to', () => {
    expect(sheetPrefix('Budget')).toBe('Budget!')
    expect(sheetPrefix('My sheet')).toBe("'My sheet'!")
    expect(sheetPrefix('A1')).toBe("'A1'!")
    expect(sheetPrefix('2027')).toBe("'2027'!")
    expect(sheetPrefix("Bob's")).toBe("'Bob''s'!")
    expect(sheetPrefix('true')).toBe("'true'!")
  })
})

describe('the references of a formula', () => {
  it('finds each with its place in the text and the cells it covers', () => {
    const found = referencesIn('=SUM(A1:B2)+$C$3+Other!D4')
    expect(found.map((r) => [r.start, r.end, r.sheet, r.r0, r.c0, r.r1, r.c1])).toEqual([
      [5, 10, null, 0, 0, 1, 1],
      [12, 16, null, 2, 2, 2, 2],
      [17, 25, 'Other', 3, 3, 3, 3],
    ])
  })
  it('reads whole columns and rows', () => {
    const [column, row] = referencesIn('=SUM(B:C)+SUM(2:3)')
    expect([column!.r0, column!.c0, column!.r1 > 1000, column!.c1]).toEqual([0, 1, true, 2])
    expect([row!.r0, row!.c0, row!.r1, row!.c1 > 100]).toEqual([1, 0, 2, true])
  })
  it('unquotes sheet names', () => {
    expect(referencesIn("='Bob''s sheet'!A1")[0]!.sheet).toBe("Bob's sheet")
  })
  it('ignores names, function names and text', () => {
    expect(referencesIn('=LOG10(100)+ATAN2(1,1)&"A1"&TRUE')).toEqual([])
  })
  it('is empty for what is no formula', () => {
    expect(referencesIn('A1')).toEqual([])
  })
})
