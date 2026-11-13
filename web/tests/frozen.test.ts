import { describe, expect, it } from 'vitest'
import { freeze, showSlides } from '~/lib/frozen'

// The pieces of a session the show reads: only these are looked at, so a plain object stands in for it.
function fake() {
  const state: any = {
    revision: 'main:7',
    slides: [{ id: 's1', objects: 1 }, { id: 's2', objects: 0 }],
    order: { s1: ['a'], s2: [] },
    objects: { a: { id: 'a', kind: 'text', anchor: { kind: 'slide', container: 's1', x: 1, y: 2 } } },
    styles: { 'body-text': { id: 'body-text' } },
    shapes: {},
    images: {},
    styleModel: { facets: {} },
    notes: { s1: 'first' },
    times: { s2: 90 },
  }
  const session: any = {
    state,
    objectsOn: (slide: string) => state.order[slide].map((id: string) => state.objects[id]),
    notesOf: (slide: string) => state.notes[slide] ?? '',
    secondsOf: (slide: string) => state.times[slide] ?? null,
  }
  return { session, state }
}

describe('the deck as it was when the show started (D292)', () => {
  it('holds the slides with their notes, times and objects', () => {
    const { session } = fake()
    const deck = freeze(session)
    expect(deck.revision).toBe('main:7')
    expect(showSlides(deck)).toEqual([
      { id: 's1', seconds: null, notes: 'first' },
      { id: 's2', seconds: 90, notes: '' },
    ])
    expect(deck.objects.s1!.map((o) => o.id)).toEqual(['a'])
    expect(deck.objects.s2).toEqual([])
  })
  it('does not change when the document does', () => {
    const { session, state } = fake()
    const deck = freeze(session)
    state.objects.a.anchor.x = 999
    state.notes.s1 = 'rewritten'
    state.styles['body-text'].id = 'other'
    state.slides.push({ id: 's3', objects: 0 })
    expect(deck.objects.s1![0]!.anchor.x).toBe(1)
    expect(showSlides(deck)[0]!.notes).toBe('first')
    expect(deck.styles['body-text']!.id).toBe('body-text')
    expect(deck.slides).toHaveLength(2)
  })
})
