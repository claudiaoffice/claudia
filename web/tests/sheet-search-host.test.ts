import { describe, expect, it, vi } from 'vitest'
import { sheetSearchHost } from '~/lib/sheet-search-host'
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
  const host = sheetSearchHost({ session: session as never, selection: () => sel, goTo })
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
    await host.replace(query, { text: true, formulas: true, values: false }, { sheet: 's1' }, [{ sheet: 's1', row: 0, col: 0, match: null }])
    expect(session.searchReplace).toHaveBeenCalledWith(query, ['text', 'formulas'], { sheet: 's1' }, [{ sheet: 's1', row: 0, col: 0, match: null }])
  })

  it('names a cell with its sheet and goes to it', () => {
    const { host, goTo } = setup()
    const match = { sheet: 's1', row: 1, col: 1 }
    expect(host.where(match)).toBe('Costs!B2')
    host.jump(match)
    expect(goTo).toHaveBeenCalledWith('s1', 1, 1)
  })

  it('says which revision the answers are for, so that a change by somebody else is noticed', () => {
    expect(setup().host.revision()).toBe('main:7')
  })
})
