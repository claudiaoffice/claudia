import { describe, expect, it } from 'vitest'
import { friendlyLabel, indicatorLabel, manageUrl, resolveOrigin, statusWord } from '~/lib/connection'
import type { Bookmark } from '~/lib/server-bookmarks'

describe('resolveOrigin', () => {
  it('builds the origin from the session\'s own host when it has one', () => {
    expect(resolveOrigin('demo.claudiaoffice.de:8420', 'https:', 'app.example.com')).toBe('https://demo.claudiaoffice.de:8420')
  })
  it('falls back to the page\'s own host before a session has one', () => {
    expect(resolveOrigin('', 'https:', 'app.example.com')).toBe('https://app.example.com')
  })
})

describe('friendlyLabel', () => {
  const bookmarks: Bookmark[] = [{ origin: 'https://demo.claudiaoffice.de', label: "tobi's server", custom: true }]

  it('uses a bookmark\'s own label when one exists for that origin', () => {
    expect(friendlyLabel('https://demo.claudiaoffice.de', 'demo.claudiaoffice.de', bookmarks)).toBe("tobi's server")
  })
  it('falls back to the bare host when the server was never bookmarked', () => {
    expect(friendlyLabel('http://127.0.0.1:8420', '127.0.0.1:8420', bookmarks)).toBe('127.0.0.1:8420')
  })
})

describe('statusWord', () => {
  it.each([
    ['open', 'Connected'],
    ['reconnecting', 'Reconnecting…'],
    ['connecting', 'Connecting…'],
    ['closed', 'Offline'],
    ['idle', 'Offline'],
  ] as const)('%s -> %s', (status, word) => {
    expect(statusWord(status)).toBe(word)
  })
})

describe('indicatorLabel', () => {
  it('says healthy when open', () => {
    expect(indicatorLabel("tobi's server", 'open')).toBe("Connection to tobi's server: healthy. Show details.")
  })
  it('says reconnecting while reconnecting or connecting', () => {
    expect(indicatorLabel("tobi's server", 'reconnecting')).toContain('reconnecting')
    expect(indicatorLabel("tobi's server", 'connecting')).toContain('reconnecting')
  })
  it('says offline once closed', () => {
    expect(indicatorLabel("tobi's server", 'closed')).toContain('offline')
  })
})

describe('manageUrl', () => {
  it('is that server\'s own settings pages', () => {
    expect(manageUrl('https://demo.claudiaoffice.de')).toBe('https://demo.claudiaoffice.de/admin/')
  })
})
