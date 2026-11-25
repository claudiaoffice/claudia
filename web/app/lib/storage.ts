// The browser's storages, reached and guarded in this one place (CODE-36). A sandboxed frame or a private window may
// have none, refuse to hand them out, or refuse a call (a full storage too); then a store in memory, one per page,
// holds what the browser would not, so a choice still holds until the page closes. Nothing here throws, so the
// modules that keep something need no guard of their own.

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

/** What `call` gives, or `null` where the browser refuses it. */
function attempt<T>(call: () => T): T | null {
  try {
    return call()
  } catch {
    return null
  }
}

/** `browser()`, with the page's memory holding only what it refused: a value it took is read from it again, so
 *  another tab's later change is seen. */
function guarded(browser: () => Store): Store {
  const memory = inMemory()
  return {
    getItem: (k) => memory.getItem(k) ?? attempt(() => browser().getItem(k)),
    setItem: (k, v) => {
      try {
        browser().setItem(k, v)
        memory.removeItem(k)
      } catch {
        memory.setItem(k, v)
      }
    },
    removeItem: (k) => {
      memory.removeItem(k)
      attempt(() => browser().removeItem(k))
    },
  }
}

const local = guarded(() => localStorage)
const session = guarded(() => sessionStorage)

/** The browser's local storage, or the page's memory for what it cannot keep. */
export function safeStorage(): Store {
  return local
}

/** The browser's storage for this tab, or the page's memory for what it cannot keep. */
export function safeSessionStorage(): Store {
  return session
}

/** The value kept under `key` if it is one of `allowed`, otherwise `fallback`. */
export function remembered<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  const value = local.getItem(key)
  return allowed.find((choice) => choice === value) ?? fallback
}

/** The text kept under `key` in this browser, or an empty text. */
export function rememberedText(key: string): string {
  return local.getItem(key) ?? ''
}

/** Keep `value` under `key` in this browser. */
export function remember(key: string, value: string): void {
  local.setItem(key, value)
}
