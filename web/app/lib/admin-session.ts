// Holding an administrator's sign-in while they are on this server's settings pages (D153: a bearer token, never a
// cookie). sessionStorage, not localStorage, on purpose — this is the "danger zone" surface, and closing the tab is
// a reasonable way to end a sitting without reaching for Sign out; a browser restart means signing in again.
//
// The key carries no server address: these pages are only ever reached by navigating to that server's own origin
// (server-bookmarks.ts), and sessionStorage is already scoped per origin by the browser, so one key is enough.
import { ref } from 'vue' // only the Vue wiring at the end uses these
import { AdminApiError, adminApi, type AdminApi } from './admin-api'

import { translate as t } from './i18n'
import { safeSessionStorage } from './storage'
const KEY = 'claudia.admin.token'

export function readToken(storage: Pick<Storage, 'getItem'> = safeSessionStorage()): string | null {
  try {
    return storage.getItem(KEY)
  } catch {
    return null
  }
}

export function storeToken(token: string, storage: Pick<Storage, 'setItem'> = safeSessionStorage()): void {
  try {
    storage.setItem(KEY, token)
  } catch {
    /* private window, or storage full: the sign-in still works for the rest of this visit */
  }
}

export function clearToken(storage: Pick<Storage, 'removeItem'> = safeSessionStorage()): void {
  try {
    storage.removeItem(KEY)
  } catch {
    /* nothing to clear */
  }
}

/** Why naming the first administrator was refused (D1371): a wrong setup code, too many tries, somebody faster, or
 *  anything else the server said (a short password, say). */
export interface SetupRefusal {
  kind: 'wrong-code' | 'too-soon' | 'taken' | 'other'
  message: string
  retryAfter?: number
}

export function setupRefusal(error: unknown): SetupRefusal {
  if (!(error instanceof AdminApiError)) return { kind: 'other', message: t('Could not reach the server.') }
  if (error.status === 403) return { kind: 'wrong-code', message: error.message }
  if (error.status === 409) return { kind: 'taken', message: error.message }
  if (error.status === 429) return { kind: 'too-soon', message: error.message, retryAfter: error.retryAfter }
  return { kind: 'other', message: error.message }
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
  /** Seconds the last refused sign-in was asked to wait (D1266); 0 when it was not. */
  const waitAdvice = ref(0)
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

  /** Become the first administrator with the setup code (D1370); `null` when it worked, else why not. */
  async function setup(adminName: string, password: string, code: string): Promise<SetupRefusal | null> {
    busy.value = true
    try {
      const { token: t, admin } = await api.setup(adminName, password, code)
      token.value = t
      name.value = admin.name
      storeToken(t)
      return null
    } catch (error) {
      return setupRefusal(error)
    } finally {
      busy.value = false
    }
  }

  async function login(adminName: string, password: string): Promise<string | null> {
    busy.value = true
    waitAdvice.value = 0
    try {
      const { token: t, admin } = await api.login(adminName, password)
      token.value = t
      name.value = admin.name
      storeToken(t)
      return null
    } catch (error) {
      if (error instanceof AdminApiError && error.retryAfter) waitAdvice.value = error.retryAfter
      return error instanceof AdminApiError ? error.message : t('Could not reach the server.')
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

  return { token, name, busy, waitAdvice, refresh, setup, login, logout }
}
