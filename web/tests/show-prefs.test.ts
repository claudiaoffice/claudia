import { describe, expect, it } from 'vitest'
import { readStoredNotes, storeNotes } from '~/lib/show-prefs'

const memory = () => {
  const map = new Map<string, string>()
  return { getItem: (k: string) => map.get(k) ?? null, setItem: (k: string, v: string) => void map.set(k, v) }
}

describe('whether the speaker notes are shown', () => {
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
    const refusing = { getItem: () => { throw new Error('denied') }, setItem: () => { throw new Error('denied') } }
    expect(readStoredNotes(refusing)).toBe(true)
    expect(() => storeNotes(false, refusing)).not.toThrow()
  })
})
