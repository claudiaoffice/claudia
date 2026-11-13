import { describe, expect, it, vi } from 'vitest'
import { LANGUAGES, appLanguage, createTranslator, languageOf, loadCatalog, setPageLanguage, useI18n } from '~/lib/i18n'
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

describe('languageOf', () => {
  // WCAG 3.1.1 (BITV 2.0): the page's `lang` is what a screen reader picks its voice by, so it must name the
  // language the words on the screen are really in, not the one that was asked for.
  it('is English for English, which needs no catalog', () => {
    expect(languageOf('en-US', {})).toBe('en')
  })

  it('is the App Language once its catalog has loaded', () => {
    expect(languageOf('de-DE', { Save: 'Speichern' })).toBe('de')
  })

  it('stays English while the German catalog is missing, because that is what is on the screen', () => {
    expect(languageOf('de', {})).toBe('en')
  })

  it('is English for a language the app does not have', () => {
    expect(languageOf('fr', { Save: 'Enregistrer' })).toBe('en')
  })
})

describe('setPageLanguage', () => {
  it('declares the language on the root element it is given', () => {
    const root = { lang: 'en' }
    setPageLanguage('de', root)
    expect(root.lang).toBe('de')
  })

  it('has nothing to declare it on outside a browser, and says nothing about that', () => {
    expect(() => setPageLanguage('de')).not.toThrow()
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

  it('declares the page language once the catalog for the chosen language has loaded', async () => {
    const root = { lang: 'en' }
    vi.stubGlobal('document', { documentElement: root })
    vi.stubGlobal('fetch', fakeFetch({ '/i18n/de.json': { Save: 'Speichern' } }))
    try {
      const i18n = useI18n()
      await i18n.choose('de')
      expect(root.lang).toBe('de')
      await i18n.choose('en')
      expect(root.lang).toBe('en')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('keeps the page English when the German catalog cannot be loaded', async () => {
    const root = { lang: 'en' }
    vi.stubGlobal('document', { documentElement: root })
    vi.stubGlobal('fetch', fakeFetch({}))
    try {
      await useI18n().choose('de')
      expect(root.lang).toBe('en')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('choosing the already-active language is harmless', async () => {
    const i18n = useI18n()
    const already = i18n.locale.value
    await i18n.choose(already)
    expect(i18n.locale.value).toBe(already)
  })
})
