import { describe, expect, it } from 'vitest'
import { boxId, columnName, columnPlace, gridOf, isBoxId, leaveSide, mergeRect, oneLine, rowPlace, stepBox, tableOf, withEvent, type TableEvent, type TableInfo } from '~/lib/tables'

function table(words: string[][], extra: Partial<TableInfo> = {}): TableInfo {
  return {
    format: 1,
    id: 't1',
    columns: (words[0] ?? []).map((_, i) => ({ id: `c${i + 1}`, kind: 'text', total: null, width: null })),
    rows: words.map((_, i) => `r${i + 1}`),
    entries: words.flatMap((line, r) => line.map((text, c): TableInfo['entries'][number] => [`r${r + 1}`, `c${c + 1}`, { style: '', text }])).filter(([, , p]) => p.text),
    merges: [],
    header_rows: 1,
    banded: false,
    look: 'rules',
    placement: 'flow',
    width: null,
    next_row: words.length,
    next_col: (words[0] ?? []).length,
    used_by: ['o1'],
    totals: {},
    ...extra,
  }
}
const GARDEN = [
  ['Site', 'Beds', 'Harvest'],
  ['Greenhouse', '12', '184,5'],
  ['North plot', '20', '231,0'],
]

describe('the rows and boxes of a table', () => {
  it('splits the header from the body and names every box by its ids', () => {
    const grid = gridOf(table(GARDEN))
    expect(grid.header.map((r) => r.map((b) => b.text))).toEqual([['Site', 'Beds', 'Harvest']])
    expect(grid.body.map((r) => r.map((b) => b.text))).toEqual([['Greenhouse', '12', '184,5'], ['North plot', '20', '231,0']])
    expect(grid.body[1]![2]!.id).toBe('t1/r3/c3')
    expect(grid.total).toBeNull()
  })

  it('shows a box that has no words as empty, and the style a person chose', () => {
    const t = table([['a', ''], ['', 'd']])
    t.entries[0] = ['r1', 'c1', { style: 'quote', text: 'a' }]
    const grid = gridOf(t)
    expect(grid.header[0]!.map((b) => [b.text, b.style])).toEqual([['a', 'quote'], ['', '']])
  })

  it('leaves out the boxes a merge covers and makes the merged one as big as the boxes it joins', () => {
    const grid = gridOf(table(GARDEN, { merges: [{ row: 'r2', col: 'c1', rows: 2, cols: 2 }] }))
    expect(grid.body[0]!.map((b) => [b.col, b.rows, b.cols])).toEqual([['c1', 2, 2], ['c3', 1, 1]])
    expect(grid.body[1]!.map((b) => b.col)).toEqual(['c3'])
  })

  it('gives the total row only when a column has a total, from the words the server derived', () => {
    const t = table(GARDEN)
    t.columns[2] = { id: 'c3', kind: 'number', total: 'sum', width: null }
    t.totals = { c3: '415,5' }
    expect(gridOf(t).total!.map((b) => b.text)).toEqual(['', '', '415,5'])
  })

  it('names a column by the last box of its header, or by its place', () => {
    const t = table([['Site', 'Beds'], ['a', '1']], { header_rows: 1 })
    expect(columnName(t, 'c2', (n) => `Column ${n}`)).toBe('Beds')
    expect(columnName(table([['', ''], ['a', '1']]), 'c2', (n) => `Column ${n}`)).toBe('Column 2')
    expect(columnName(table([['a', '1']], { header_rows: 0 }), 'c1', (n) => `Column ${n}`)).toBe('Column 1')
  })
})

describe('steps between boxes', () => {
  const t = table(GARDEN)
  it('goes on with Tab, back with Shift+Tab, and leaves the last box for a new row', () => {
    expect(stepBox(t, { row: 'r1', col: 'c1' }, 'next')).toEqual({ row: 'r1', col: 'c2' })
    expect(stepBox(t, { row: 'r1', col: 'c3' }, 'next')).toEqual({ row: 'r2', col: 'c1' })
    expect(stepBox(t, { row: 'r3', col: 'c3' }, 'next')).toBe('end')
    expect(stepBox(t, { row: 'r2', col: 'c1' }, 'prev')).toEqual({ row: 'r1', col: 'c3' })
    expect(stepBox(t, { row: 'r1', col: 'c1' }, 'prev')).toBeNull()
  })

  it('moves with the arrows, stops at the edge, and goes round a merge', () => {
    expect(stepBox(t, { row: 'r2', col: 'c2' }, 'down')).toEqual({ row: 'r3', col: 'c2' })
    expect(stepBox(t, { row: 'r2', col: 'c2' }, 'up')).toEqual({ row: 'r1', col: 'c2' })
    expect(stepBox(t, { row: 'r1', col: 'c2' }, 'up')).toBeNull()
    expect(stepBox(t, { row: 'r2', col: 'c3' }, 'right')).toBeNull()
    const merged = table(GARDEN, { merges: [{ row: 'r2', col: 'c1', rows: 2, cols: 2 }] })
    expect(stepBox(merged, { row: 'r1', col: 'c2' }, 'down')).toEqual({ row: 'r2', col: 'c1' })
    expect(stepBox(merged, { row: 'r2', col: 'c1' }, 'right')).toEqual({ row: 'r2', col: 'c3' })
    expect(stepBox(merged, { row: 'r2', col: 'c1' }, 'down')).toBeNull()
    expect(stepBox(t, { row: 'nope', col: 'c1' }, 'next')).toBeNull()
  })
})

describe('the ids of a table', () => {
  it('writes and recognises the id of a box, which is not a paragraph of the text', () => {
    expect(boxId('t1', 'r2', 'c3')).toBe('t1/r2/c3')
    expect(isBoxId('t1/r2/c3')).toBe(true)
    expect(isBoxId('p7')).toBe(false)
  })

  it('says what a box is made of on one line, as the server does', () => {
    expect(oneLine('a\nb\r\nc')).toBe('a b c')
  })

  it('names where an insert goes next to a row or a column', () => {
    expect(rowPlace('r2', 'above')).toEqual({ before: 'r2' })
    expect(rowPlace('r2', 'below')).toEqual({ after: 'r2' })
    expect(columnPlace('c1', 'left')).toEqual({ before: 'c1' })
    expect(columnPlace('c1', 'right')).toEqual({ after: 'c1' })
  })

  it('finds the table an object shows', () => {
    const tables = { t1: table(GARDEN) }
    expect(tableOf(tables, { kind: 'table', ref: 't1' })?.id).toBe('t1')
    expect(tableOf(tables, { kind: 'table', ref: 'gone' })).toBeNull()
    expect(tableOf(tables, { kind: 'text', ref: 't1' })).toBeNull()
  })
})

describe('what an event says', () => {
  it('puts the changed table in, keeps what the server derives until it is asked again, and drops a forgotten one', () => {
    const tables: Record<string, TableInfo> = { t1: table(GARDEN, { totals: { c3: '1' } }) }
    const { used_by: _u, totals: _t, ...definition } = table([['x']])
    const event: TableEvent = { type: 'table', id: 't1', definition }
    withEvent(tables, event)
    expect(tables.t1!.rows).toEqual(['r1'])
    expect(tables.t1!.used_by).toEqual(['o1'])
    expect(tables.t1!.totals).toEqual({ c3: '1' })
    withEvent(tables, { type: 'table', id: 't1', definition: null })
    expect(tables.t1).toBeUndefined()
  })
})

// D1330: the keys that take the caret out of a table, and to which side
describe('which key leaves a table, and to which side', () => {
  const side = (t: TableInfo, row: string, col: string, step: Parameters<typeof leaveSide>[2]) => leaveSide(t, { row, col }, step)

  it('the down arrow in any box of the last row leaves after the table, the up arrow in the first row before it', () => {
    const t = table(GARDEN)
    expect(side(t, 'r3', 'c1', 'down')).toBe('after')
    expect(side(t, 'r3', 'c2', 'down')).toBe('after')
    expect(side(t, 'r1', 'c3', 'up')).toBe('before')
  })

  it('right leaves only from the very last box, left only from the very first', () => {
    const t = table(GARDEN)
    expect(side(t, 'r3', 'c3', 'right')).toBe('after')
    expect(side(t, 'r2', 'c3', 'right')).toBeNull()
    expect(side(t, 'r1', 'c1', 'left')).toBe('before')
    expect(side(t, 'r2', 'c1', 'left')).toBeNull()
  })

  it('does not leave where a box is still to go to, nor with Tab, which adds a row in the last box', () => {
    const t = table(GARDEN)
    expect(side(t, 'r2', 'c1', 'down')).toBeNull()
    expect(side(t, 'r2', 'c1', 'up')).toBeNull()
    expect(side(t, 'r3', 'c3', 'next')).toBeNull()
    expect(side(t, 'r1', 'c1', 'prev')).toBeNull()
  })

  it('a box joined over the last two rows leaves downwards too', () => {
    const t = table(GARDEN, { merges: [{ row: 'r2', col: 'c1', rows: 2, cols: 1 }] })
    expect(side(t, 'r2', 'c1', 'down')).toBe('after')
  })
})

describe('what Merge Cells joins', () => {
  const at = (t: TableInfo, row: string, col: string) => mergeRect(t, { row, col })

  it('joins a box with the one to its right, else with the one below', () => {
    const t = table(GARDEN)
    expect(at(t, 'r2', 'c1')).toEqual({ row: 'r2', col: 'c1', rows: 1, cols: 2 })
    expect(at(t, 'r2', 'c3')).toEqual({ row: 'r2', col: 'c3', rows: 2, cols: 1 })
  })

  it('has nothing to join in the last box of the last row, or when the table is one box', () => {
    expect(at(table(GARDEN), 'r3', 'c3')).toBeNull()
    expect(at(table([['x']]), 'r1', 'c1')).toBeNull()
  })

  it('never joins across the header, never joins what is joined already, and reaches over a joined neighbour', () => {
    const t = table(GARDEN, { merges: [{ row: 'r2', col: 'c2', rows: 1, cols: 2 }] })
    expect(at(t, 'r1', 'c3')).toBeNull()
    expect(at(t, 'r2', 'c2')).toBeNull()
    expect(at(t, 'r2', 'c1')).toEqual({ row: 'r2', col: 'c1', rows: 1, cols: 3 })
  })

  it('does not join a box with a taller neighbour: it goes down instead', () => {
    const t = table(GARDEN, { header_rows: 0, merges: [{ row: 'r1', col: 'c2', rows: 2, cols: 1 }] })
    expect(at(t, 'r1', 'c1')).toEqual({ row: 'r1', col: 'c1', rows: 2, cols: 1 })
    expect(at(t, 'r3', 'c2')).toEqual({ row: 'r3', col: 'c2', rows: 1, cols: 2 })
  })
})
