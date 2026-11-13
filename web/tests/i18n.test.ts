import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LANGUAGES, appLanguage, createTranslator, loadCatalog, translate, useI18n } from '~/lib/i18n'
import { currentLocale } from '~/lib/locale'

function fakeFetch(responses: Record<string, unknown>): typeof fetch {
  return (async (input: string | URL | Request) => {
    const url = String(input)
    const body = responses[url]
    if (body === undefined) return new Response(null, { status: 404 })
    return new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
  }) as typeof fetch
}

describe('appLanguage', () => {
  it('is the App Language entry for a locale tag, region and case aside', () => {
    expect(appLanguage('de')).toBe('de')
    expect(appLanguage('de-DE')).toBe('de')
    expect(appLanguage('DE-at')).toBe('de')
    expect(appLanguage('en-US')).toBe('en')
  })

  it('falls back to English, the source language, for a language Claudia has no catalog for', () => {
    expect(appLanguage('fr-FR')).toBe('en')
    expect(appLanguage('')).toBe('en')
  })
})

describe('loadCatalog', () => {
  it('never fetches for a regional English such as en-US (a browser default): there is no en-US.json', async () => {
    // Counted, not thrown: `loadCatalog` swallows a failing fetch, so a throwing stub could not tell the difference.
    const asked: string[] = []
    const fetchImpl = (async (input: string | URL | Request) => {
      asked.push(String(input))
      return new Response(null, { status: 404 })
    }) as typeof fetch
    expect(await loadCatalog('en-US', '/i18n', fetchImpl)).toEqual({})
    expect(asked).toEqual([])
  })

  it("reads a regional tag from its language's catalog: de-DE is de.json", async () => {
    const catalog = await loadCatalog('de-DE', '/i18n', fakeFetch({ '/i18n/de.json': { Save: 'Speichern' } }))
    expect(catalog).toEqual({ Save: 'Speichern' })
  })


  it('never fetches for en, the source language', async () => {
    const asked: string[] = []
    const fetchImpl = (async (input: string | URL | Request) => {
      asked.push(String(input))
      return new Response(null, { status: 404 })
    }) as typeof fetch
    expect(await loadCatalog('en', '/i18n', fetchImpl)).toEqual({})
    expect(asked).toEqual([])
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

  it('starts at the App Language of the current locale and falls back to the msgid before any catalog has loaded', () => {
    // Not asserting a specific tag: Node 21+ exposes a minimal global `navigator` of its own (`locale.test.ts`'s
    // own caveat), so `currentLocale()` reads whatever that reports, not necessarily 'en'. Whatever it is, the
    // menu needs one of its own entries checked, so `locale` is always one of LANGUAGES' tags.
    const i18n = useI18n()
    expect(i18n.locale.value).toBe(appLanguage(currentLocale()))
    expect(LANGUAGES.map(([tag]) => tag)).toContain(i18n.locale.value)
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

describe('one language for the whole page', () => {
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  // `choose` loads a catalog only when the language changes, so every test starts from English.
  beforeEach(() => useI18n().choose('en'))

  async function choosingGerman(catalog: Record<string, string>) {
    const real = globalThis.fetch
    globalThis.fetch = (async () => new Response(JSON.stringify(catalog), { status: 200 })) as typeof fetch
    try {
      await useI18n().choose('de')
    } finally {
      globalThis.fetch = real
    }
  }

  it('lets a component that never chose anything read the language another one chose', async () => {
    const dialog = useI18n()
    const menu = useI18n()
    await choosingGerman({ Save: 'Speichern' })
    expect(menu.locale.value).toBe('de')
    expect(dialog.locale.value).toBe('de')
    expect(dialog.t('Save')).toBe('Speichern')
    expect(menu.t('Save')).toBe('Speichern')
  })

  it('lets a plain module translate with the same catalog, through `translate`', async () => {
    await choosingGerman({ Save: 'Speichern', 'Hello {name}': 'Hallo {name}' })
    expect(translate('Save')).toBe('Speichern')
    expect(translate('Hello {name}', { name: 'Ann' })).toBe('Hallo Ann')
    expect(translate('Not in the catalog')).toBe('Not in the catalog')
  })

  it('goes back to the msgids when English is chosen again', async () => {
    await choosingGerman({ Save: 'Speichern' })
    await useI18n().choose('en')
    expect(translate('Save')).toBe('Save')
  })
})
