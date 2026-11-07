import { describe, expect, it, vi } from 'vitest'
import { clearLocale, currentLocale, detectLocale, isLocaleTag, setLocale, storedLocale } from '~/lib/locale'

function fakeStorage(initial: Record<string, string> = {}) {
  const data = { ...initial }
  return {
    getItem: (key: string) => data[key] ?? null,
    setItem: (key: string, value: string) => {
      data[key] = value
    },
    removeItem: (key: string) => {
      delete data[key]
    },
  }
}

describe('isLocaleTag', () => {
  it('accepts BCP-47-ish tags', () => {
    for (const tag of ['en', 'de', 'de-DE', 'pt-BR', 'zh-Hans']) expect(isLocaleTag(tag)).toBe(true)
  })
  it('rejects anything else', () => {
    for (const bad of ['', 'not a locale!', 'de_DE', 'x'.repeat(50)]) expect(isLocaleTag(bad)).toBe(false)
  })
})

describe('detectLocale', () => {
  it('reads navigator.language when it is a usable tag', () => {
    expect(detectLocale({ language: 'de-DE' })).toBe('de-DE')
  })
  it('falls back to en when the given navigator has no usable language', () => {
    expect(detectLocale({ language: '' })).toBe('en')
  })
  it('falls back to en when there is no navigator at all to read', () => {
    // Node itself exposes a minimal global `navigator` (with a real `.language`) from v21 on, so this
    // environment is not "no browser" by default — stub it away to exercise that case deliberately.
    vi.stubGlobal('navigator', undefined)
    expect(detectLocale(undefined)).toBe('en')
    vi.unstubAllGlobals()
  })
})

describe('stored/set/clearLocale', () => {
  it('round-trips an override through the given storage', () => {
    const store = fakeStorage()
    expect(storedLocale(store)).toBeNull()
    setLocale('fr', store)
    expect(storedLocale(store)).toBe('fr')
    clearLocale(store)
    expect(storedLocale(store)).toBeNull()
  })
  it('refuses to store something that is not a locale tag', () => {
    expect(() => setLocale('nope!', fakeStorage())).toThrow()
  })
  it('ignores a stored value that is not a well-formed tag', () => {
    expect(storedLocale(fakeStorage({ 'claudia:locale': 'nope!' }))).toBeNull()
  })
  it('treats a storage read that throws as no override, not an error', () => {
    const angry = {
      getItem: () => {
        throw new Error('blocked')
      },
    }
    expect(storedLocale(angry)).toBeNull()
  })
  it('works with no storage available at all (outside a browser)', () => {
    expect(storedLocale(undefined)).toBeNull()
  })
})

describe('currentLocale', () => {
  it('is callable with no arguments outside a browser and does not throw', () => {
    expect(() => currentLocale()).not.toThrow()
    expect(typeof currentLocale()).toBe('string')
  })
})

describe('setLocale swallows a storage failure on write', () => {
  it('does not throw even if the underlying storage does', () => {
    const angry = {
      setItem: () => {
        throw new Error('full')
      },
    }
    expect(() => setLocale('de', angry)).not.toThrow()
  })
})
