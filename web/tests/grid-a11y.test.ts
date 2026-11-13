import { describe, expect, it } from 'vitest'
import { ariaColCount, ariaRowCount, cellDomId, cellName, colIndexOf, rowIndexOf, selectionAnnouncement } from '~/lib/grid-a11y'

const plain = { ref: 'B3', text: '12', kind: 'int', formula: false, spill: false, error: null, alternatives: [], outcome: null, role: null }

describe('cellName: what a screen reader says on arriving in a cell', () => {
  it('says the address, then the value', () => {
    expect(cellName(plain)).toBe('B3, 12')
  })
  it('says an empty cell is empty, rather than saying nothing at all', () => {
    expect(cellName({ ...plain, text: '', kind: '' })).toBe('B3, empty')
    expect(cellName(null, 'B3')).toBe('B3, empty')
  })
  it('says a calculated value is calculated, because the value alone hides that it will change', () => {
    expect(cellName({ ...plain, formula: true })).toBe('B3, 12, formula')
  })
  it('says an error as an error and gives its reason when there is one', () => {
    expect(cellName({ ...plain, text: '#DIV/0!', kind: 'error', error: 'division by zero' })).toBe('B3, error #DIV/0!: division by zero')
    expect(cellName({ ...plain, text: '#REF!', kind: 'error', error: '' })).toBe('B3, error #REF!')
  })
  it('says a cell of a query result is one, since it cannot be typed into', () => {
    expect(cellName({ ...plain, spill: true })).toBe('B3, 12, part of a result')
  })
  it('lists alternatives and the outcome caption, which the dots and chips only show to the eye', () => {
    expect(cellName({ ...plain, text: '', alternatives: ['800', '1000'] })).toBe('B3, alternatives: 800, 1000')
    expect(cellName({ ...plain, outcome: 'median 5, from 2 to 9' })).toBe('B3, 12, median 5, from 2 to 9')
  })
  it('says the part a cell plays in a followed computation', () => {
    expect(cellName({ ...plain, role: 'Result of the computation' })).toBe('B3, 12, Result of the computation')
  })
})

describe('selectionAnnouncement: said when the selection is more than the one cell', () => {
  const sel = (row: number, col: number, row2: number, col2: number) => ({ row, col, row2, col2 })
  it('is nothing for one cell (the active cell speaks for itself)', () => {
    expect(selectionAnnouncement(sel(2, 1, 2, 1), 10_000, 702)).toBeNull()
  })
  it('names a block by its corners and its size, whichever way it was dragged', () => {
    expect(selectionAnnouncement(sel(0, 0, 2, 2), 10_000, 702)).toBe('A1:C3 selected, 9 cells')
    expect(selectionAnnouncement(sel(2, 2, 0, 0), 10_000, 702)).toBe('A1:C3 selected, 9 cells')
  })
  it('says a whole column, a whole row, and everything, as such', () => {
    expect(selectionAnnouncement(sel(0, 1, 9_999, 1), 10_000, 702)).toBe('Column B selected')
    expect(selectionAnnouncement(sel(4, 0, 4, 701), 10_000, 702)).toBe('Row 5 selected')
    expect(selectionAnnouncement(sel(0, 0, 9_999, 701), 10_000, 702)).toBe('All cells selected')
  })
})

describe('the numbers a grid needs to say where it is', () => {
  it('counts the header row and the row-number column, which are part of the grid', () => {
    expect(ariaRowCount(10_000)).toBe(10_001)
    expect(ariaColCount(702)).toBe(703)
  })
  it('numbers from one, with the headers taking the first row and column', () => {
    expect(rowIndexOf(0)).toBe(2)
    expect(colIndexOf(0)).toBe(2)
  })
  it('gives each cell an id that no other grid on the page shares, and the same one every time', () => {
    expect(cellDomId('g1', 2, 1)).toBe('g1-r2c1')
    expect(cellDomId('g2', 2, 1)).not.toBe(cellDomId('g1', 2, 1))
  })
})
