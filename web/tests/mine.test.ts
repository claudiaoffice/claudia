import { describe, expect, it } from 'vitest'
import {
  MOST_MINE,
  createCollection,
  deleteCollection,
  entriesOf,
  forgetMine,
  keyOf,
  listCollections,
  listMine,
  parseKey,
  rememberOpened,
  setInCollection,
} from '~/lib/mine'

function memoryStorage() {
  const map = new Map<string, string>()
  return { getItem: (k: string) => map.get(k) ?? null, setItem: (k: string, v: string) => void map.set(k, v) }
}

const HOME = 'http://127.0.0.1:8765'
const budget = { origin: HOME, app: 'computes', id: 'budget' }
const notes = { origin: 'https://team.example.org', app: 'composes', id: 'notes' }

describe('Mine', () => {
  it('starts empty and keeps the most recently opened first', () => {
    const store = memoryStorage()
    expect(listMine(store)).toEqual([])
    rememberOpened(budget, '2026-11-14T10:00:00Z', store)
    rememberOpened(notes, '2026-11-14T11:00:00Z', store)
    expect(listMine(store).map((e) => e.id)).toEqual(['notes', 'budget'])
  })
  it('names a document by place, app and id, so the same id in two apps is two entries (D431)', () => {
    const store = memoryStorage()
    rememberOpened(budget, '2026-11-14T10:00:00Z', store)
    rememberOpened({ ...budget, app: 'composes' }, '2026-11-14T10:01:00Z', store)
    expect(listMine(store)).toHaveLength(2)
  })
  it('moves a document opened again to the top instead of listing it twice', () => {
    const store = memoryStorage()
    rememberOpened(budget, '2026-11-14T10:00:00Z', store)
    rememberOpened(notes, '2026-11-14T11:00:00Z', store)
    rememberOpened(budget, '2026-11-14T12:00:00Z', store)
    expect(listMine(store).map((e) => [e.id, e.opened])).toEqual([
      ['budget', '2026-11-14T12:00:00Z'],
      ['notes', '2026-11-14T11:00:00Z'],
    ])
  })
  it(`remembers at most ${MOST_MINE}`, () => {
    const store = memoryStorage()
    for (let i = 0; i < MOST_MINE + 5; i++) rememberOpened({ ...budget, id: `d${i}` }, new Date(Date.UTC(2026, 0, 1, 0, i)).toISOString(), store)
    expect(listMine(store)).toHaveLength(MOST_MINE)
    expect(listMine(store)[0].id).toBe(`d${MOST_MINE + 4}`)
  })
  it('forgets an entry, and takes it out of every collection too', () => {
    const store = memoryStorage()
    rememberOpened(budget, '2026-11-14T10:00:00Z', store)
    createCollection('Finance', store)
    setInCollection('Finance', keyOf(budget), true, store)
    forgetMine(keyOf(budget), store)
    expect(listMine(store)).toEqual([])
    expect(listCollections(store)[0].entries).toEqual([])
  })
  it('ignores what it cannot read', () => {
    const store = memoryStorage()
    store.setItem('claudia.mine', '{not json')
    expect(listMine(store)).toEqual([])
    store.setItem('claudia.mine', JSON.stringify([{ origin: 1 }, { ...budget, opened: 'x' }]))
    expect(listMine(store)).toHaveLength(1)
  })
})

describe('collections', () => {
  it('are made once per name, case ignored, and never with an empty name', () => {
    const store = memoryStorage()
    createCollection('Finance', store)
    createCollection('finance', store)
    createCollection('  ', store)
    expect(listCollections(store).map((c) => c.name)).toEqual(['Finance'])
  })
  it('hold a document once, and one document can be in several', () => {
    const store = memoryStorage()
    createCollection('Finance', store)
    createCollection('Teaching', store)
    setInCollection('Finance', keyOf(budget), true, store)
    setInCollection('Finance', keyOf(budget), true, store)
    setInCollection('Teaching', keyOf(budget), true, store)
    expect(listCollections(store).map((c) => c.entries)).toEqual([[keyOf(budget)], [keyOf(budget)]])
    setInCollection('Finance', keyOf(budget), false, store)
    expect(listCollections(store)[0].entries).toEqual([])
  })
  it('lose only the grouping when deleted', () => {
    const store = memoryStorage()
    rememberOpened(budget, '2026-11-14T10:00:00Z', store)
    createCollection('Finance', store)
    setInCollection('Finance', keyOf(budget), true, store)
    deleteCollection('Finance', store)
    expect(listCollections(store)).toEqual([])
    expect(listMine(store)).toHaveLength(1)
  })
  it('show their documents in the order they were put in, also those never opened from here', () => {
    const store = memoryStorage()
    rememberOpened(notes, '2026-11-14T11:00:00Z', store)
    createCollection('Both', store)
    setInCollection('Both', keyOf(budget), true, store)
    setInCollection('Both', keyOf(notes), true, store)
    const shown = entriesOf(listCollections(store)[0], listMine(store))
    expect(shown.map((e) => [e.id, e.opened])).toEqual([
      ['budget', ''],
      ['notes', '2026-11-14T11:00:00Z'],
    ])
  })
  it('read back the place, app and id of a key', () => {
    expect(parseKey(keyOf(budget))).toEqual(budget)
    expect(parseKey('not a key at all')).toBeNull()
  })
})
