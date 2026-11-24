// The browser's storages, reached in this one place (CODE-36). A sandboxed frame or a private window may have none or
// refuse them; then a store in memory stands in, one per page, so a choice still holds until the page closes.

/** What the browser keeps; narrower than `Storage` so a test can hand in a map. */
export type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

function inMemory(): Store {
  const memory = new Map<string, string>()
  return {
    getItem: (k) => memory.get(k) ?? null,
    setItem: (k, v) => void memory.set(k, v),
    removeItem: (k) => void memory.delete(k),
  }
}

const localMemory = inMemory()
const sessionMemory = inMemory()

/** The browser's local storage, or the page's memory where there is none to reach. */
export function safeStorage(): Store {
  try {
    return localStorage
  } catch {
    return localMemory
  }
}

/** The browser's storage for this tab, or the page's memory where there is none to reach. */
export function safeSessionStorage(): Store {
  try {
    return sessionStorage
  } catch {
    return sessionMemory
  }
}

/** The value kept under `key` if it is one of `allowed`, otherwise `fallback`. */
export function remembered<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  const value = read(key)
  return allowed.find((choice) => choice === value) ?? fallback
}

/** Keep `value` under `key` in this browser. */
export function remember(key: string, value: string): void {
  try {
    safeStorage().setItem(key, value)
  } catch {
    /* full or refused: the choice still holds for this visit */
  }
}

function read(key: string): string | null {
  try {
    return safeStorage().getItem(key)
  } catch {
    return null
  }
}
