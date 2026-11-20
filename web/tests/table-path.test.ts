import { describe, expect, it } from 'vitest'
import { endsWithTable, pastTable, tableAbove, tableBelow, type PathBlock } from '~/lib/table-path'

// "Before" with two tables after it, then "After"; and a text that ends with a table
const TWO: PathBlock[] = [
  { id: 'b1', length: 6, tables: ['o1', 'o2'] },
  { id: 'b2', length: 5, tables: [] },
]
const AT_THE_END: PathBlock[] = [
  { id: 'b1', length: 6, tables: [] },
  { id: 'b2', length: 5, tables: ['o1'] },
]

describe('where the caret goes when it leaves a table (D1330, D1331)', () => {
  it('after: into the next table of the same paragraph, else to the start of the next paragraph', () => {
    expect(pastTable(TWO, 'o1', 'after')).toEqual({ kind: 'table', object: 'o2', where: 'first' })
    expect(pastTable(TWO, 'o2', 'after')).toEqual({ kind: 'text', block: 'b2', offset: 0 })
  })

  it('after the table that ends the text: a paragraph is to be made after its paragraph', () => {
    expect(pastTable(AT_THE_END, 'o1', 'after')).toEqual({ kind: 'new', after: 'b2' })
  })

  it('before: into the last row of the table before it, else to the end of the paragraph it hangs from', () => {
    expect(pastTable(TWO, 'o2', 'before')).toEqual({ kind: 'table', object: 'o1', where: 'lastRow' })
    expect(pastTable(TWO, 'o1', 'before')).toEqual({ kind: 'text', block: 'b1', offset: 6 })
  })

  it('a table that is not on the path goes nowhere', () => {
    expect(pastTable(TWO, 'o9', 'after')).toBeNull()
  })
})

describe('which table the words lead into', () => {
  it('down from a paragraph: its first table; up from the next paragraph: the last table of the one before', () => {
    expect(tableBelow(TWO, 'b1')).toBe('o1')
    expect(tableBelow(TWO, 'b2')).toBeNull()
    expect(tableAbove(TWO, 'b2')).toBe('o2')
    expect(tableAbove(TWO, 'b1')).toBeNull()
  })

  it('knows when the text ends with a table', () => {
    expect(endsWithTable(AT_THE_END)).toBe(true)
    expect(endsWithTable(TWO)).toBe(false)
    expect(endsWithTable([])).toBe(false)
  })
})
