// Servers the Open dialog has connected to before (D115, the connection-awareness notes): a name and an address,
// remembered on this device only — never an access secret or a document password, which are asked for again every
// time. Switching to a different bookmarked server is a full page navigation (adminUrl/openUrl below), never an
// in-page fetch to another origin: the same "page and socket share one origin" choice the project already made for
// the Linux shell (D115), and it means none of this ever has to think about CORS.

import { translate } from './i18n'
import { safeStorage } from './storage'

export interface Bookmark {
  /** `protocol//host`, e.g. `https://demo.claudiaoffice.de` — the canonical key, and what every link is built from. */
  origin: string
  label: string
  /** `true` once a person has renamed it: a renamed label is theirs to keep, and `upsert` stops refreshing it. */
  custom: boolean
  /** `true` for her own server on this computer ("Private on this computer"), which only a desktop shell lists (the entry
   * is the shell's, not renameable, and named by the page: `named`). */
  local?: boolean
  /** `true` for the computer's shared service ("Shared on this computer", E8.5, D1622), which only a desktop shell lists
   * while it is installed; named by the page (`named`) unless a person renamed it. */
  shared?: boolean
}

const KEY = 'claudia.servers'

export function list(storage: Pick<Storage, 'getItem'> = safeStorage()): Bookmark[] {
  try {
    const raw = storage.getItem(KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter(isBookmark) : []
  } catch {
    return []
  }
}

export function isBookmark(value: unknown): value is Bookmark {
  const b = value as Partial<Bookmark>
  return typeof b?.origin === 'string' && typeof b?.label === 'string' && typeof b?.custom === 'boolean' && (b.local === undefined || typeof b.local === 'boolean') && (b.shared === undefined || typeof b.shared === 'boolean')
}

function save(bookmarks: Bookmark[], storage: Pick<Storage, 'setItem'> = safeStorage()): void {
  storage.setItem(KEY, JSON.stringify(bookmarks))
}

/** `bookmarks` with `origin` added, or its label refreshed with `defaultLabel` — unless a person already renamed it
 * (`custom`). Pure: the list it is given is not changed. */
export function withBookmark(bookmarks: Bookmark[], origin: string, defaultLabel: string): Bookmark[] {
  const next = bookmarks.map((b) => ({ ...b }))
  const existing = next.find((b) => b.origin === origin)
  if (!existing) next.push({ origin, label: defaultLabel, custom: false })
  else if (!existing.custom) existing.label = defaultLabel
  return next
}

/** `bookmarks` with a person's own name for one of them, from here on kept exactly as given (see `withBookmark`). */
export function withRenamed(bookmarks: Bookmark[], origin: string, label: string): Bookmark[] {
  const next = bookmarks.map((b) => ({ ...b }))
  const existing = next.find((b) => b.origin === origin)
  if (existing && !existing.local) {
    existing.label = label.trim() || existing.label
    existing.custom = true
  }
  return next
}

/** Remember `origin`, or refresh its label with `defaultLabel` — unless a person already renamed it (`custom`). */
export function upsert(origin: string, defaultLabel: string, storage: Pick<Storage, 'getItem' | 'setItem'> = safeStorage()): Bookmark[] {
  const bookmarks = withBookmark(list(storage), origin, defaultLabel)
  save(bookmarks, storage)
  return bookmarks
}

/** A person's own name for a bookmark, from here on kept exactly as given (see `upsert`). */
export function rename(origin: string, label: string, storage: Pick<Storage, 'getItem' | 'setItem'> = safeStorage()): Bookmark[] {
  const bookmarks = withRenamed(list(storage), origin, label)
  save(bookmarks, storage)
  return bookmarks
}

/** The label a fresh bookmark gets: the administrator's name if the server has one; "Shared on this computer" for a
 *  server on this computer seen from a plain browser tab, which cannot tell whose it is (E8.5, D1623; it was "This
 *  computer", D243); else its own host. `t` is the translator (the language now, unless a test gives another). */
export function defaultLabel(origin: string, administrator: string | null, t: typeof translate = translate): string {
  if (administrator) return t('{administrator}\'s server', { administrator })
  try {
    const host = new URL(origin).hostname
    if (host === 'localhost' || host === '[::1]' || /^127\./.test(host)) return t('Shared on this computer')
    return new URL(origin).host
  } catch {
    return origin
  }
}

/** A place as the page names it: her own server, whatever a desktop shell called it, is "Private on this computer" in
 *  her language (E8.5, D1623), and the computer's shared service "Shared on this computer" -- also once it has an
 *  administrator -- unless a person renamed it; every other place keeps its label. */
export function named(bookmark: Bookmark, t: typeof translate = translate): Bookmark {
  if (bookmark.local) return { ...bookmark, label: t('Private on this computer') }
  if (bookmark.shared && !bookmark.custom) return { ...bookmark, label: t('Shared on this computer') }
  return bookmark
}

/** Where that server's settings pages are: a plain navigation, same origin as everything they serve (D115-style). */
export function adminUrl(origin: string): string {
  return `${origin}/admin/`
}

/** What "+ Connect to a server…" turns typed text into: an origin to navigate to, or `null` for blank input. A bare
 * host or `host:port` gets the page's own scheme; anything that already names one (`http://` on a loopback dev
 * server, say) is kept exactly as typed rather than silently upgraded to `pageProtocol`. */
export function normalizeServerInput(input: string, pageProtocol: string): string | null {
  const trimmed = input.trim()
  if (!trimmed) return null
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `${pageProtocol}//${trimmed}`
  return withScheme.replace(/\/+$/, '')
}
