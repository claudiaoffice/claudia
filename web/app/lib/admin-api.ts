// Talking to a server's own /api/admin/* (E3.11, D151-D155): the settings pages' API, signed in to separately from
// any document. These pages are only ever reached by navigating to that server's own /admin/ (server-bookmarks.ts
// never fetches a different origin in the page), so every call here is a plain relative fetch — no server address
// to carry around, no CORS to worry about.
//
// Field names are kept exactly as the wire sends them (snake_case), the same choice protocol.ts makes for the
// document socket: one less mapping layer, and the tests can compare directly against what the server returns.

import type { CheckAnswer, FontsPage, MayGo } from './admin-fonts'

export class AdminApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

export interface AdminStatus {
  needs_administrator: boolean
  exposed: boolean
  /** The earliest-added administrator's name, or `null` if there is none yet. A hint for a default label
   *  (server-bookmarks.ts), never a credential and never required to be signed in. */
  administrator: string | null
}

/** Whether to offer becoming this server's first administrator (`FirstAdminSetup.vue`) — true whenever nobody
 *  has ever become one, regardless of `needs_administrator`. That flag also requires the server to be exposed
 *  beyond loopback (D152: a loopback-only server is never *forced* through this screen), so it stays `false` even
 *  with zero administrators on the common local-only server. This is the other half: someone who navigates to
 *  the settings pages directly can still *choose* to set one up, so the screen must still be reachable then. */
export function hasNoAdministrator(status: Pick<AdminStatus, 'administrator'>): boolean {
  return status.administrator === null
}

export interface AdminAccount {
  name: string
  added: string
  /** Whether this is the administrator the request was signed in as. */
  you: boolean
}

export interface Changed {
  by: string
  at: string
}

export interface AiSettings {
  model_dir: string | null
  device: string
  max_tokens: number
  timeout: number
}

export interface TypesetSettings {
  xelatex: string | null
  pdftocairo: string | null
}

export interface TypesetDiagnosis {
  ok: boolean
  detail: string
}

export interface ServerSettingsView {
  max_documents: number
  access_secret_set: boolean
  ai: AiSettings
  typeset: TypesetSettings
  typeset_diagnosis: Record<string, TypesetDiagnosis>
  changed: Record<string, Changed>
}

export type AdminApi = ReturnType<typeof createAdminApi>

/** What Add fonts… sends to make a collection (E3.13 f, D1041). */
export interface NewFontCollection {
  files: string[]
  name: string
  licence: string
  may_go: MayGo
}

/** Everything the settings pages call, bound to one `fetch` implementation — a real one in the browser, a fake one
 *  in a test (the same injection `i18n.ts`'s `loadCatalog` uses, just once here instead of on every function). */
export function createAdminApi(fetchImpl: typeof fetch = fetch) {
  async function call<T>(method: string, path: string, body?: unknown, token?: string, raw?: { data: Blob; name: string }): Promise<T> {
    const headers: Record<string, string> = {}
    if (body !== undefined) headers['content-type'] = 'application/json'
    if (raw) headers['x-claudia-name'] = encodeURIComponent(raw.name)
    if (token) headers.authorization = `Bearer ${token}`
    const sent = raw ? raw.data : body === undefined ? undefined : JSON.stringify(body)
    const response = await fetchImpl(`/api/admin${path}`, { method, headers, body: sent })
    if (response.status === 204) return undefined as T
    let parsed: unknown = null
    try {
      parsed = await response.json()
    } catch {
      /* an empty or non-JSON body: `parsed` stays null, which only matters if the response was not ok */
    }
    if (!response.ok) {
      const detail = (parsed as { detail?: unknown })?.detail
      throw new AdminApiError(response.status, typeof detail === 'string' ? detail : `request failed (${response.status})`)
    }
    return parsed as T
  }

  return {
    status: (): Promise<AdminStatus> => call('GET', '/status'),
    setup: (name: string, password: string): Promise<{ token: string; admin: AdminAccount }> => call('POST', '/setup', { name, password }),
    login: (name: string, password: string): Promise<{ token: string; admin: AdminAccount }> => call('POST', '/login', { name, password }),
    logout: (token: string): Promise<void> => call('POST', '/logout', undefined, token),
    me: (token: string): Promise<{ name: string }> => call('GET', '/me', undefined, token),

    listAdmins: (token: string): Promise<AdminAccount[]> => call('GET', '/admins', undefined, token),
    addAdmin: (token: string, name: string, password: string): Promise<AdminAccount> => call('POST', '/admins', { name, password }, token),
    removeAdmin: (token: string, name: string): Promise<void> => call('DELETE', `/admins/${encodeURIComponent(name)}`, undefined, token),
    changeAdminPassword: (token: string, name: string, password: string): Promise<void> =>
      call('POST', `/admins/${encodeURIComponent(name)}/password`, { password }, token),

    getSettings: (token: string): Promise<ServerSettingsView> => call('GET', '/settings', undefined, token),
    setMaxDocuments: (token: string, maxDocuments: number): Promise<ServerSettingsView> =>
      call('PUT', '/settings/max-documents', { max_documents: maxDocuments }, token),
    revealAccessSecret: (token: string): Promise<{ access_secret: string | null }> => call('GET', '/settings/access-secret', undefined, token),
    putAccessSecret: (token: string, accessSecret: string | null): Promise<ServerSettingsView> =>
      call('PUT', '/settings/access-secret', { access_secret: accessSecret }, token),
    rotateAccessSecret: (token: string): Promise<ServerSettingsView & { access_secret: string }> =>
      call('POST', '/settings/access-secret/rotate', undefined, token),
    setAi: (token: string, settings: AiSettings): Promise<ServerSettingsView> => call('PUT', '/settings/ai', settings, token),
    setTypeset: (token: string, settings: TypesetSettings): Promise<ServerSettingsView> => call('PUT', '/settings/typeset', settings, token),

    // Server settings ▸ Fonts (E3.13 f, D1041): every change answers the whole page.
    fontsPage: (token: string): Promise<FontsPage> => call('GET', '/fonts', undefined, token),
    /** Holds one file for Add fonts… (the bytes as the body, as `/api/uploads` takes them); nothing is added yet. */
    holdFontFile: (token: string, data: Blob, name: string): Promise<{ token: string; name: string; size: number }> =>
      call('POST', '/fonts/files', undefined, token, { data, name }),
    checkFonts: (token: string, files: string[]): Promise<CheckAnswer> => call('POST', '/fonts/check', { files }, token),
    addFontCollection: (token: string, collection: NewFontCollection): Promise<FontsPage> => call('POST', '/fonts/collections', collection, token),
    renameFontCollection: (token: string, id: string, name: string): Promise<FontsPage> =>
      call('PATCH', `/fonts/collections/${encodeURIComponent(id)}`, { name }, token),
    removeFontCollection: (token: string, id: string): Promise<FontsPage> => call('DELETE', `/fonts/collections/${encodeURIComponent(id)}`, undefined, token),
  }
}

/** The browser's own `fetch`, bound once — what every component imports; tests import `createAdminApi` instead. */
export const adminApi = createAdminApi()
