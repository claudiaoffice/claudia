// Mine and the collections (sheet 10, D443): the documents a person opened before, on any place, and the groups she
// makes of them. Both are hers alone and are kept in this browser (or, later, the shell and the vault): no server
// sees them. An entry names a document by its place (an origin), its app and its id, which together are what
// opens it (D431); a collection holds such names, so one document can be in several collections.

const MINE_KEY = 'claudia.mine'
const COLLECTIONS_KEY = 'claudia.collections'
/** How many documents Mine remembers; the oldest go first. */
export const MOST_MINE = 200

export interface MineEntry {
  origin: string
  app: string
  id: string
  /** When it was last opened from this browser (ISO 8601). */
  opened: string
}

export interface Collection {
  name: string
  /** `keyOf` of each entry, in the order they were added. */
  entries: string[]
}

type Store = Pick<Storage, 'getItem' | 'setItem'>

function storage(): Store | null {
  try {
    return localStorage
  } catch {
    return null // a sandboxed frame or a private window that refuses: nothing is remembered
  }
}

function read<T>(key: string, check: (value: unknown) => value is T, store: Store | null): T[] {
  try {
    const parsed: unknown = JSON.parse(store?.getItem(key) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter(check) : []
  } catch {
    return []
  }
}

function write(key: string, value: unknown, store: Store | null) {
  try {
    store?.setItem(key, JSON.stringify(value))
  } catch {
    /* full or refused: Mine is a convenience, never a reason to fail */
  }
}

function isEntry(value: unknown): value is MineEntry {
  const v = value as MineEntry
  return !!v && typeof v.origin === 'string' && typeof v.app === 'string' && typeof v.id === 'string' && typeof v.opened === 'string'
}

function isCollection(value: unknown): value is Collection {
  const v = value as Collection
  return !!v && typeof v.name === 'string' && Array.isArray(v.entries) && v.entries.every((e) => typeof e === 'string')
}

/** What names one document everywhere: its place, its app and its id. */
export function keyOf(entry: { origin: string; app: string; id: string }): string {
  return `${entry.origin} ${entry.app} ${entry.id}`
}

/** Mine, the most recently opened first. */
export function listMine(store: Store | null = storage()): MineEntry[] {
  return read(MINE_KEY, isEntry, store).sort((a, b) => b.opened.localeCompare(a.opened))
}

/** Remember that this document was just opened (it moves to the top). */
export function rememberOpened(entry: Omit<MineEntry, 'opened'>, when = new Date().toISOString(), store: Store | null = storage()): MineEntry[] {
  const key = keyOf(entry)
  const kept = listMine(store).filter((e) => keyOf(e) !== key)
  const next = [{ ...entry, opened: when }, ...kept].slice(0, MOST_MINE)
  write(MINE_KEY, next, store)
  return next
}

/** Take a document off Mine (it stays on its place, and in no collection any more). */
export function forgetMine(key: string, store: Store | null = storage()): MineEntry[] {
  const next = listMine(store).filter((e) => keyOf(e) !== key)
  write(MINE_KEY, next, store)
  write(COLLECTIONS_KEY, listCollections(store).map((c) => ({ ...c, entries: c.entries.filter((k) => k !== key) })), store)
  return next
}

/** The collections, in the order they were made. */
export function listCollections(store: Store | null = storage()): Collection[] {
  return read(COLLECTIONS_KEY, isCollection, store)
}

/** Make a collection; a name that is empty or taken (case ignored) makes none. */
export function createCollection(name: string, store: Store | null = storage()): Collection[] {
  const trimmed = name.trim()
  const all = listCollections(store)
  if (!trimmed || all.some((c) => c.name.toLowerCase() === trimmed.toLowerCase())) return all
  const next = [...all, { name: trimmed, entries: [] }]
  write(COLLECTIONS_KEY, next, store)
  return next
}

/** Put a document into a collection (once) or take it out. */
export function setInCollection(name: string, key: string, inside: boolean, store: Store | null = storage()): Collection[] {
  const next = listCollections(store).map((c) => {
    if (c.name !== name) return c
    const rest = c.entries.filter((k) => k !== key)
    return { ...c, entries: inside ? [...rest, key] : rest }
  })
  write(COLLECTIONS_KEY, next, store)
  return next
}

/** Remove a collection: only the grouping goes, never a document. */
export function deleteCollection(name: string, store: Store | null = storage()): Collection[] {
  const next = listCollections(store).filter((c) => c.name !== name)
  write(COLLECTIONS_KEY, next, store)
  return next
}

/** The place, app and id a `keyOf` names; `null` for a key that is not one. */
export function parseKey(key: string): { origin: string; app: string; id: string } | null {
  const [origin, app, id, ...rest] = key.split(' ')
  return origin && app && id && rest.length === 0 ? { origin, app, id } : null
}

/** The documents a collection holds, in the order they were put in. One that is also in Mine says when it was last
 *  opened; one that was put in from a place's list without being opened has `opened: ''`. */
export function entriesOf(collection: Collection, mine: MineEntry[]): MineEntry[] {
  const opened = new Map(mine.map((e) => [keyOf(e), e]))
  return collection.entries.flatMap((key) => {
    const known = opened.get(key)
    if (known) return [known]
    const named = parseKey(key)
    return named ? [{ ...named, opened: '' }] : []
  })
}
