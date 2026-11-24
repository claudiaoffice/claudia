// CODE-36: the browser's storage is reached in one place. Before, six modules each had their own `safeStorage()` and
// three components their own `remembered()`, and they had drifted apart.
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it } from 'vitest'
import { remember, remembered, rememberedText, safeSessionStorage, safeStorage } from '~/lib/storage'
import { forgetBrowser, refuseEveryCall } from './refusing-browser'

const APP = fileURLToPath(new URL('../app', import.meta.url))

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return sources(path)
    return /\.(ts|vue)$/.test(entry.name) ? [path] : []
  })
}

/** The code of a file without its comments, which may well talk about `localStorage`. */
function code(path: string): string {
  return readFileSync(path, 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|\s)\/\/.*$/gm, '$1')
}

describe('where the browser storage is reached', () => {
  it('only lib/storage.ts defines safeStorage or remembered, or touches localStorage or sessionStorage', () => {
    const offenders = sources(APP)
      .filter((path) => !path.endsWith(join('lib', 'storage.ts')))
      .filter((path) => /function (safeStorage|remembered)\b|\b(localStorage|sessionStorage)\b/.test(code(path)))
      .map((path) => path.slice(APP.length + 1))
    expect(offenders).toEqual([])
  })
})

/** A browser that refuses its storage: reading `localStorage` or `sessionStorage` throws, as in a sandboxed frame. */
function refuseStorage() {
  for (const name of ['localStorage', 'sessionStorage']) {
    Object.defineProperty(globalThis, name, {
      configurable: true,
      get() {
        throw new Error('SecurityError')
      },
    })
  }
}

describe('safeStorage, where the browser has no storage or refuses it', () => {
  afterEach(forgetBrowser)

  it('without any storage, a key nobody set reads as null and nothing throws', () => {
    expect(() => safeStorage().setItem('claudia.test.absent', 'x')).not.toThrow()
    expect(safeStorage().getItem('claudia.test.never-set')).toBeNull()
    expect(safeSessionStorage().getItem('claudia.test.never-set')).toBeNull()
  })

  it('with a storage that throws when it is reached, a key nobody set reads as null and nothing throws', () => {
    refuseStorage()
    expect(() => safeStorage().getItem('claudia.test.never-set')).not.toThrow()
    expect(safeStorage().getItem('claudia.test.never-set')).toBeNull()
    expect(safeSessionStorage().getItem('claudia.test.never-set')).toBeNull()
  })

  it('what is remembered in a refusing browser holds for the rest of the page', () => {
    refuseStorage()
    remember('claudia.test.view', 'page')
    expect(remembered('claudia.test.view', ['flow', 'page'], 'flow')).toBe('page')
  })
})

describe('safeStorage, where the browser storage refuses a call', () => {
  afterEach(forgetBrowser)

  it('nothing throws, and what was written holds for the rest of the page until it is removed', () => {
    refuseEveryCall()
    for (const store of [safeStorage(), safeSessionStorage()]) {
      expect(() => store.setItem('claudia.test.refused', 'kept')).not.toThrow()
      expect(store.getItem('claudia.test.refused')).toBe('kept')
      expect(() => store.removeItem('claudia.test.refused')).not.toThrow()
      expect(store.getItem('claudia.test.refused')).toBeNull()
    }
  })

  it('a write the browser takes again wins over what the page held while it refused', () => {
    refuseEveryCall()
    safeStorage().setItem('claudia.test.later', 'held')
    const kept = new Map<string, string>()
    ;(globalThis as Record<string, unknown>).localStorage = {
      getItem: (k: string) => kept.get(k) ?? null,
      setItem: (k: string, v: string) => void kept.set(k, v),
      removeItem: (k: string) => void kept.delete(k),
    }
    safeStorage().setItem('claudia.test.later', 'stored')
    expect(kept.get('claudia.test.later')).toBe('stored')
    kept.set('claudia.test.later', 'from another tab')
    expect(safeStorage().getItem('claudia.test.later')).toBe('from another tab')
  })
})

describe('rememberedText', () => {
  it('reads the text kept under a key, and an empty text for a key nobody set', () => {
    remember('claudia.test.user', 'Ada')
    expect(rememberedText('claudia.test.user')).toBe('Ada')
    expect(rememberedText('claudia.test.nobody')).toBe('')
  })
})

describe('remembered', () => {
  afterEach(forgetBrowser)

  it('gives the fallback for a key nobody set, and for a value that is not allowed', () => {
    expect(remembered('claudia.test.unset', ['on', 'off'], 'off')).toBe('off')
    remember('claudia.test.odd', 'sideways')
    expect(remembered('claudia.test.odd', ['on', 'off'], 'off')).toBe('off')
  })

  it('reads the browser storage when it has one', () => {
    const kept = new Map([['claudia.test.kept', 'on']])
    ;(globalThis as Record<string, unknown>).localStorage = { getItem: (k: string) => kept.get(k) ?? null }
    expect(remembered('claudia.test.kept', ['on', 'off'], 'off')).toBe('on')
  })
})
