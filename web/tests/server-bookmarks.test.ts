import { describe, expect, it } from 'vitest'
import { adminUrl, defaultLabel, isBookmark, list, normalizeServerInput, rename, upsert, withBookmark, withRenamed } from '~/lib/server-bookmarks'

function memoryStorage() {
  const map = new Map<string, string>()
  return { getItem: (k: string) => map.get(k) ?? null, setItem: (k: string, v: string) => void map.set(k, v) }
}

describe('defaultLabel', () => {
  it("is \"<administrator>'s server\" once the server has one", () => {
    expect(defaultLabel('https://demo.claudiaoffice.de', 'tobi')).toBe("tobi's server")
  })
  it('falls back to the host when there is no administrator yet', () => {
    expect(defaultLabel('http://127.0.0.1:8420', null)).toBe('127.0.0.1:8420')
  })
  it('falls back to the origin itself if it cannot be parsed as a URL', () => {
    expect(defaultLabel('not a url', null)).toBe('not a url')
  })
})

describe('list / upsert', () => {
  it('starts empty', () => {
    expect(list(memoryStorage())).toEqual([])
  })
  it('remembers a new server with its default label, not yet custom', () => {
    const storage = memoryStorage()
    upsert('https://demo.claudiaoffice.de', "tobi's server", storage)
    expect(list(storage)).toEqual([{ origin: 'https://demo.claudiaoffice.de', label: "tobi's server", custom: false }])
  })
  it('refreshes the label of an un-renamed bookmark on a later visit', () => {
    const storage = memoryStorage()
    upsert('http://127.0.0.1:8420', '127.0.0.1:8420', storage)
    upsert('http://127.0.0.1:8420', "tobi's server", storage) // the server got its first administrator since
    expect(list(storage)[0]?.label).toBe("tobi's server")
  })
  it('never overwrites a label the person chose themselves', () => {
    const storage = memoryStorage()
    upsert('https://demo.claudiaoffice.de', "tobi's server", storage)
    rename('https://demo.claudiaoffice.de', 'The demo box', storage)
    upsert('https://demo.claudiaoffice.de', "anna's server", storage) // the first administrator changed; irrelevant now
    expect(list(storage)[0]).toEqual({ origin: 'https://demo.claudiaoffice.de', label: 'The demo box', custom: true })
  })
  it('keeps several servers apart', () => {
    const storage = memoryStorage()
    upsert('https://demo.claudiaoffice.de', "tobi's server", storage)
    upsert('http://192.168.1.42:8420', "anna's server", storage)
    expect(list(storage).map((b) => b.origin)).toEqual(['https://demo.claudiaoffice.de', 'http://192.168.1.42:8420'])
  })
  it('ignores a damaged store rather than throwing', () => {
    const storage = { getItem: () => '{not json' }
    expect(list(storage)).toEqual([])
  })
})

describe('rename', () => {
  it('does nothing for a server that was never bookmarked', () => {
    const storage = memoryStorage()
    expect(rename('https://nowhere.example', 'x', storage)).toEqual([])
  })
  it('keeps the old label when renamed to blank', () => {
    const storage = memoryStorage()
    upsert('https://demo.claudiaoffice.de', "tobi's server", storage)
    rename('https://demo.claudiaoffice.de', '   ', storage)
    expect(list(storage)[0]?.label).toBe("tobi's server")
  })
})

describe('adminUrl', () => {
  it('is the settings pages, at that server\'s own origin', () => {
    expect(adminUrl('https://demo.claudiaoffice.de')).toBe('https://demo.claudiaoffice.de/admin/')
  })
})

describe('normalizeServerInput', () => {
  it('gives a bare host the page\'s own scheme', () => {
    expect(normalizeServerInput('demo.claudiaoffice.de', 'https:')).toBe('https://demo.claudiaoffice.de')
  })
  it('keeps a host:port the same way', () => {
    expect(normalizeServerInput('192.168.1.42:8420', 'https:')).toBe('https://192.168.1.42:8420')
  })
  it('keeps an explicit scheme as typed, even if it differs from the page\'s own', () => {
    expect(normalizeServerInput('http://127.0.0.1:8420', 'https:')).toBe('http://127.0.0.1:8420')
  })
  it('trims surrounding whitespace and a trailing slash', () => {
    expect(normalizeServerInput('  demo.claudiaoffice.de/  ', 'https:')).toBe('https://demo.claudiaoffice.de')
  })
  it('is null for blank input', () => {
    expect(normalizeServerInput('   ', 'https:')).toBeNull()
  })
})


describe('withBookmark / withRenamed (the same rules on a list that is not in this browser)', () => {
  const demo = { origin: 'https://demo.claudiaoffice.de', label: "tobi's server", custom: false }
  it('adds a server without changing the list it was given', () => {
    const before = [demo]
    const after = withBookmark(before, 'http://127.0.0.1:8420', '127.0.0.1:8420')
    expect(after).toHaveLength(2)
    expect(before).toHaveLength(1)
  })
  it('refreshes an un-renamed label and keeps a renamed one', () => {
    expect(withBookmark([demo], demo.origin, 'new')[0]?.label).toBe('new')
    expect(withBookmark([{ ...demo, custom: true }], demo.origin, 'new')[0]?.label).toBe("tobi's server")
  })
  it('renames, and never touches the server on this computer, which is the shell\'s', () => {
    const local = { origin: 'http://127.0.0.1:41233', label: 'This computer', custom: true, local: true }
    const after = withRenamed([demo, local], local.origin, 'mine')
    expect(after[1]).toEqual(local)
    expect(withRenamed([demo, local], demo.origin, ' Demo ')[0]).toEqual({ ...demo, label: 'Demo', custom: true })
  })
})

describe('isBookmark', () => {
  it('accepts the shell\'s entry for this computer and refuses a malformed flag', () => {
    expect(isBookmark({ origin: 'http://127.0.0.1:1', label: 'x', custom: true, local: true })).toBe(true)
    expect(isBookmark({ origin: 'http://127.0.0.1:1', label: 'x', custom: true, local: 'yes' })).toBe(false)
    expect(isBookmark({ origin: 'x', label: 'x' })).toBe(false)
  })
})
