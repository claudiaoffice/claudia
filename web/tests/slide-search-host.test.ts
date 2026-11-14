import { describe, expect, it, vi } from 'vitest'
import { marksFor, piecesOf, slideOf, slideSearchHost } from '~/lib/slide-search-host'
import type { SearchMatch } from '~/lib/search'
import { createTranslator } from '~/lib/i18n'

function setup(role: 'owner' | 'editor' | 'viewer' = 'editor') {
  const session = {
    state: { activeSlide: 's2', slides: [{ id: 's1' }, { id: 's2' }], me: { role }, revision: 'main:7' },
    searchFind: vi.fn(async () => ({ matches: [] })),
    searchPreview: vi.fn(async () => ({ changes: [] })),
    searchReplace: vi.fn(async () => ({ replaced: 1 })),
    showSlide: vi.fn(async () => undefined),
  }
  const showNotes = vi.fn()
  const host = slideSearchHost({ session: session as never, showNotes, t: createTranslator({}) })
  return { host, session, showNotes }
}

const match = (at: SearchMatch['at'], start = 0, end = 3): SearchMatch => ({ at, kind: 'text', number: 1, start, end, parts: [], replacement: null }) as SearchMatch

describe('the search host of a presentation', () => {
  it('says what a presentation can be searched for and where', () => {
    const { host } = setup()
    expect(host.unit).toBe('text')
    expect(host.switches.map((s) => [s.key, s.matchKind, s.replaceable, s.whileReplacing])).toEqual([
      ['text', 'text', true, true],
      ['label', 'label', true, true],
      ['notes', 'notes', true, true],
      ['description', 'description', true, true],
    ])
    expect(host.scopes).toEqual(['all', 'slide'])
    expect(host.extraParts).toEqual(['word'])
  })

  it('is read-only for somebody who can only look', () => {
    expect(setup('viewer').host.readonly).toBe(true)
    expect(setup('editor').host.readonly).toBe(false)
  })

  it('turns the scopes of the panel into the scopes of the server', () => {
    const { host } = setup()
    expect(host.scopeOf('slide')).toEqual({ slide: 's2' })
    expect(host.scopeOf('all')).toEqual({})
  })

  it('looks in every kind and previews and replaces in the ones switched on', async () => {
    const { host, session } = setup()
    const query = { mode: 'text', text: 'x', match_case: false, replace: [{ text: 'y' }] } as const
    await host.find(query, {})
    expect(session.searchFind).toHaveBeenCalledWith(query, ['text', 'label', 'notes', 'description'], {})
    await host.preview(query, { text: true, label: false, notes: true, description: false }, {}, [])
    expect(session.searchPreview).toHaveBeenCalledWith(query, ['text', 'notes'], {}, [])
    await host.replace(query, { text: false, label: true, notes: false, description: true }, { slide: 's1' }, [])
    expect(session.searchReplace).toHaveBeenCalledWith(query, ['label', 'description'], { slide: 's1' }, [])
  })

  it('names a place for the person and keeps one key per place', () => {
    const { host } = setup()
    const words = { slide: 's2', object: 'o1', source: 'box' }
    expect(host.where(words)).toBe('Object on slide 2')
    expect(host.where({ ...words, source: 'description' })).toBe('Description of an object on slide 2')
    expect(host.where({ slide: 's1', source: 'notes' })).toBe('Speaker notes of slide 1')
    expect(host.keyOf(words)).toBe('s2/o1/box')
    expect(host.keyOf({ slide: 's1', source: 'notes' })).toBe('s1/notes')
    expect(() => slideOf({ cell: 1 })).toThrow('not a place in a presentation')
  })

  it('goes to the slide, and shows the notes for a match in them', async () => {
    const { host, session, showNotes } = setup()
    host.jump({ slide: 's1', object: 'o1', source: 'box' })
    await vi.waitFor(() => expect(session.showSlide).toHaveBeenCalledWith('s1'))
    expect(showNotes).not.toHaveBeenCalled()
    host.jump({ slide: 's1', source: 'notes' })
    await vi.waitFor(() => expect(showNotes).toHaveBeenCalledOnce())
  })

  it('follows the revision of the document', () => {
    expect(setup().host.revision()).toBe('main:7')
  })
})

describe('what a slide draws for a search', () => {
  it('marks the words of objects on this slide, and the one being looked at', () => {
    const matches = [
      match({ slide: 's2', object: 'a', source: 'box' }, 1, 4),
      match({ slide: 's2', object: 'b', source: 'label' }, 0, 2),
      match({ slide: 's1', object: 'a', source: 'box' }), // another slide
      match({ slide: 's2', object: 'a', source: 'description' }), // not drawn
      match({ slide: 's2', source: 'notes' }), // not drawn
    ]
    expect(marksFor(matches, 1, 's2')).toEqual([
      { object: 'a', start: 1, end: 4, current: false },
      { object: 'b', start: 0, end: 2, current: true },
    ])
    expect(marksFor(matches, null, 's2').every((m) => !m.current)).toBe(true)
  })

  it('cuts the words where the marks are, and the pieces make the words again', () => {
    const pieces = piecesOf('one two three', [{ start: 4, end: 7, current: true }, { start: 0, end: 3, current: false }])
    expect(pieces).toEqual([
      { text: 'one', found: 'match' },
      { text: ' ', found: null },
      { text: 'two', found: 'current' },
      { text: ' three', found: null },
    ])
    expect(pieces.map((p) => p.text).join('')).toBe('one two three')
  })

  it('draws words without marks whole, even none, and fits stale marks to the words', () => {
    expect(piecesOf('abc', [])).toEqual([{ text: 'abc', found: null }])
    expect(piecesOf('', [])).toEqual([{ text: '', found: null }])
    expect(piecesOf('abc', [{ start: 2, end: 9, current: false }, { start: 7, end: 8, current: false }])).toEqual([
      { text: 'ab', found: null },
      { text: 'c', found: 'match' },
    ])
  })
})
