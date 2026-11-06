import { describe, expect, it } from 'vitest'
import { applyTheme, readStoredTheme, resolvedTheme, storeTheme } from '~/lib/theme'

function memoryStorage() {
  const map = new Map<string, string>()
  return { getItem: (k: string) => map.get(k) ?? null, setItem: (k: string, v: string) => void map.set(k, v) }
}

describe('readStoredTheme / storeTheme', () => {
  it('defaults to system when nothing is stored', () => {
    expect(readStoredTheme(memoryStorage())).toBe('system')
  })
  it('round-trips a stored choice', () => {
    const storage = memoryStorage()
    storeTheme('dark', storage)
    expect(readStoredTheme(storage)).toBe('dark')
  })
  it('falls back to system for a value it does not recognise (an older or newer build)', () => {
    const storage = memoryStorage()
    storage.setItem('claudia.theme', 'solarized')
    expect(readStoredTheme(storage)).toBe('system')
  })
})

describe('resolvedTheme', () => {
  it('follows the system only when the choice is "system"', () => {
    expect(resolvedTheme('system', true)).toBe('dark')
    expect(resolvedTheme('system', false)).toBe('light')
  })
  it('an explicit choice overrides the system either way', () => {
    expect(resolvedTheme('dark', false)).toBe('dark')
    expect(resolvedTheme('light', true)).toBe('light')
  })
})

describe('applyTheme', () => {
  it('sets data-theme="dark" only for dark; light clears it rather than setting data-theme="light"', () => {
    const calls: string[] = []
    const root = {
      setAttribute: (n: string, v: string) => calls.push(`set ${n}=${v}`),
      removeAttribute: (n: string) => calls.push(`remove ${n}`),
    }
    applyTheme(root, 'dark')
    applyTheme(root, 'light')
    expect(calls).toEqual(['set data-theme=dark', 'remove data-theme'])
  })
})
