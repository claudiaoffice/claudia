// Catalog loading and lookup (E5.7, D31). The single source of truth for every translatable string is a gettext
// `.po` file, shared with the Gtk client; `scripts/po_to_json.py` derives the JSON this module reads from it at
// build time, so there is one place to edit a string and no second catalog to keep in sync. `useI18n`, at the foot
// of this file, is where the owner's second i18n round (D148's groundwork, D160) actually moved menu chrome into
// this pipeline — before it, `loadCatalog` finding nothing was the normal case for every locale, not just 'en'.
import { onMounted, ref, shallowRef, triggerRef, watch } from 'vue' // only the Vue wiring at the end uses these
import { currentLocale, setLocale as persistLocale } from './locale'

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

/** The language the words on the screen are really in (WCAG 3.1.1): the App Language of `locale` once its catalog has
 *  loaded, else English, which is what every string renders as while a catalog is missing. This, not the browser's
 *  own tag, is what the page's `lang` must say, because a screen reader chooses its voice by it. */
export function languageOf(locale: string, catalog: Catalog): string {
  const language = appLanguage(locale)
  return language === 'en' || Object.keys(catalog).length > 0 ? language : 'en'
}

/** Declares the page's language (`<html lang>`). `root` is the page's root element; without one, and outside a
 *  browser, there is nothing to declare it on. */
export function setPageLanguage(language: string, root?: { lang: string }): void {
  const element = root ?? (typeof document !== 'undefined' ? document.documentElement : undefined)
  if (element) element.lang = language
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

// One language and one catalog for the whole page, shared by every component and every plain module (D160's
// first round gave each `useI18n()` call its own, so only the workspace that called `choose` switched live; the
// side panel, the dialogs and the session's notices would have stayed in the old language). `shallowRef`: the
// catalog is replaced whole, never edited, so Vue need not make a few hundred entries deeply reactive.
const activeLocale = ref(appLanguage(currentLocale()))
const activeCatalog = shallowRef<Catalog>({})
let loadedFor: string | null = null
let loading: Promise<void> | null = null

async function loadFor(tag: string): Promise<void> {
  activeCatalog.value = await loadCatalog(tag)
  loadedFor = tag
  setPageLanguage(languageOf(tag, activeCatalog.value))
}

/** Loads the active language's catalog unless it is loaded already (or being loaded). Every component's `onMounted`
 * calls this, so the first one to mount does the fetch and the rest find it done. */
function ensureLoaded(): Promise<void> {
  if (loadedFor === activeLocale.value) return Promise.resolve()
  loading ??= loadFor(activeLocale.value).finally(() => {
    loading = null
  })
  return loading
}

/**
 * Translate `msgid` with the catalog of the language that is active *now*. Reading `activeCatalog.value` is what
 * makes a template or `computed` that calls this re-render when `choose` loads another language. Plain modules
 * (the sessions' notices, the menu builders) import it as ``import { translate as t } from './i18n'`` so that
 * `scripts/extract_i18n.py`, which only recognises an unqualified `t(...)` call, still finds their strings.
 */
export function translate(msgid: string, vars?: Record<string, string | number>): string {
  return createTranslator(activeCatalog.value)(msgid, vars)
}

/** The App Language now, a tag such as `de`: what a session tells the server to speak to this window (D323). */
export function languageNow(): string {
  return activeLocale.value
}

/** Calls `handler` with the tag of the App Language each time it is chosen; returns what stops it. A plain module
 * (a session) listens with this instead of calling `useI18n()`, which belongs to a component. */
export function onLanguageChange(handler: (tag: string) => void): () => void {
  return watch(activeLocale, (tag) => handler(tag))
}

/**
 * The App Language (the Config ▸ App Language menu's own state, D160): the shared `locale` ref every workspace's
 * `menus` computed reads (so every `config.language.<tag>` item's `checked` recomputes from this one ref —
 * `manifest.py`'s docstring describes the same "one ref, no special-cased mutual exclusion" design for the Linux
 * client's native menu), `t` for the catalog loaded now, and `choose` to switch.
 */
export function useI18n() {
  onMounted(() => void ensureLoaded())

  // Exposed as `t` only on the object returned below, never declared under that name: the extractor's regex would
  // take a `function t(...)` *declaration* for a call (the module's `translate` above is the declaration).
  /** Picks `tag` as the active language: persists it, switches `locale` (so every `checked` built from it
   * recomputes), and loads its catalog. `triggerRef` also fires that recompute when `tag` was already active —
   * a native shell's own menu item optimistically unchecks itself on *any* activation, checked ones included
   * (`window.py`'s `_on_change_state`), before the page's next `action_state` report corrects it back; without
   * this, re-picking the already-active language would leave that native checkmark stuck off, since a ref
   * assignment Vue sees as unchanged triggers no dependents and so sends no correcting report at all. */
  async function choose(tag: string): Promise<void> {
    const changed = tag !== activeLocale.value
    persistLocale(tag)
    activeLocale.value = tag
    if (changed) await loadFor(tag)
    else setPageLanguage(languageOf(tag, activeCatalog.value)) // (`loadFor` declares it when the language changes)
    triggerRef(activeLocale)
  }

  return { locale: activeLocale, t: translate, choose }
}
