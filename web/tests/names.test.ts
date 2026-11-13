import { describe, expect, it } from 'vitest'
import { parseCell } from '~/lib/cells'
import {
  applyCompletion,
  blockerOf,
  completionsAt,
  columnPurpose,
  didYouMean,
  draftOf,
  guessHeader,
  escapeColumn,
  nameAt,
  nameBoxAction,
  nameProblem,
  quoteIdentifier,
  referLabel,
  replaceWord,
  regionLabel,
  resolveName,
  structuredRef,
  tableAt,
  tableBoxes,
  visibleNames,
  withPurpose,
  type NameInfo,
} from '~/lib/names'

function info(name: string, fields: Partial<NameInfo> = {}): NameInfo {
  return {
    name,
    scope: null,
    kind: 'range',
    header: true,
    grows: true,
    purpose: 'data',
    column_purposes: [],
    sheet: 's1',
    sheet_name: 'Data',
    region: { sheet: 's1', row0: 0, col0: 0, row1: 3, col1: 3 },
    a1: 'Data!A1:D4',
    anchor: null,
    columns: [],
    rows: 3,
    ...fields,
  }
}

describe('what a name may be', () => {
  it('accepts words and refuses what a formula could not tell from something else', () => {
    expect(nameProblem('Sales')).toBeNull()
    expect(nameProblem('Q1.Revenue_2')).toBeNull()
    expect(nameProblem('Übersicht')).toBeNull()
    expect(nameProblem('')).toMatch(/some text/)
    expect(nameProblem('2024')).toMatch(/starts with a letter/)
    expect(nameProblem('Unit price')).toMatch(/starts with a letter/)
    expect(nameProblem('true')).toMatch(/value/)
    expect(nameProblem('B3')).toMatch(/cell/)
    expect(nameProblem('ZZZZ9')).toBeNull() // four letters is no column
    expect(nameProblem('x'.repeat(256))).toMatch(/at most 255/)
  })
})

describe('which names are in view', () => {
  const names = [info('Sales'), info('sales', { scope: 's2' }), info('Costs', { scope: 's1' }), info('Alpha')]
  it('lets a sheet own name shadow the workbook wide one, sorted by text', () => {
    expect(visibleNames(names, 's2').map((n) => [n.name, n.scope])).toEqual([
      ['Alpha', null],
      ['sales', 's2'],
    ])
    expect(visibleNames(names, 's1').map((n) => n.name)).toEqual(['Alpha', 'Costs', 'Sales'])
  })
  it('resolves a text to the sheet own name first', () => {
    expect(resolveName(names, 's2', 'SALES')?.scope).toBe('s2')
    expect(resolveName(names, 's1', 'SALES')?.scope).toBeNull()
    expect(resolveName(names, 's1', 'nothing')).toBeNull()
  })
})

describe('what is under the cursor', () => {
  const sales = info('Sales', { purpose: 'input', column_purposes: [[3, 'calc']] })
  const names = [sales]
  it('finds a name when the selection is exactly its cells', () => {
    expect(nameAt(names, 's1', 0, 0, 3, 3)?.name).toBe('Sales')
    expect(nameAt(names, 's1', 0, 0, 2, 3)).toBeNull()
    expect(nameAt(names, 's2', 0, 0, 3, 3)).toBeNull()
  })
  it('finds the table of a cell, its header row and the purpose of its column', () => {
    expect(tableAt(names, 's1', 0, 1)).toMatchObject({ header: true, purpose: 'input' })
    expect(tableAt(names, 's1', 2, 3)).toMatchObject({ header: false, purpose: 'calc' })
    expect(tableAt(names, 's1', 4, 0)).toBeNull()
    expect(tableAt(names, 's2', 1, 1)).toBeNull()
  })
  it('knows no header row for a range without one', () => {
    const plain = info('Plain', { header: false })
    expect(tableAt([plain], 's1', 0, 0)?.header).toBe(false)
  })
  it('takes the column purpose before the table one', () => {
    expect(columnPurpose(sales, 3)).toBe('calc')
    expect(columnPurpose(sales, 0)).toBe('input')
  })
  it('skips a result that has no table right now', () => {
    expect(tableAt([info('Gone', { region: null, a1: null })], 's1', 0, 0)).toBeNull()
  })
})

describe('text the editors write', () => {
  it('escapes the characters of a column that a reference cannot hold', () => {
    expect(escapeColumn('Unit price')).toBe('Unit price')
    expect(escapeColumn("a[1]#'")).toBe("a'[1']'#''")
    expect(structuredRef('Sales', 'Amount')).toBe('Sales[Amount]')
    expect(structuredRef('Sales', 'Q[1]')).toBe("Sales[Q'[1']]")
  })
  it('quotes a SQL identifier only when it has to', () => {
    expect(quoteIdentifier('Amount')).toBe('Amount')
    expect(quoteIdentifier('Unit price')).toBe('"Unit price"')
    expect(quoteIdentifier('say "hi"')).toBe('"say ""hi"""')
    expect(quoteIdentifier('1st')).toBe('"1st"')
  })
  it('labels where a name lives', () => {
    expect(regionLabel({ sheet: 's1', row0: 0, col0: 0, row1: 3, col1: 3 })).toBe('A1:D4')
    expect(regionLabel(null)).toBeNull()
    expect(referLabel(info('Sales'))).toBe('Data!A1:D4')
    expect(referLabel(info('R', { a1: null, region: null, anchor: { sheet: 's1', row: 5, col: 0 } }))).toBe('Data!A6 (no table right now)')
    expect(referLabel(info('X', { a1: null, region: null }))).toBe('—')
  })
})

describe('what the Name Box does with what was typed', () => {
  const names = [info('Sales'), info('ByRegion', { kind: 'result', anchor: { sheet: 's1', row: 5, col: 0 } }), info('Gone', { kind: 'result', region: null, a1: null })]
  const act = (typed: string, one = true) => nameBoxAction(typed, 's1', names, one, parseCell)
  it('goes to a cell', () => {
    expect(act('b3')).toEqual({ kind: 'cell', row: 2, col: 1 })
  })
  it('selects a range of cells', () => {
    expect(act('A1:C4')).toEqual({ kind: 'range', row: 0, col: 0, row2: 3, col2: 2 })
    expect(act('A1:nope')).toMatchObject({ kind: 'problem' })
  })
  it('goes to a name, and to a name of a result even when more is selected', () => {
    expect(act('sales')).toMatchObject({ kind: 'goto' })
    expect(act('ByRegion', false)).toMatchObject({ kind: 'goto' })
  })
  it('offers to move a name of cells to a bigger selection', () => {
    expect(act('Sales', false)).toMatchObject({ kind: 'redefine' })
  })
  it('says when a result has no cells', () => {
    expect(act('Gone')).toEqual({ kind: 'problem', message: 'Gone has no cells right now' })
  })
  it('names the selection with a new word and says why a typo cannot be a name', () => {
    expect(act('Costs')).toEqual({ kind: 'define', name: 'Costs', scope: null })
    expect(act('not a name')).toMatchObject({ kind: 'problem' })
  })
})

describe('what is drawn under the cells of a table', () => {
  const view = { r0: 0, r1: 20, c0: 0, c1: 10 }
  const sales = info('Sales', { purpose: 'input', column_purposes: [[3, 'calc']] })
  it('draws a frame, a header and a body per column, and a ghost row below a growing table', () => {
    const boxes = tableBoxes([sales], 's1', view)
    expect(boxes.filter((b) => b.kind === 'frame')).toHaveLength(1)
    expect(boxes.filter((b) => b.kind === 'head')).toHaveLength(4)
    const bodies = boxes.filter((b) => b.kind === 'column')
    expect(bodies.map((b) => [b.c0, b.r0, b.r1, b.purpose])).toEqual([[0, 1, 3, 'input'], [1, 1, 3, 'input'], [2, 1, 3, 'input'], [3, 1, 3, 'calc']])
    expect(boxes.find((b) => b.kind === 'ghost')).toMatchObject({ r0: 4, c0: 0, c1: 3 })
  })
  it('has no header over a range without one, and no ghost row when it does not grow', () => {
    const plain = info('Plain', { header: false, grows: false })
    const boxes = tableBoxes([plain], 's1', view)
    expect(boxes.some((b) => b.kind === 'head' || b.kind === 'ghost')).toBe(false)
    expect(boxes.find((b) => b.kind === 'column')?.r0).toBe(0)
  })
  it('gives a query result no ghost row', () => {
    const result = info('R', { kind: 'result', purpose: 'result', anchor: { sheet: 's1', row: 0, col: 0 } })
    expect(tableBoxes([result], 's1', view).some((b) => b.kind === 'ghost')).toBe(false)
  })
  it('leaves out what is off screen, other sheets and results without cells, and clips a tall table to the view', () => {
    expect(tableBoxes([sales], 's1', { r0: 50, r1: 60, c0: 0, c1: 10 })).toEqual([])
    expect(tableBoxes([sales], 's2', view)).toEqual([])
    expect(tableBoxes([info('Gone', { region: null, a1: null })], 's1', view)).toEqual([])
    const tall = info('Tall', { region: { sheet: 's1', row0: 0, col0: 0, row1: 100_000, col1: 0 }, grows: false })
    const frame = tableBoxes([tall], 's1', view).find((b) => b.kind === 'frame')!
    expect(frame.r1).toBe(21)
  })
  it('draws nothing of the columns that are out of view', () => {
    expect(tableBoxes([sales], 's1', { r0: 0, r1: 20, c0: 2, c1: 2 }).filter((b) => b.kind === 'column').map((b) => b.c0)).toEqual([2])
  })
})

describe('mending a query', () => {
  const sales = info('Sales', { columns: [{ name: 'Region', type: 'text', purpose: 'data' }, { name: 'Revenue', type: 'real', purpose: 'data' }] })
  it('suggests the column that was meant', () => {
    expect(didYouMean('no such column: Revnue', [sales])).toEqual({ wrong: 'Revnue', right: 'Revenue' })
    expect(didYouMean('no such column: Sales.regoin', [sales])).toEqual({ wrong: 'regoin', right: 'Region' })
    expect(didYouMean('no such column: Amnt', [info('Sales', { columns: [{ name: 'Amount', type: 'real', purpose: 'data' }] })])).toEqual({ wrong: 'Amnt', right: 'Amount' })
  })
  it('suggests nothing when nothing is near or the problem is another', () => {
    expect(didYouMean('no such column: Banana', [sales])).toBeNull()
    expect(didYouMean('no such table: Sale', [sales])).toBeNull()
    expect(didYouMean('no such column: region', [sales])).toBeNull() // same word, only another case: SQL accepts it
  })
  it('replaces the wrong word, whole words only, quoting the right one when it needs it', () => {
    expect(replaceWord('SELECT Revnue, Revnue2 FROM Sales', 'Revnue', 'Revenue')).toBe('SELECT Revenue, Revnue2 FROM Sales')
    expect(replaceWord('SELECT "Unit prise" FROM Sales', 'Unit prise', 'Unit price')).toBe('SELECT "Unit price" FROM Sales')
    expect(replaceWord('SELECT Prise FROM Sales', 'Prise', 'Unit price')).toBe('SELECT "Unit price" FROM Sales')
  })
  it('reads the cell that is in the way of a result', () => {
    expect(blockerOf('SalesByRegion needs A3:B7, but B5 holds a value', parseCell)).toEqual([4, 1])
    expect(blockerOf('which does not fit on the sheet', parseCell)).toBeNull()
  })
})

describe('what the define popover starts from and sends', () => {
  it('reads a header when the first row is all text and there is more below', () => {
    expect(guessHeader([['text', 'text'], ['text', 'int']], [['Region', 'Units'], ['North', '10']])).toBe(true)
    expect(guessHeader([['text', 'int'], ['text', 'int']], [['Region', '1'], ['North', '10']])).toBe(false)
    expect(guessHeader([['text', null], ['text', 'int']], [['Region', ''], ['North', '10']])).toBe(false)
    expect(guessHeader([['text', 'text']], [['a', 'b']])).toBe(false)
  })
  it('sends a table that grows only when it has a header', () => {
    const region = { sheet: 's1', row0: 0, col0: 0, row1: 3, col1: 3 }
    expect(draftOf({ name: ' Sales ', scope: null, region, header: true, grows: true, purpose: 'input' })).toEqual({
      name: 'Sales', scope: null, range: region, header: true, grows: true, purpose: 'input',
    })
    expect(draftOf({ name: 'Plain', scope: 's1', region, header: false, grows: true, purpose: 'data' }).grows).toBe(false)
  })
  it('changes one column or the whole table', () => {
    const table = info('Sales', { purpose: 'input', column_purposes: [[3, 'calc']] })
    expect(withPurpose(table, 1, 'result')).toMatchObject({ purpose: 'input', column_purposes: [[3, 'calc'], [1, 'result']] })
    expect(withPurpose(table, 3, 'input').column_purposes).toEqual([]) // the table's own purpose again
    expect(withPurpose(table, null, 'data')).toMatchObject({ purpose: 'data', column_purposes: [] })
    expect(withPurpose(table, 0, 'calc').range).toEqual(table.region)
  })
})

describe('finishing what is typed in a formula', () => {
  const sales = info('Sales', {
    rows: 3,
    columns: [
      { name: 'Region', type: 'text', purpose: 'data' },
      { name: 'Unit price', type: 'real', purpose: 'data' },
      { name: 'Amount', type: 'real', purpose: 'data' },
    ],
  })
  const costs = info('Costs', { header: false })
  const gone = info('Gone', { region: null, a1: null })
  const names = [sales, costs, gone]
  const at = (text: string, caret = text.length) => completionsAt(text, caret, names, 's1')

  it('offers the columns of a table after its bracket', () => {
    expect(at('=SUM(Sales[')?.items.map((i) => i.label)).toEqual(['Region', 'Unit price', 'Amount', '#All', '#Data', '#Headers', '@'])
    expect(at('=SUM(Sales[Am')).toMatchObject({ from: 11, items: [{ label: 'Amount', insert: 'Amount' }] })
  })
  it('offers the special items after # and @, and only those', () => {
    expect(at('=Sales[#')?.items.map((i) => i.label)).toEqual(['#All', '#Data', '#Headers'])
    expect(at('=Sales[@')?.items.map((i) => i.label)).toEqual(['Region', 'Unit price', 'Amount'])
  })
  it('offers the names that start with the word', () => {
    expect(at('=SUM(Sa')?.items).toEqual([{ label: 'Sales', insert: 'Sales', detail: 'table · 3 rows', closes: false }])
    expect(at('=C')?.items[0]).toMatchObject({ label: 'Costs', detail: 'cells' })
    expect(at('=1+Sa')?.from).toBe(3)
  })
  it('offers nothing where a name cannot be', () => {
    expect(at('Sales[')).toBeNull() // not a formula
    expect(at('="Sa')).toBeNull() // inside a text
    expect(at('=Gone')).toBeNull() // a name without cells, complete anyway
    expect(at('=Sales')).toBeNull() // already the whole name
    expect(at('=Nothing[')).toBeNull()
    expect(at('=A1+')).toBeNull()
    expect(at('=Data!Sa')).toBeNull() // after a sheet
    expect(at('=Sales[Zzz')).toBeNull()
  })
  it('puts the finished word in and closes the bracket of a column', () => {
    const found = at('=SUM(Sales[Am')!
    expect(applyCompletion('=SUM(Sales[Am', 13, found, found.items[0]!)).toEqual({ text: '=SUM(Sales[Amount]', caret: 18 })
    const open = '=SUM(Sales[Am)'
    expect(applyCompletion(open, 13, found, found.items[0]!)).toEqual({ text: '=SUM(Sales[Amount])', caret: 18 })
    const closed = '=SUM(Sales[Am])'
    expect(applyCompletion(closed, 13, found, found.items[0]!)).toEqual({ text: '=SUM(Sales[Amount])', caret: 18 })
    const all = at('=Sales[#')!
    expect(applyCompletion('=Sales[#', 8, all, all.items[0]!)).toEqual({ text: '=Sales[#All]', caret: 12 })
    const row = at('=Sales[@')!
    expect(applyCompletion('=Sales[@', 8, row, row.items[1]!)).toEqual({ text: "=Sales[@Unit price]", caret: 19 })
  })
  it('escapes a column that has a bracket in it, and leaves a name without a bracket', () => {
    const odd = info('Odd', { columns: [{ name: 'Q[1]', type: 'int', purpose: 'data' }] })
    const found = completionsAt('=Odd[Q', 6, [odd], 's1')!
    expect(found.items[0]!.insert).toBe("Q'[1']")
    const word = at('=SUM(Sa')!
    expect(applyCompletion('=SUM(Sa', 7, word, word.items[0]!)).toEqual({ text: '=SUM(Sales', caret: 10 })
  })
})
