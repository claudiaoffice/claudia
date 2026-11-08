import { describe, expect, it, vi } from 'vitest'
import { LANGUAGES, createTranslator, loadCatalog, useI18n } from '~/lib/i18n'
import { currentLocale } from '~/lib/locale'

function fakeFetch(responses: Record<string, unknown>): typeof fetch {
  return (async (input: string | URL | Request) => {
    const url = String(input)
    const body = responses[url]
    if (body === undefined) return new Response(null, { status: 404 })
    return new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
  }) as typeof fetch
}

describe('loadCatalog', () => {
  it('never fetches for en, the source language', async () => {
    const fetchImpl = (() => {
      throw new Error('should not be called')
    }) as unknown as typeof fetch
    expect(await loadCatalog('en', '/i18n', fetchImpl)).toEqual({})
  })

  it('returns the catalog it finds', async () => {
    const catalog = await loadCatalog('de', '/i18n', fakeFetch({ '/i18n/de.json': { Save: 'Speichern' } }))
    expect(catalog).toEqual({ Save: 'Speichern' })
  })

  it('returns an empty catalog, not an error, when there is none yet (no .po has been translated)', async () => {
    expect(await loadCatalog('fr', '/i18n', fakeFetch({}))).toEqual({})
  })

  it('returns an empty catalog for a response that is not a string-to-string object', async () => {
    expect(await loadCatalog('de', '/i18n', fakeFetch({ '/i18n/de.json': ['not', 'a', 'catalog'] }))).toEqual({})
    expect(await loadCatalog('de', '/i18n', fakeFetch({ '/i18n/de.json': { count: 3 } }))).toEqual({})
  })

  it('returns an empty catalog rather than throwing when the fetch itself fails', async () => {
    const fetchImpl = (async () => {
      throw new Error('offline')
    }) as unknown as typeof fetch
    expect(await loadCatalog('de', '/i18n', fetchImpl)).toEqual({})
  })
})

describe('createTranslator', () => {
  it('renders a known msgid from the catalog', () => {
    const t = createTranslator({ Save: 'Speichern' })
    expect(t('Save')).toBe('Speichern')
  })

  it('falls back to the msgid itself when the catalog does not have it', () => {
    const t = createTranslator({})
    expect(t('Save')).toBe('Save')
  })

  it('substitutes {placeholder}s from vars', () => {
    const t = createTranslator({ 'Hello {name}': 'Hallo {name}' })
    expect(t('Hello {name}', { name: 'Ann' })).toBe('Hallo Ann')
  })

  it('leaves a placeholder untouched when vars does not have it', () => {
    const t = createTranslator({})
    expect(t('Hello {name}', { other: 1 })).toBe('Hello {name}')
  })

  it('accepts a numeric var', () => {
    const t = createTranslator({})
    expect(t('{count} items', { count: 3 })).toBe('3 items')
  })
})

describe('LANGUAGES', () => {
  it('lists English and German by their own autonyms, matching manifest.LANGUAGES', () => {
    expect(LANGUAGES).toEqual([
      ['en', 'English'],
      ['de', 'Deutsch'],
    ])
  })
})

describe('useI18n', () => {
  // `onMounted` warns (harmlessly) outside a component's `setup()` -- exercising `choose` directly, as the Config
  // menu's own action handler does, needs no component mount.
  vi.spyOn(console, 'warn').mockImplementation(() => {})

  it('starts at the current locale and falls back to the msgid itself before any catalog has loaded', () => {
    // Not asserting a specific tag: Node 21+ exposes a minimal global `navigator` of its own (`locale.test.ts`'s
    // own caveat), so `currentLocale()` reads whatever that reports, not necessarily 'en'.
    const i18n = useI18n()
    expect(i18n.locale.value).toBe(currentLocale())
    expect(i18n.t('Save')).toBe('Save')
  })

  it('choosing a language switches locale', async () => {
    const i18n = useI18n()
    await i18n.choose('de')
    expect(i18n.locale.value).toBe('de')
  })

  it('choosing the already-active language is harmless', async () => {
    const i18n = useI18n()
    const already = i18n.locale.value
    await i18n.choose(already)
    expect(i18n.locale.value).toBe(already)
  })
})
