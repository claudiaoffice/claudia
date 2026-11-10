// Holding an administrator's sign-in while they are on this server's settings pages (D153: a bearer token, never a
// cookie). sessionStorage, not localStorage, on purpose — this is the "danger zone" surface, and closing the tab is
// a reasonable way to end a sitting without reaching for Sign out; a browser restart means signing in again.
//
// The key carries no server address: these pages are only ever reached by navigating to that server's own origin
// (server-bookmarks.ts), and sessionStorage is already scoped per origin by the browser, so one key is enough.
import { ref } from 'vue' // only the Vue wiring at the end uses these
import { AdminApiError, adminApi, type AdminApi } from './admin-api'

const KEY = 'claudia.admin.token'

export function readToken(storage: Pick<Storage, 'getItem'> = safeStorage()): string | null {
  try {
    return storage.getItem(KEY)
  } catch {
    return null
  }
}

export function storeToken(token: string, storage: Pick<Storage, 'setItem'> = safeStorage()): void {
  try {
    storage.setItem(KEY, token)
  } catch {
    /* private window, or storage full: the sign-in still works for the rest of this visit */
  }
}

export function clearToken(storage: Pick<Storage, 'removeItem'> = safeStorage()): void {
  try {
    storage.removeItem(KEY)
  } catch {
    /* nothing to clear */
  }
}

function safeStorage(): Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> {
  try {
    return sessionStorage
  } catch {
    const memory = new Map<string, string>()
    return {
      getItem: (k) => memory.get(k) ?? null,
      setItem: (k, v) => void memory.set(k, v),
      removeItem: (k) => void memory.delete(k),
    }
  }
}

// ------------------------------------------------------------------------------------------------------- Vue wiring

/** One administrator's sitting on this server's settings pages: the token, who it is, and the actions that change
 * it. `name` is `null` until `refresh()` (or `setup`/`login`) confirms the stored token still resolves to somebody —
 * a token can outlive the session that issued it being revoked (another administrator removed them, say).
 *
 * `api` defaults to the real browser-bound client; tests pass a `createAdminApi`-shaped fake instead, the same
 * injection admin-api.ts itself uses for `fetch`. */
export function useAdminSession(api: AdminApi = adminApi) {
  const token = ref<string | null>(readToken())
  const name = ref<string | null>(null)
  const busy = ref(false)

  async function refresh(): Promise<boolean> {
    if (!token.value) return false
    try {
      name.value = (await api.me(token.value)).name
      return true
    } catch {
      clear()
      return false
    }
  }

  async function setup(adminName: string, password: string): Promise<string | null> {
    busy.value = true
    try {
      const { token: t, admin } = await api.setup(adminName, password)
      token.value = t
      name.value = admin.name
      storeToken(t)
      return null
    } catch (error) {
      return error instanceof AdminApiError ? error.message : 'Could not reach the server.'
    } finally {
      busy.value = false
    }
  }

  async function login(adminName: string, password: string): Promise<string | null> {
    busy.value = true
    try {
      const { token: t, admin } = await api.login(adminName, password)
      token.value = t
      name.value = admin.name
      storeToken(t)
      return null
    } catch (error) {
      return error instanceof AdminApiError ? error.message : 'Could not reach the server.'
    } finally {
      busy.value = false
    }
  }

  function clear() {
    token.value = null
    name.value = null
    clearToken()
  }

  async function logout(): Promise<void> {
    const t = token.value
    clear()
    if (t) await api.logout(t).catch(() => {}) // signed out locally either way
  }

  return { token, name, busy, refresh, setup, login, logout }
}
