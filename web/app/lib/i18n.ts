// Catalog loading and lookup (E5.7, D31). The single source of truth for every translatable string is a gettext
// `.po` file, shared with the Gtk client; `scripts/po_to_json.py` derives the JSON this module reads from it at
// build time, so there is one place to edit a string and no second catalog to keep in sync. No `.po` has any real
// translations yet (nothing has moved off plain English text), so `loadCatalog` finding nothing is the normal case
// today, not a bug: `translator` falls back to the English text it is given.

export type Catalog = Record<string, string>

/** Fetch the catalog for `locale` (as `po_to_json.py` writes it, normally under `/i18n/<locale>.json`). An empty
 *  catalog — not an error — if there is none yet, the locale is 'en' (the source language needs no catalog), or the
 *  fetch fails for any reason (offline, 404, bad JSON): a missing translation must never block the app. */
export async function loadCatalog(locale: string, base = '/i18n', fetchImpl: typeof fetch = fetch): Promise<Catalog> {
  if (locale === 'en') return {}
  try {
    const response = await fetchImpl(`${base}/${locale}.json`)
    if (!response.ok) return {}
    const data: unknown = await response.json()
    return isCatalog(data) ? data : {}
  } catch {
    return {}
  }
}

function isCatalog(value: unknown): value is Catalog {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((v) => typeof v === 'string')
  )
}

/** `t('Save')`, or `t('Hello {name}', { name })` for a string with `{placeholder}`s (kept simple on purpose, so the
 *  same substitution works the same way in the Python catalog — see `po_to_json.py`'s docstring). A `msgid` the
 *  catalog does not have renders as itself: that is what makes this safe to use before any catalog exists. */
export function createTranslator(catalog: Catalog): (msgid: string, vars?: Record<string, string | number>) => string {
  return (msgid, vars) => {
    const template = catalog[msgid] ?? msgid
    if (!vars) return template
    return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match))
  }
}
