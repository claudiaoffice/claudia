// The person's locale (E5.7, D31): always a client setting, never stored on the server (a document's users are
// scoped to that document, D35, so there is no account profile to keep it on). The default is the OS or browser
// locale; `setLocale` is how a later Config menu item overrides it. Nothing is translated with this yet — see i18n.ts
// for the (also still-empty) catalog loader this feeds.
//
// None of this assumes a browser: `currentLocale` and friends are also called from plain unit tests and (through
// `people.ts`'s default parameters) from any code that formats a date, so they read `navigator`/`localStorage`
// only behind a `typeof` guard and fall back to the default locale where neither exists, rather than throwing.

const STORAGE_KEY = 'claudia:locale'
const DEFAULT_LOCALE = 'en'

/** A locale tag is well-formed enough to pick a catalog with: loose on purpose (BCP-47-ish, not a full parser). */
export function isLocaleTag(value: string): boolean {
  return /^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$/.test(value)
}

/** The browser/OS locale, normalized to a bare tag ('de-DE'), or the default if there is none to read. Pass `nav`
 *  in a test instead of relying on a real `navigator`. */
export function detectLocale(nav?: Pick<Navigator, 'language'>): string {
  const source = nav ?? (typeof navigator !== 'undefined' ? navigator : undefined)
  const tag = source?.language
  return typeof tag === 'string' && isLocaleTag(tag) ? tag : DEFAULT_LOCALE
}

// Generic so each caller can ask for only the one or two Storage methods it actually uses (real `localStorage`
// satisfies any such subset, so the fallback below fits every call site).
function storage<T>(given: T | undefined): T | Storage | undefined {
  return given ?? (typeof localStorage !== 'undefined' ? localStorage : undefined)
}

/** The override the person picked for themselves, if any and still well-formed; `null` otherwise. No storage to
 *  read from (no browser, or reading it throws — private browsing, a blocked origin) is "no override", not an
 *  error here. */
export function storedLocale(given?: Pick<Storage, 'getItem'>): string | null {
  const s = storage(given)
  if (!s) return null
  try {
    const value = s.getItem(STORAGE_KEY)
    return value !== null && isLocaleTag(value) ? value : null
  } catch {
    return null
  }
}

/** Remember an override for next time. Throws only if `locale` is not a usable tag; no storage to write to, or a
 *  write that fails, is swallowed (the same as `storedLocale` finding nothing). */
export function setLocale(locale: string, given?: Pick<Storage, 'setItem'>): void {
  if (!isLocaleTag(locale)) throw new Error(`not a locale tag: ${locale}`)
  const s = storage(given)
  try {
    s?.setItem(STORAGE_KEY, locale)
  } catch {
    // ignored: see above
  }
}

/** Forget the override, back to following the OS/browser locale. */
export function clearLocale(given?: Pick<Storage, 'removeItem'>): void {
  const s = storage(given)
  try {
    s?.removeItem(STORAGE_KEY)
  } catch {
    // ignored, as in setLocale
  }
}

/** What to use right now: the person's own override if they set one, else the OS/browser locale, else the
 *  default — safe to call from anywhere, including outside a browser. */
export function currentLocale(): string {
  return storedLocale() ?? detectLocale()
}
