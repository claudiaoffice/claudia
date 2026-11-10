// Catalog loading and lookup (E5.7, D31). The single source of truth for every translatable string is a gettext
// `.po` file, shared with the Gtk client; `scripts/po_to_json.py` derives the JSON this module reads from it at
// build time, so there is one place to edit a string and no second catalog to keep in sync. `useI18n`, at the foot
// of this file, is where the owner's second i18n round (D148's groundwork, D160) actually moved menu chrome into
// this pipeline — before it, `loadCatalog` finding nothing was the normal case for every locale, not just 'en'.

export type Catalog = Record<string, string>

/** The language picker's own short, explicit list (Config ▸ App Language): the same two entries
 * `manifest.LANGUAGES` lists for the Linux client (kept in sync by hand — there is no shared manifest between the
 * two shells, the same as `about_links()`'s three links). Each entry's own name is its autonym ("Deutsch", not
 * "German" from an English catalog); `t()` must never be called on one, the same universal convention every OS
 * and browser language picker already follows (`manifest.py`'s docstring). */
export const LANGUAGES: ReadonlyArray<readonly [tag: string, autonym: string]> = [
  ['en', 'English'],
  ['de', 'Deutsch'],
]

/** The App Language a locale tag means: the `LANGUAGES` entry with the same tag, else the one with its language
 *  (`de-AT` reads German), else English, the source language. A browser reports a regional tag (`en-US`,
 *  `de-DE`); catalogs and the Config ▸ App Language menu are per language. */
export function appLanguage(locale: string): string {
  const tags = LANGUAGES.map(([tag]) => tag)
  const lower = locale.toLowerCase()
  return tags.find((tag) => tag === lower) ?? tags.find((tag) => tag === lower.split('-')[0]) ?? 'en'
}

/** Fetch the catalog for `locale`'s App Language (as `po_to_json.py` writes it, under `/i18n/<language>.json`).
 *  An empty catalog — not an error — for English (the source language needs no catalog, so nothing is fetched and
 *  a browser in `en-US` asks for no `en-US.json` that does not exist), or when the fetch fails for any reason
 *  (offline, 404, bad JSON): a missing translation must never block the app. */
export async function loadCatalog(locale: string, base = '/i18n', fetchImpl: typeof fetch = fetch): Promise<Catalog> {
  const language = appLanguage(locale)
  if (language === 'en') return {}
  try {
    const response = await fetchImpl(`${base}/${language}.json`)
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

// ------------------------------------------------------------------------------------------------------- Vue wiring
import { onMounted, ref, triggerRef } from 'vue'
import { currentLocale, setLocale as persistLocale } from './locale'

/**
 * The Config ▸ App Language menu's own state (the owner's second i18n round, D160): a `locale` ref every
 * workspace's `menus` computed reads from (so every `config.language.<tag>` item's own `checked` recomputes from
 * this one ref — `manifest.py`'s own docstring describes the same "one ref, no special-cased mutual exclusion"
 * design for the Linux client's native menu), and a `t` that looks up the *currently loaded* catalog, so a
 * `computed<Menu[]>` that calls it is automatically re-run once `choose` finishes loading a new one.
 *
 * Deliberately not reactive-on-every-letter: `t` is read many times while building one `menus` array, so it stays
 * a plain function closed over `catalog.value` (re-reading it fresh on every call) rather than, say, a `computed`
 * per string — there is no per-string computed to invalidate, only the one `catalog` ref the whole menu bar
 * depends on together.
 */
export function useI18n() {
  // The App Language, not the raw browser tag: the menu checks one of its own entries, never none of them.
  const locale = ref(appLanguage(currentLocale()))
  const catalog = ref<Catalog>({})

  async function loadFor(tag: string): Promise<void> {
    catalog.value = await loadCatalog(tag)
  }

  onMounted(() => void loadFor(locale.value))

  // Not named `t` here: `scripts/extract_i18n.py`'s regex looks for the literal text "t(" with nothing word-like
  // or a dot right before it, which a `function t(...)` *declaration* satisfies just as well as a real call does
  // (the lookbehind only rules out `format(`-style false positives, not this one) — the function is exposed as
  // `t` only on the object `useI18n` returns, below, never declared under that name itself.
  function translate(msgid: string, vars?: Record<string, string | number>): string {
    return createTranslator(catalog.value)(msgid, vars)
  }

  /** Picks `tag` as the active language: persists it, switches `locale` (so every `checked` built from it
   * recomputes), and loads its catalog. `triggerRef` also fires that recompute when `tag` was already active —
   * a native shell's own menu item optimistically unchecks itself on *any* activation, checked ones included
   * (`window.py`'s `_on_change_state`), before the page's next `action_state` report corrects it back; without
   * this, re-picking the already-active language would leave that native checkmark stuck off, since a ref
   * assignment Vue sees as unchanged triggers no dependents and so sends no correcting report at all. */
  async function choose(tag: string): Promise<void> {
    const changed = tag !== locale.value
    persistLocale(tag)
    locale.value = tag
    if (changed) await loadFor(tag)
    triggerRef(locale)
  }

  return { locale, t: translate, choose }
}
