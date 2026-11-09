import { describe, expect, it } from 'vitest'
import { readStoredGrid, storeGrid } from '~/lib/grid'

function memoryStorage() {
  const map = new Map<string, string>()
  return { getItem: (k: string) => map.get(k) ?? null, setItem: (k: string, v: string) => void map.set(k, v) }
}

describe('readStoredGrid / storeGrid', () => {
  it('defaults to shown when nothing is stored', () => {
    expect(readStoredGrid(memoryStorage())).toBe(true)
  })
  it('round-trips a stored choice', () => {
    const storage = memoryStorage()
    storeGrid(false, storage)
    expect(readStoredGrid(storage)).toBe(false)
    storeGrid(true, storage)
    expect(readStoredGrid(storage)).toBe(true)
  })
})
