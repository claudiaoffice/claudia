import { describe, expect, it } from 'vitest'
import { DEFAULT_AI_MODE, aiModeKey, readAiMode, storeAiMode } from '~/lib/ai-mode'

function memoryStorage() {
  const map = new Map<string, string>()
  return { getItem: (k: string) => map.get(k) ?? null, setItem: (k: string, v: string) => void map.set(k, v), map }
}

describe('the AI mode (D262)', () => {
  it('is suggest for somebody who never chose', () => {
    expect(DEFAULT_AI_MODE).toBe('suggest')
    expect(readAiMode('127.0.0.1:8420', 'plan', memoryStorage())).toBe('suggest')
  })

  it('remembers what a person chose, for this document only', () => {
    const storage = memoryStorage()
    storeAiMode('127.0.0.1:8420', 'plan', 'act', storage)
    expect(readAiMode('127.0.0.1:8420', 'plan', storage)).toBe('act')
    expect(readAiMode('127.0.0.1:8420', 'budget', storage)).toBe('suggest')
    expect(readAiMode('other.example:8420', 'plan', storage)).toBe('suggest')
  })

  it('takes a choice back', () => {
    const storage = memoryStorage()
    storeAiMode('h', 'plan', 'act', storage)
    storeAiMode('h', 'plan', 'suggest', storage)
    expect(readAiMode('h', 'plan', storage)).toBe('suggest')
  })

  it('does not trust what is in the storage: anything but act is suggest', () => {
    const storage = memoryStorage()
    storage.setItem(aiModeKey('h', 'plan'), 'yolo')
    expect(readAiMode('h', 'plan', storage)).toBe('suggest')
  })

  it('keeps a document name that looks like another one apart', () => {
    expect(aiModeKey('a:1', 'b')).not.toBe(aiModeKey('a', '1:b'))
  })

  it('still works when the browser will not store anything', () => {
    const refusing = {
      getItem: () => {
        throw new Error('denied')
      },
      setItem: () => {
        throw new Error('denied')
      },
    }
    expect(readAiMode('h', 'plan', refusing)).toBe('suggest')
    expect(() => storeAiMode('h', 'plan', 'act', refusing)).not.toThrow()
  })
})
