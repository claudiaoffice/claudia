// Which servers a Claudia client may connect to, and the list of them that it remembers (E5.8). No Node or browser
// import beyond `node:net` for IP syntax; no network. Port of clients/linux/src/claudia_shell_gtk/servers.py.
//
// Two rules live here, both about what a person can type or a page can ask for:
//  - an **address** names one origin (`https://host:port`) and nothing else. Plain `http` is only for this
//    computer, so a password or a document never crosses a network unencrypted because of a typing slip;
//  - the **list** of servers is the shell's, not the page's: the page may rename entries and hand a list back, but
//    only what passes `sanitize` is ever kept, at most `MAX_SERVERS` of them, and this computer's own server --
//    whose port changes with every start -- is never written down (`forPage` adds it fresh each time).
//
// An entry has the shape of the web app's own bookmark (`web/app/lib/server-bookmarks.ts`): `origin`, `label` and
// `custom` (true once a person has named it), plus `local` for this computer's own server.

import { isIP } from 'node:net'

export const MAX_SERVERS = 64
export const MAX_LABEL = 128
export const MAX_ADDRESS = 255

export type Entry = { origin: string; label: string; custom: boolean; local?: boolean }

export class AddressRefused extends Error {
  constructor(
    readonly code: 'bad_address' | 'insecure',
    message: string,
  ) {
    super(message)
    this.name = 'AddressRefused'
  }
}

export interface Address {
  readonly scheme: 'http' | 'https'
  /** Lower case; an IPv6 address without its brackets. */
  readonly host: string
  /** `null` for the scheme's own port (80 or 443). */
  readonly port: number | null
  /** `https://demo.example.org:8420` -- the one canonical spelling, and the key everything else is stored by. */
  readonly origin: string
  /** Does this address reach only the computer the client runs on? */
  readonly isLoopback: boolean
}

const DEFAULT_PORTS = { http: 80, https: 443 } as const
const BARE_HOST = /^(\[[0-9A-Fa-f:.]+\]|[^:/\s[\]]+)(:\d+)?$/
const DNS_NAME = /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$/

/** `localhost` and the loopback addresses (127.0.0.0/8, ::1) -- not names that merely start like them. */
export function isLoopbackHost(host: string): boolean {
  if (host === 'localhost') return true
  const kind = isIP(host)
  if (kind === 4) return host.split('.')[0] === '127'
  if (kind === 6) {
    const lower = host.toLowerCase()
    return lower === '::1' || /^::ffff:127\./.test(lower) || /^(0:){6}0?:?0*1$/.test(lower) || lower === '0:0:0:0:0:0:0:1'
  }
  return false
}

const badAddress = (): AddressRefused =>
  new AddressRefused('bad_address', 'Type the address of a server, such as demo.example.org:8420.')

function validHost(host: string): boolean {
  return DNS_NAME.test(host) || isIP(host) !== 0
}

/** The server that `raw` names, or `AddressRefused`.
 *
 * A bare `host` or `host:port` gets `defaultScheme` -- `https`, never something weaker. Anything but a plain
 * origin is refused: other schemes, a user name or password, a path, a query, a fragment, a bad port, a host that
 * is not a DNS name or an IP address (an internationalised name has to be typed in its `xn--` form), and plain
 * `http` to anything but this computer. */
export function parseAddress(raw: string, defaultScheme: 'http' | 'https' = 'https'): Address {
  let input = raw.trim()
  // eslint-disable-next-line no-control-regex
  if (!input || input.length > MAX_ADDRESS || /[^\x00-\x7f]/.test(input)) throw badAddress() // an internationalised name is typed as xn--
  if (!input.includes('://')) {
    if (!BARE_HOST.test(input)) throw badAddress() // also catches "javascript:alert(1)": a scheme is only taken from "scheme://"
    input = `${defaultScheme}://${input}`
  }
  let url: URL
  try {
    url = new URL(input)
  } catch {
    throw badAddress()
  }
  const scheme = url.protocol.slice(0, -1)
  if (scheme !== 'http' && scheme !== 'https') throw badAddress()
  let host = url.hostname.toLowerCase()
  if (host.startsWith('[') && host.endsWith(']')) host = host.slice(1, -1)
  let port: number | null = url.port === '' ? null : Number(url.port)
  if (
    url.username !== '' ||
    url.password !== '' ||
    !host ||
    !validHost(host) ||
    (url.pathname !== '' && url.pathname !== '/') ||
    url.search !== '' ||
    url.hash !== '' ||
    port === 0 ||
    input.includes('?') ||
    input.includes('#')
  ) {
    throw badAddress()
  }
  // WHATWG URL drops a port that is the scheme's default; an explicit 80/443 on the other scheme stays.
  if (port === DEFAULT_PORTS[scheme]) port = null
  const loopback = isLoopbackHost(host)
  if (scheme === 'http' && !loopback) {
    throw new AddressRefused('insecure', 'Use https:// — plain http is only allowed for this computer.')
  }
  const shown = host.includes(':') ? `[${host}]` : host
  return {
    scheme,
    host,
    port,
    origin: `${scheme}://${shown}${port !== null ? `:${port}` : ''}`,
    isLoopback: loopback,
  }
}

// --------------------------------------------------------------------------------------------------- lists

/** The name a server gets until a person renames it: its host and port. */
export function defaultLabel(origin: string): string {
  try {
    return new URL(origin).host || origin
  } catch {
    return origin
  }
}

/** What may be remembered of `raw` -- a list from the settings file or one that the page sent.
 *
 * Entries that are not a valid origin are dropped, origins are made canonical, a server stays in the list once (the
 * first wins), a missing or unusable label becomes the default one, a long one is cut, this computer's own entry
 * is never kept, and the list is cut at `MAX_SERVERS`. Anything that is not a list is no list at all. */
export function sanitize(raw: unknown): Entry[] {
  if (!Array.isArray(raw)) return []
  const kept: Entry[] = []
  const seen = new Set<string>()
  for (const item of raw) {
    if (typeof item !== 'object' || item === null || Array.isArray(item)) continue
    const entry = item as Record<string, unknown>
    if (entry.local === true || typeof entry.origin !== 'string') continue
    if (!entry.origin.includes('://')) continue // a stored origin names its scheme; only what a person types may be bare
    let origin: string
    try {
      origin = parseAddress(entry.origin).origin
    } catch {
      continue
    }
    if (seen.has(origin)) continue
    seen.add(origin)
    const label =
      typeof entry.label === 'string' && entry.label.trim() ? entry.label.trim().slice(0, MAX_LABEL) : defaultLabel(origin)
    kept.push({ origin, label, custom: entry.custom === true })
    if (kept.length === MAX_SERVERS) break
  }
  return kept
}

/** The list the page shows: this computer's server first (when there is one), then the remembered ones. The local
 * entry is named by the shell and never by the page (`custom`), and a remembered entry at the same address -- left
 * over from an earlier start that happened to get the same port -- is not shown a second time. */
export function forPage(saved: readonly Entry[], options: { localOrigin: string | null; localLabel: string }): Entry[] {
  const shown: Entry[] = []
  if (options.localOrigin !== null) {
    shown.push({ origin: options.localOrigin, label: options.localLabel, custom: true, local: true })
  }
  for (const entry of saved) if (entry.origin !== options.localOrigin) shown.push({ ...entry })
  return shown
}

/** `saved` with the server at `origin` added when it is not in it yet. What is there already stays as it is, so a
 * name a person gave a server is never replaced by the default one. */
export function remember(saved: readonly Entry[], origin: string): Entry[] {
  const kept = saved.map((entry) => ({ ...entry }))
  const canonical = parseAddress(origin).origin
  if (kept.every((entry) => entry.origin !== canonical)) {
    kept.push({ origin: canonical, label: defaultLabel(canonical), custom: false })
  }
  return kept
}
