import { describe, expect, it } from 'vitest'
import {
  chipsOf,
  defaultAggregation,
  definitionHint,
  emptyDefinition,
  fillsLine,
  isTicked,
  moveChip,
  newSheetName,
  moveTargets,
  parsePlace,
  pivotAt,
  pivotBoxes,
  pivotLabels,
  pivotNameProblem,
  placeField,
  preselected,
  removeField,
  removeValue,
  roleAt,
  setKeep,
  setValue,
  sourceChoices,
  suggestName,
  toggleField,
  valueIndexFor,
  valueTitle,
  zoneOf,
  zonesOf,
  type PivotDefinition,
  type PivotInfo,
} from '~/lib/pivots'
import type { NameInfo } from '~/lib/names'

const LABELS = { total: 'Total', blank: '(blank)', row_header: 'Rows', sum_of: 'Sum of {field}', count_of: 'Count of {field}', average_of: 'Average of {field}', min_of: 'Min of {field}', max_of: 'Max of {field}' }

function table(name: string, fields: Partial<NameInfo> = {}): NameInfo {
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
    region: { sheet: 's1', row0: 10, col0: 0, row1: 20, col1: 5 },
    a1: 'Data!A11:F21',
    anchor: null,
    columns: [
      { name: 'Region', type: 'text', purpose: 'data' },
      { name: 'Amount', type: 'real', purpose: 'data' },
    ],
    rows: 10,
    ...fields,
  }
}

/** The pivot of mock 1: Region down, Quarter across, Sum of Amount, at A5:E11 of sheet r1. */
function pivot(fields: Partial<PivotInfo> = {}): PivotInfo {
  const definition: PivotDefinition = { ...emptyDefinition('Sales'), rows: ['Region'], columns: ['Quarter'], values: [{ field: 'Amount', aggregation: 'sum', name: '' }] }
  return {
    name: 'SalesPivot',
    definition,
    labels: LABELS,
    anchor: { sheet: 'r1', row: 4, col: 0 },
    region: { sheet: 'r1', row0: 4, col0: 0, row1: 10, col1: 4 },
    a1: 'Report!A5:E11',
    placed: true,
    error: null,
    header_rows: 2,
    header_roles: [
      ['field', 'header', 'header', 'header', 'header'],
      ['corner', 'header', 'header', 'header', 'header'],
    ],
    total_row: true,
    total_column: true,
    ...fields,
  }
}

describe('the boxes of the field panel', () => {
  const start = emptyDefinition('Sales')

  it('puts a field into a box and out of the one it was in', () => {
    const rows = placeField(start, 'Region', 'rows').definition
    expect(rows.rows).toEqual(['Region'])
    const moved = placeField(rows, 'Region', 'columns').definition
    expect(moved.rows).toEqual([])
    expect(moved.columns).toEqual(['Region'])
    expect(zoneOf(moved, 'Region')).toBe('columns')
  })

  it('finds a field without regard to case, as the engine does', () => {
    const rows = placeField(start, 'Region', 'rows').definition
    expect(zonesOf(rows, 'REGION')).toEqual(['rows'])
    expect(placeField(rows, 'region', 'filters').definition.rows).toEqual([])
  })

  it('has room for one row field and one column field, and says which one had to go', () => {
    const one = placeField(start, 'Region', 'rows').definition
    const placed = placeField(one, 'Product', 'rows')
    expect(placed.definition.rows).toEqual(['Product'])
    expect(placed.displaced).toBe('Region')
    expect(isTicked(placed.definition, 'Region')).toBe(false)
    expect(placeField(start, 'Region', 'rows').displaced).toBeNull()
  })

  it('keeps any number of filters, each keeping everything at first', () => {
    const two = placeField(placeField(start, 'Product', 'filters').definition, 'Region', 'filters').definition
    expect(two.filters).toEqual([
      { field: 'Product', keep: null },
      { field: 'Region', keep: null },
    ])
  })

  it('sums a number and counts anything else when it goes into Values, once', () => {
    expect(defaultAggregation('real')).toBe('sum')
    expect(defaultAggregation('int')).toBe('sum')
    expect(defaultAggregation('text')).toBe('count')
    expect(defaultAggregation(undefined)).toBe('count')
    const one = placeField(start, 'Amount', 'values', 'real').definition
    expect(one.values).toEqual([{ field: 'Amount', aggregation: 'sum', name: '' }])
    expect(placeField(one, 'Amount', 'values', 'real').definition).toBe(one)
  })

  it('lets a field be in Values and in a box besides', () => {
    const both = placeField(placeField(start, 'Region', 'rows').definition, 'Region', 'values', 'text').definition
    expect(zonesOf(both, 'Region')).toEqual(['rows', 'values'])
    expect(both.values[0]!.aggregation).toBe('count')
    expect(removeField(both, 'Region')).toEqual(start)
  })

  it('ticks like Excel: numbers to Values, text to Rows, then Columns, then Filters', () => {
    let def = toggleField(start, 'Amount', 'real').definition
    expect(def.values.map((v) => v.field)).toEqual(['Amount'])
    def = toggleField(def, 'Region', 'text').definition
    expect(def.rows).toEqual(['Region'])
    def = toggleField(def, 'Quarter', 'text').definition
    expect(def.columns).toEqual(['Quarter'])
    def = toggleField(def, 'Product', 'text').definition
    expect(def.filters.map((f) => f.field)).toEqual(['Product'])
  })

  it('takes a field out of every box when it is ticked off', () => {
    const def = toggleField(toggleField(start, 'Region', 'text').definition, 'Region', 'text').definition
    expect(def).toEqual(start)
  })

  it('moves a chip: a value goes out of Values, a field into Values stays where it was', () => {
    const def: PivotDefinition = {
      ...emptyDefinition('Sales'),
      rows: ['Region'],
      values: [
        { field: 'Amount', aggregation: 'sum', name: '' },
        { field: 'Amount', aggregation: 'max', name: 'Largest' },
      ],
    }
    const toColumns = moveChip(def, { zone: 'values', field: 'Amount', index: 1 }, 'columns', 'real')
    expect(toColumns.definition.values).toEqual([def.values[0]]) // only the chip that was moved
    expect(toColumns.definition.columns).toEqual(['Amount'])
    const intoValues = moveChip(def, { zone: 'rows', field: 'Region', index: 0 }, 'values', 'text')
    expect(intoValues.definition.rows).toEqual(['Region'])
    expect(intoValues.definition.values.map((v) => v.field)).toEqual(['Amount', 'Amount', 'Region'])
    expect(moveChip(def, { zone: 'rows', field: 'Region', index: 0 }, 'rows').definition).toBe(def)
  })

  it('offers every box but its own in the chip menu', () => {
    expect(moveTargets('rows')).toEqual(['filters', 'columns', 'values'])
    expect(moveTargets('values')).toEqual(['filters', 'columns', 'rows'])
  })

  it('changes one value field, or takes one chip away', () => {
    const def = placeField(placeField(start, 'Amount', 'values', 'real').definition, 'Units', 'values', 'int').definition
    const changed = setValue(def, 1, { aggregation: 'average', name: 'Mean units' })
    expect(changed.values[1]).toEqual({ field: 'Units', aggregation: 'average', name: 'Mean units' })
    expect(changed.values[0]).toEqual(def.values[0])
    expect(removeValue(changed, 0).values.map((v) => v.field)).toEqual(['Units'])
  })

  it('records which members of a filter stay in', () => {
    const def = placeField(start, 'Product', 'filters').definition
    expect(setKeep(def, 'product', ['Desk', null]).filters[0]!.keep).toEqual(['Desk', null])
    expect(setKeep(setKeep(def, 'Product', ['Desk']), 'Product', null).filters[0]!.keep).toBeNull()
  })

  it('says what is missing for there to be numbers', () => {
    expect(definitionHint(start)).toMatch(/Values/)
    expect(definitionHint(placeField(start, 'Amount', 'values', 'real').definition)).toBeNull()
  })
})

describe('the chips', () => {
  it('show a field, the title of a value, and how much of a filter stays', () => {
    const def: PivotDefinition = {
      ...emptyDefinition('Sales'),
      rows: ['Region'],
      values: [
        { field: 'Amount', aggregation: 'sum', name: '' },
        { field: 'Units', aggregation: 'average', name: 'Mean units' },
      ],
      filters: [
        { field: 'Product', keep: null },
        { field: 'Quarter', keep: ['Q1', 'Q2'] },
      ],
    }
    expect(chipsOf(def, 'rows', LABELS).map((c) => c.label)).toEqual(['Region'])
    expect(chipsOf(def, 'values', LABELS).map((c) => c.label)).toEqual(['Sum of Amount', 'Mean units'])
    expect(chipsOf(def, 'filters', LABELS).map((c) => c.detail)).toEqual(['(All)', '2 kept'])
    expect(chipsOf(def, 'values', LABELS)[1]).toMatchObject({ zone: 'values', field: 'Units', index: 1 })
    expect(chipsOf(def, 'columns', LABELS)).toEqual([])
  })

  it('titles a value in the pivot’s own words', () => {
    const german = { ...LABELS, sum_of: 'Summe von {field}' }
    expect(valueTitle({ field: 'Betrag', aggregation: 'sum', name: '' }, german)).toBe('Summe von Betrag')
    expect(valueTitle({ field: 'Betrag', aggregation: 'sum', name: 'Umsatz' }, german)).toBe('Umsatz')
    expect(valueTitle({ field: 'x', aggregation: 'max', name: '' }, LABELS)).toBe('Max of x')
  })

  it('finds the value field a column shows from the titles in its header', () => {
    const two = pivot({
      definition: {
        ...emptyDefinition('Sales'),
        values: [
          { field: 'Amount', aggregation: 'sum', name: '' },
          { field: 'Units', aggregation: 'average', name: 'Mean units' },
        ],
      },
    })
    expect(valueIndexFor(two, ['Mean units', 'Q1'])).toBe(1)
    expect(valueIndexFor(two, ['Sum of Amount', 'Q1'])).toBe(0)
    expect(valueIndexFor(two, ['Region'])).toBe(0)
    expect(valueIndexFor(pivot({ definition: emptyDefinition('Sales') }), ['x'])).toBeNull()
  })

  it('leaves {field} for the server to fill when a pivot is made', () => {
    expect(pivotLabels().sum_of).toBe('Sum of {field}')
    expect(Object.keys(pivotLabels()).sort()).toEqual(Object.keys(LABELS).sort())
  })
})

describe('the source and the place', () => {
  const sales = table('Sales')
  const budget = table('Budget', { region: { sheet: 's2', row0: 0, col0: 0, row1: 5, col1: 3 }, sheet: 's2' })

  it('offers tables and query results with columns, not loose cells and not a pivot’s own result', () => {
    const loose = table('Loose', { header: false })
    const result = table('Totals', { kind: 'result', header: true })
    const sheetOnly = table('Mine', { scope: 's1' })
    const noColumns = table('Empty', { columns: [] })
    const own = table('SalesPivot', { kind: 'result' })
    const found = sourceChoices([sales, loose, result, sheetOnly, noColumns, own, budget], [{ name: 'salespivot' }])
    expect(found.map((n) => n.name)).toEqual(['Budget', 'Sales', 'Totals'])
  })

  it('starts on the table the cursor is in, else the first', () => {
    const choices = [budget, sales]
    expect(preselected(choices, 's1', 12, 2)?.name).toBe('Sales')
    expect(preselected(choices, 's1', 0, 0)?.name).toBe('Budget')
    expect(preselected([], 's1', 0, 0)).toBeNull()
  })

  it('names a new pivot after its source, and keeps the name free', () => {
    expect(suggestName('Sales', [])).toBe('SalesPivot')
    expect(suggestName('Sales', ['salespivot', 'SalesPivot2'])).toBe('SalesPivot3')
    expect(suggestName('2024', [])).toBe('Pivot')
  })

  it('refuses a name a formula cannot use or one that is taken', () => {
    expect(pivotNameProblem('SalesPivot', ['Sales'])).toBeNull()
    expect(pivotNameProblem('Sales Pivot', [])).toMatch(/letter/)
    expect(pivotNameProblem('B3', [])).toMatch(/cell/)
    expect(pivotNameProblem('sales', ['Sales'])).toMatch(/already/)
  })

  it('calls the sheet of a new pivot after it, and numbers it when that name is taken', () => {
    expect(newSheetName('SalesPivot', [{ name: 'Data' }])).toBe('SalesPivot')
    expect(newSheetName('SalesPivot', [{ name: 'salespivot' }, { name: 'SalesPivot 2' }])).toBe('SalesPivot 3')
  })

  it('reads the cell it starts in, with or without the sheet', () => {
    expect(parsePlace('Data!H11', 'Data')).toEqual({ row: 10, col: 7 })
    expect(parsePlace('h11', 'Data')).toEqual({ row: 10, col: 7 })
    expect(parsePlace("'My data'!A1", 'My data')).toEqual({ row: 0, col: 0 })
    expect(parsePlace('Other!A1', 'Data')).toBeNull()
    expect(parsePlace('not a cell', 'Data')).toBeNull()
    expect(parsePlace('', 'Data')).toBeNull()
  })
})

describe('the cells of a pivot', () => {
  const p = pivot()

  it('knows which pivot a cell belongs to', () => {
    expect(pivotAt([p], 'r1', 6, 2)).toBe(p)
    expect(pivotAt([p], 'r1', 11, 2)).toBeNull()
    expect(pivotAt([p], 's1', 6, 2)).toBeNull()
    expect(pivotAt([pivot({ region: null })], 'r1', 6, 2)).toBeNull()
  })

  it('names the role of each cell: header rows as the engine says, then labels, values, totals', () => {
    expect(roleAt(p, 4, 0)).toBe('field')
    expect(roleAt(p, 5, 0)).toBe('corner')
    expect(roleAt(p, 5, 2)).toBe('header')
    expect(roleAt(p, 6, 0)).toBe('label')
    expect(roleAt(p, 6, 2)).toBe('value')
    expect(roleAt(p, 6, 4)).toBe('total') // the total column
    expect(roleAt(p, 10, 2)).toBe('total') // the total row
    expect(roleAt(p, 10, 0)).toBe('total')
    expect(roleAt(p, 11, 0)).toBeNull()
  })

  it('has no total where there is none', () => {
    const bare = pivot({ total_row: false, total_column: false })
    expect(roleAt(bare, 10, 2)).toBe('value')
    expect(roleAt(bare, 6, 4)).toBe('value')
  })

  it('paints the header cells, the labels, and the totals', () => {
    const boxes = pivotBoxes([p], 'r1', { r0: 0, r1: 30, c0: 0, c1: 10 })
    const by = (role: string) => boxes.filter((b) => b.role === role)
    expect(by('header')).toHaveLength(8)
    expect(by('field')).toHaveLength(1)
    expect(by('corner')).toHaveLength(1)
    expect(by('label')).toEqual([expect.objectContaining({ r0: 6, r1: 9, c0: 0, c1: 0 })]) // the rows between the headers and the total
    expect(by('total')).toEqual([
      expect.objectContaining({ key: 'SalesPivot:total-column', r0: 6, r1: 9, c0: 4, c1: 4 }),
      expect.objectContaining({ key: 'SalesPivot:total-row', r0: 10, r1: 10, c0: 0, c1: 4 }),
    ])
  })

  it('draws only what is on screen', () => {
    const scrolled = pivotBoxes([p], 'r1', { r0: 8, r1: 30, c0: 1, c1: 2 })
    expect(scrolled.every((b) => b.r1 >= 8 && b.c0 >= 1 && b.c1 <= 2)).toBe(true)
    expect(scrolled.find((b) => b.role === 'label')).toBeUndefined() // the labels' column is off to the left
    expect(scrolled.find((b) => b.key.endsWith('total-column'))).toBeUndefined()
    expect(scrolled.find((b) => b.key.endsWith('total-row'))).toMatchObject({ c0: 1, c1: 2 })
    expect(pivotBoxes([p], 'other', { r0: 0, r1: 30, c0: 0, c1: 10 })).toEqual([])
    expect(pivotBoxes([pivot({ region: null })], 'r1', { r0: 0, r1: 30, c0: 0, c1: 10 })).toEqual([])
  })

  it('says what it fills, or what is wrong', () => {
    expect(fillsLine(p)).toContain('Report!A5:E11')
    expect(fillsLine(pivot({ error: { code: '#SQL!', detail: 'no such column: Revnue' } }))).toContain('no such column: Revnue')
    expect(fillsLine(pivot({ placed: false }))).toMatch(/written over/)
    expect(fillsLine(pivot({ a1: null, region: null }))).toMatch(/nothing yet/)
  })
})
