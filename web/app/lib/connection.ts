// Pure helpers for the connection health indicator (E3.11, "knowing which server you're on" — canvas note s5): which
// server a session is actually showing, in what words, and where its settings pages are. Kept free of Vue and the
// DOM so they're tested directly; ConnectionIndicator.vue only wires these to the button and its tooltip.
import { adminUrl, list as listBookmarks, type Bookmark } from './server-bookmarks'
import type { BaseState } from './base-session'

export type ConnectionStatus = BaseState['status']

/** The server a session is actually talking to, as an origin (`protocol://host`). `host` is blank until a session
 * has one (base-session.ts's `SessionOptions.host`); the page's own host stands in until then — before the Open
 * dialog's `?server=`/bookmark switching, that is always the right answer anyway. */
export function resolveOrigin(host: string, protocol: string, pageHost: string): string {
  return `${protocol}//${host || pageHost}`
}

/** The label to show for `origin`: a bookmark's own label (server-bookmarks.ts) once one exists for it — set the
 * moment it is first connected to and renamed at will from then on — or else its bare host, same as a fresh
 * bookmark's own default before anyone names it. */
export function friendlyLabel(origin: string, host: string, bookmarks: Bookmark[] = listBookmarks()): string {
  return bookmarks.find((b) => b.origin === origin)?.label ?? host
}

/** The tooltip's status line, before any latency reading is appended. */
export function statusWord(status: ConnectionStatus): string {
  switch (status) {
    case 'open':
      return 'Connected'
    case 'reconnecting':
      return 'Reconnecting…'
    case 'connecting':
      return 'Connecting…'
    default:
      return 'Offline'
  }
}

/** The health button's own `aria-label` — spoken on focus, before anyone opens the tooltip. */
export function indicatorLabel(label: string, status: ConnectionStatus): string {
  const word = status === 'open' ? 'healthy' : status === 'reconnecting' || status === 'connecting' ? 'reconnecting' : 'offline'
  return `Connection to ${label}: ${word}. Show details.`
}

/** Where that server's settings pages are, from the current page — a plain navigation, never an in-page fetch
 * (D115: page and socket share one origin; switching servers is always a full page load). */
export function manageUrl(origin: string): string {
  return adminUrl(origin)
}
