import { describe, expect, it, vi } from 'vitest'
import { cellOf, marksFor, sheetSearchHost, whereLabel } from '~/lib/sheet-search-host'
import type { SearchMatch } from '~/lib/search'
import { createTranslator } from '~/lib/i18n'
import { single } from '~/lib/selection'

function setup(role: 'owner' | 'editor' | 'viewer' = 'editor') {
  const session = {
    state: { activeSheet: 's2', sheets: [{ id: 's1', name: 'Costs' }, { id: 's2', name: 'Rates' }], me: { role }, revision: 'main:7' },
    searchFind: vi.fn(async () => ({ matches: [] })),
    searchPreview: vi.fn(async () => ({ changes: [] })),
    searchReplace: vi.fn(async () => ({ replaced: 1 })),
  }
  let sel = single(2, 3)
  const goTo = vi.fn()
  const host = sheetSearchHost({ session: session as never, selection: () => sel, goTo, t: createTranslator({}) })
  return { host, session, goTo, select: (s: typeof sel) => (sel = s) }
}

describe('the search host of a workbook', () => {
  it('says what a workbook can be searched for and where', () => {
    const { host } = setup()
    expect(host.kinds).toEqual(['text', 'formulas', 'values'])
    expect(host.scopes).toEqual(['sheet', 'all', 'selection'])
    expect(host.extraParts).toEqual(['cellref'])
  })

  it('is read-only for somebody who can only look', () => {
    expect(setup('viewer').host.readonly).toBe(true)
    expect(setup('editor').host.readonly).toBe(false)
  })

  it('turns the scopes of the panel into the scopes of the server', () => {
    const { host, select } = setup()
    expect(host.scopeOf('sheet')).toEqual({ sheet: 's2' })
    expect(host.scopeOf('all')).toEqual({})
    select({ row: 5, col: 4, row2: 1, col2: 2 }) // dragged up and to the left
    expect(host.scopeOf('selection')).toEqual({ sheet: 's2', range: [1, 2, 5, 4] })
  })

  it('always looks in every kind: the switches only choose what is shown, and show how many each has', async () => {
    const { host, session } = setup()
    await host.find({ mode: 'text', text: 'x', match_case: false }, { sheet: 's2' })
    expect(session.searchFind).toHaveBeenCalledWith({ mode: 'text', text: 'x', match_case: false }, ['text', 'formulas', 'values'], { sheet: 's2' })
  })

  it('previews and replaces in the kinds that are switched on', async () => {
    const { host, session } = setup()
    const query = { mode: 'text', text: 'x', match_case: false, replace: [{ text: 'y' }] } as const
    await host.preview(query, { text: true, formulas: false, values: true }, {}, [])
    expect(session.searchPreview).toHaveBeenCalledWith(query, ['text', 'values'], {}, [])
    await host.replace(query, { text: true, formulas: true, values: false }, { sheet: 's1' }, [{ at: { sheet: 's1', row: 0, col: 0 }, match: null }])
    expect(session.searchReplace).toHaveBeenCalledWith(query, ['text', 'formulas'], { sheet: 's1' }, [{ at: { sheet: 's1', row: 0, col: 0 }, match: null }])
  })

  it('names a cell with its sheet and goes to it', () => {
    const { host, goTo } = setup()
    const at = { sheet: 's1', row: 1, col: 1 }
    expect(host.where(at)).toBe('Costs!B2')
    host.jump(at)
    expect(goTo).toHaveBeenCalledWith('s1', 1, 1)
  })

  it('names the scopes in the person’s words', () => {
    const { host } = setup()
    expect(host.scopes.map((s) => host.scopeLabel(s))).toEqual(['This sheet', 'All sheets', 'Selection'])
  })

  it('keys a cell the same however its place is written, and tells cells apart', () => {
    const { host } = setup()
    expect(host.keyOf({ sheet: 's1', row: 1, col: 2 })).toBe(host.keyOf({ col: 2, row: 1, sheet: 's1' }))
    expect(host.keyOf({ sheet: 's1', row: 1, col: 2 })).not.toBe(host.keyOf({ sheet: 's1', row: 12, col: 0 }))
  })

  it('refuses a place that is not a cell, loudly: it is a bug, not a person’s mistake', () => {
    expect(() => cellOf({ paragraph: 'p1' })).toThrow('not a cell')
    expect(cellOf({ sheet: 's1', row: 0, col: 3 })).toEqual({ sheet: 's1', row: 0, col: 3 })
  })

  it('says which revision the answers are for, so that a change by somebody else is noticed', () => {
    expect(setup().host.revision()).toBe('main:7')
  })
})

describe('a cell and its marks on the grid', () => {
  const at = (row: number, kind: SearchMatch['kind'], number = 0, sheet = 's1'): SearchMatch => ({
    at: { sheet, row, col: 0 },
    kind,
    number,
    start: 0,
    end: 1,
    parts: [],
    after: null,
    text: 'x',
    excerpt: [0, 1],
    clipped: [false, false],
  })

  it('names the cell with its sheet', () => {
    expect(whereLabel({ sheet: 's1', row: 1, col: 1 }, (id) => (id === 's1' ? 'Costs' : id))).toBe('Costs!B2')
    expect(whereLabel({ sheet: 's1', row: 0, col: 27 }, (id) => id)).toBe('s1!AB1')
  })

  it('marks cells on one sheet: every match, the current one apart, formulas known', () => {
    const marks = marksFor([at(0, 'text'), at(1, 'formula'), at(2, 'text', 0, 's2')], 's1', 1)
    expect([...marks.cells.entries()].map(([k, v]) => [k, v.current, v.formula])).toEqual([
      [0, false, false],
      [100_000, true, true],
    ])
  })

  it('shows one mark per cell, the current one winning', () => {
    const marks = marksFor([at(0, 'text', 0), at(0, 'text', 1)], 's1', 1)
    expect(marks.cells.size).toBe(1)
    expect(marks.cells.get(0)?.current).toBe(true)
  })

  it('shows what a replacement would make of a cell, and which cells it skips', () => {
    const marks = marksFor([at(0, 'text')], 's1', null, {
      changes: [
        { at: { sheet: 's1', row: 0, col: 0 }, kind: 'text', before: 'x', after: 'y' },
        { at: { sheet: 's2', row: 0, col: 0 }, kind: 'text', before: 'a', after: 'b' },
      ],
      skipped: [{ at: { sheet: 's1', row: 3, col: 0 }, kind: 'text', reason: 'locked', by: 'anna' }],
    })
    expect(marks.after.get(0)).toBe('y')
    expect(marks.after.size).toBe(1)
    expect(marks.blocked.get(300_000)).toBe('anna')
  })
})
