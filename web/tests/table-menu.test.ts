import { describe, expect, it } from 'vitest'
import { possible, tableShortcuts, TABLE_ACTION_IDS, type TableAction, type TableMenuHost } from '~/lib/table-menu'
import type { TableInfo } from '~/lib/tables'
import { KEYS } from '~/lib/menus.generated'
import { dispatch } from '~/lib/shortcuts'

const t = (msgid: string) => msgid

function table(rows: number, cols: number, extra: Partial<TableInfo> = {}): TableInfo {
  return {
    format: 1,
    id: 't1',
    columns: Array.from({ length: cols }, (_, i) => ({ id: `c${i + 1}`, kind: 'text' as const, total: null, width: null })),
    rows: Array.from({ length: rows }, (_, i) => `r${i + 1}`),
    entries: [],
    merges: [],
    header_rows: 0,
    banded: false,
    look: 'rules',
    placement: 'flow',
    width: null,
    next_row: rows,
    next_col: cols,
    used_by: ['o1'],
    totals: {},
    ...extra,
  }
}
function host(over: Partial<TableMenuHost> = {}): TableMenuHost & { done: TableAction[] } {
  const done: TableAction[] = []
  return { table: table(3, 3), box: { row: 'r1', col: 'c1' }, readonly: false, run: (a) => done.push(a), ...over, done }
}
const ALL = Object.keys(TABLE_ACTION_IDS) as TableAction[]

describe('what can be done to a table in a text', () => {
  it('is all of it in a box of an ordinary table but Split Cell, and every action has a key from the definition', () => {
    expect(ALL.filter((action) => possible(host(), action))).toEqual(ALL.filter((action) => action !== 'split-cell'))
    for (const action of ALL) expect(KEYS[TABLE_ACTION_IDS[action]]).toBeDefined()
  })

  it('is nothing outside a table, and nothing for somebody who may only read', () => {
    for (const h of [host({ box: null }), host({ table: null }), host({ readonly: true })]) {
      expect(ALL.some((action) => possible(h, action))).toBe(false)
    }
  })

  it('keep the limits: no eleventh column, no hundred and first row, no last row or column deleted', () => {
    expect(possible(host({ table: table(100, 3) }), 'row-below')).toBe(false)
    expect(possible(host({ table: table(3, 10) }), 'column-right')).toBe(false)
    expect(possible(host({ table: table(1, 1) }), 'row-delete')).toBe(false)
    expect(possible(host({ table: table(1, 1) }), 'column-delete')).toBe(false)
    expect(possible(host({ table: table(1, 1) }), 'sort-ascending')).toBe(true)
  })

  it('offer Merge Cells where there is a box to join and Split Cell on a joined one', () => {
    const joined = table(3, 3, { merges: [{ row: 'r1', col: 'c1', rows: 1, cols: 2 }] })
    expect(possible(host(), 'merge-cells')).toBe(true)
    expect(possible(host(), 'split-cell')).toBe(false)
    expect(possible(host({ table: joined }), 'merge-cells')).toBe(false)
    expect(possible(host({ table: joined }), 'split-cell')).toBe(true)
    expect(possible(host({ table: table(1, 1) }), 'merge-cells')).toBe(false)
  })
})

describe('the keys of the table entries', () => {
  const press = (defs: ReturnType<typeof tableShortcuts>, id: string, typing: boolean) => {
    const chord = KEYS[id]!.chord
    return dispatch(defs, { key: chord.key, code: chord.code, ctrlKey: !!chord.ctrl, metaKey: false, shiftKey: !!chord.shift, altKey: !!chord.alt }, typing)
  }

  it('work in the box the caret is in, which is a field, and run the action', () => {
    const h = host()
    expect(press(tableShortcuts({ t }, h), 'tools.merge-cells', true)?.id).toBe('tools.merge-cells')
    expect(press(tableShortcuts({ t }, h), 'edit.row-insert-below', true)?.id).toBe('edit.row-insert-below')
    expect(h.done).toEqual(['merge-cells', 'row-below'])
  })

  it('do nothing where the entry is off', () => {
    const h = host({ box: null })
    expect(press(tableShortcuts({ t }, h), 'tools.sort-ascending', false)).toBeNull()
    expect(h.done).toEqual([])
  })
})
