// The setup code on the page (SEC-12, D1370–D1373): the server asks for it before anyone becomes its first
// administrator, and says it only where its operator looks. A page gets it two ways, and keeps it for this tab only
// (sessionStorage, never localStorage or a cookie; in memory where storage throws), until an administrator exists:
//
// * from a link of the server's log, `/admin#setup=<code>`: the fragment never reaches the server or a proxy, and
//   `takeCodeFromAddress` removes it from the address at once, so it is not bookmarked or shared by accident;
// * from the desktop app, which reads it in its own server's state folder and sends it in `welcome` (shell-bridge.ts).
//
// The server compares codes the same way (`claudia_server.setup_code.normalize`).

import { safeSessionStorage, type Store } from './storage'

export type CodeSource = 'link' | 'app'
export interface GivenCode {
  code: string
  from: CodeSource
}
/** Was a given code accepted by the server (`POST /api/admin/setup-code`)? */
export type CodeCheck = 'unchecked' | 'ok' | 'refused'

const KEY = 'claudia.admin.setup-code'
const LOOK_ALIKES: Record<string, string> = { O: '0', I: '1', L: '1' }

/** A typed code as it is compared: upper case, without dashes and white space, O as 0, I and L as 1. */
export function normalizeSetupCode(text: string): string {
  return text
    .replace(/[\s-]/g, '')
    .toUpperCase()
    .replace(/[OIL]/g, (c) => LOOK_ALIKES[c] ?? c)
}

/** The code of a `#setup=…` fragment, if there is one; the fragment loses it right away (`history.replaceState`), and
 *  keeps anything else it had (`#fonts`). */
export function takeCodeFromAddress(
  loc: Pick<Location, 'pathname' | 'search' | 'hash'>,
  history: Pick<History, 'replaceState'>,
): string | null {
  if (!loc.hash.includes('setup=')) return null
  const parts = loc.hash.slice(1).split('&')
  const found = parts.find((part) => part.startsWith('setup='))
  if (found === undefined) return null
  const rest = parts.filter((part) => part !== found).join('&')
  history.replaceState(null, '', `${loc.pathname}${loc.search}${rest ? `#${rest}` : ''}`)
  const code = decodeURIComponent(found.slice('setup='.length))
  return code || null
}

// ------------------------------------------------------------------------------------------------------ remembering

let inMemory: GivenCode | null = null
const listeners = new Set<(given: GivenCode) => void>()

function isGiven(value: unknown): value is GivenCode {
  const v = value as GivenCode | null
  return !!v && typeof v.code === 'string' && (v.from === 'link' || v.from === 'app')
}

/** Keep `code` for this tab, and tell a page that waits for one (`onSetupCode`). */
export function rememberSetupCode(code: string, from: CodeSource, store: Store | null = safeSessionStorage()): void {
  const given = { code, from }
  inMemory = given
  try {
    store?.setItem(KEY, JSON.stringify(given))
  } catch {
    /* a private window: `inMemory` holds it for this page */
  }
  for (const listener of listeners) listener(given)
}

/** The code this tab was given, or `null`. */
export function rememberedSetupCode(store: Store | null = safeSessionStorage()): GivenCode | null {
  try {
    const raw = store?.getItem(KEY)
    if (raw == null) return store ? null : inMemory
    const value: unknown = JSON.parse(raw)
    return isGiven(value) ? value : null
  } catch {
    return inMemory
  }
}

/** Drop the code (an administrator exists now, or the person chose to type another). */
export function forgetSetupCode(store: Store | null = safeSessionStorage()): void {
  inMemory = null
  try {
    store?.removeItem(KEY)
  } catch {
    /* nothing to forget */
  }
}

/** Be told when a code arrives (the desktop app's welcome may come after the page has drawn); returns a remover. */
export function onSetupCode(listener: (given: GivenCode) => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

// ------------------------------------------------------------------------------------------------------- the field

/** What the setup page shows for the code: no field (the server asks for none, or the desktop app gave one that was
 *  not refused), the code from a link filled in, or a field to type it in. */
export function codeField(serverAsks: boolean, given: GivenCode | null, check: CodeCheck): 'none' | 'from-link' | 'typed' {
  if (!serverAsks) return 'none'
  if (given && check !== 'refused') return given.from === 'app' ? 'none' : 'from-link'
  return 'typed'
}
