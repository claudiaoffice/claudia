import { describe, expect, it, vi } from 'vitest'
import { blockOf, marksFor, textSearchHost } from '~/lib/text-search-host'
import type { SearchMatch } from '~/lib/search'
import { createTranslator } from '~/lib/i18n'

type Pos = { block: string; offset: number }
function setup(role: 'owner' | 'editor' | 'viewer' = 'editor', selection: { anchor: Pos; focus: Pos } | null = null) {
  const session = {
    state: { blocks: [{ id: 'b1' }, { id: 'b2' }, { id: 'b3' }], selection, me: { role }, revision: 'main:3' },
    searchFind: vi.fn(async () => ({ matches: [] })),
    searchPreview: vi.fn(async () => ({ changes: [] })),
    searchReplace: vi.fn(async () => ({ replaced: 1 })),
  }
  const goTo = vi.fn()
  const host = textSearchHost({ session: session as never, goTo, t: createTranslator({}) })
  return { host, session, goTo }
}

const match = (at: SearchMatch['at'], start = 0, end = 3): SearchMatch => ({ at, kind: 'text', number: 1, start, end, parts: [], replacement: null }) as SearchMatch

describe('the search host of a text', () => {
  it('says what a text can be searched for and where', () => {
    const { host } = setup()
    expect(host.unit).toBe('text')
    expect(host.switches.map((s) => s.key)).toEqual(['text', 'heading', 'remark', 'object', 'description'])
    expect(host.scopes).toEqual(['all', 'section', 'selection'])
    expect(host.extraParts).toEqual(['word'])
  })

  it('is read-only for somebody who can only look', () => {
    expect(setup('viewer').host.readonly).toBe(true)
  })

  it('turns the scopes of the panel into the scopes of the server', () => {
    const caret = { anchor: { block: 'b2', offset: 1 }, focus: { block: 'b2', offset: 1 } }
    expect(setup('editor', caret).host.scopeOf('all')).toEqual({})
    expect(setup('editor', caret).host.scopeOf('section')).toEqual({ section: 'b2' })
    expect(setup().host.scopeOf('section')).toEqual({ section: 'b1' })
    expect(setup('editor', caret).host.scopeOf('selection')).toEqual({}) // only a caret: nothing is selected
  })

  it('reads a selection from its earlier end to its later one, whichever way it was made', () => {
    const backwards = { anchor: { block: 'b3', offset: 2 }, focus: { block: 'b1', offset: 4 } }
    expect(setup('editor', backwards).host.scopeOf('selection')).toEqual({
      range: { from: { block: 'b1', offset: 4 }, to: { block: 'b3', offset: 2 } },
    })
  })

  it('looks in every kind and previews and replaces in the ones switched on', async () => {
    const { host, session } = setup()
    const query = { mode: 'text', text: 'x', match_case: false, replace: [{ text: 'y' }] } as const
    await host.find(query, {})
    expect(session.searchFind).toHaveBeenCalledWith(query, ['text', 'heading', 'remark', 'object', 'description'], {})
    await host.preview(query, { text: true, heading: true, remark: false, object: false, description: false }, {}, [])
    expect(session.searchPreview).toHaveBeenCalledWith(query, ['text', 'heading'], {}, [])
  })

  it('names a place for the person and goes to its paragraph', () => {
    const { host, goTo } = setup()
    expect(host.where({ block: 'b2' })).toBe('Paragraph 2')
    expect(host.where({ block: 'b3', object: 'o', source: 'box' })).toBe('Object in paragraph 3')
    expect(host.where({ block: 'b3', object: 'o', source: 'description' })).toBe('Description of an object in paragraph 3')
    expect(host.keyOf({ block: 'b2', offset: 5 })).toBe('b2:5')
    expect(host.keyOf({ block: 'b2', object: 'o', source: 'box' })).toBe('b2/o/box')
    host.jump({ block: 'b3', object: 'o', source: 'box' })
    expect(goTo).toHaveBeenCalledWith('b3')
    expect(() => blockOf({ sheet: 'x' })).toThrow('not a place in a text')
  })
})

describe('what the editor draws for a search', () => {
  it('marks stretches of paragraphs, from the offset of a partial paragraph, and skips objects', () => {
    const matches = [
      match({ block: 'b1' }, 2, 5),
      match({ block: 'b2', offset: 10 }, 1, 3),
      match({ block: 'b2', object: 'o', source: 'box' }),
    ]
    expect(marksFor(matches, 1)).toEqual([
      { block: 'b1', start: 2, end: 5, current: false },
      { block: 'b2', start: 11, end: 13, current: true },
    ])
  })
})
