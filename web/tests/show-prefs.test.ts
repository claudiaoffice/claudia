import { afterEach, describe, expect, it } from 'vitest'
import { readStoredNotes, storeNotes } from '~/lib/show-prefs'
import { forgetBrowser, refuseEveryCall } from './refusing-browser'

const memory = () => {
  const map = new Map<string, string>()
  return { getItem: (k: string) => map.get(k) ?? null, setItem: (k: string, v: string) => void map.set(k, v) }
}

describe('whether the speaker notes are shown', () => {
  afterEach(forgetBrowser)

  it('shows them until told not to', () => {
    expect(readStoredNotes(memory())).toBe(true)
  })
  it('remembers what was chosen', () => {
    const storage = memory()
    storeNotes(false, storage)
    expect(readStoredNotes(storage)).toBe(false)
    storeNotes(true, storage)
    expect(readStoredNotes(storage)).toBe(true)
  })
  it('does not mind a browser that will not remember', () => {
    refuseEveryCall()
    expect(readStoredNotes()).toBe(true)
    expect(() => storeNotes(false)).not.toThrow()
  })
})
