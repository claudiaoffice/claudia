import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { Outcome } from '../src/connection.js'
import { Connector, ServerBook } from '../src/connector.js'
import { Settings } from '../src/settings.js'

describe('ServerBook', () => {
  let directory: string
  let settings: Settings
  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'claudia-book-'))
    settings = new Settings(join(directory, 'shell.json'))
  })
  afterEach(() => rmSync(directory, { recursive: true, force: true }))

  it("lists this computer's server first, named by the shell, then the remembered ones", () => {
    settings.saveServers('creates', [{ origin: 'https://a.example', label: 'A', custom: true }])
    const book = new ServerBook('creates', settings, { localOrigin: 'http://127.0.0.1:5000' })
    expect(book.entries().map((e) => [e.origin, e.label, e.local ?? false])).toEqual([
      ['http://127.0.0.1:5000', 'This computer', true],
      ['https://a.example', 'A', false],
    ])
  })

  it("follows the local server once it has started, and never writes it down", () => {
    const book = new ServerBook('creates', settings)
    expect(book.entries()).toEqual([])
    book.localOrigin = 'http://127.0.0.1:6000'
    book.remember('http://127.0.0.1:6000')
    expect(settings.loadServers('creates')).toEqual([])
    expect(book.entries()).toHaveLength(1)
  })

  it('remembers a server once, keeping the name a person gave it', () => {
    const book = new ServerBook('creates', settings)
    book.remember('https://a.example')
    book.replace([{ origin: 'https://a.example', label: 'Office', custom: true }])
    book.remember('https://a.example')
    expect(settings.loadServers('creates')).toEqual([{ origin: 'https://a.example', label: 'Office', custom: true }])
  })

  it('keeps the list of each app apart, and only what is valid of what the page sends', () => {
    const creates = new ServerBook('creates', settings)
    const computes = new ServerBook('computes', settings)
    creates.replace([{ origin: 'https://a.example', label: 'A', custom: false }, { origin: 'javascript:1', label: 'x', custom: false }])
    expect(creates.entries().map((e) => e.origin)).toEqual(['https://a.example'])
    expect(computes.entries()).toEqual([])
  })
})

describe('Connector', () => {
  let directory: string
  let book: ServerBook
  let shown: string[]
  let failed: Array<[string, string]>
  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'claudia-connector-'))
    book = new ServerBook('creates', new Settings(join(directory, 'shell.json')))
    shown = []
    failed = []
  })
  afterEach(() => rmSync(directory, { recursive: true, force: true }))

  const make = (check: (origin: string, app: string) => Promise<Outcome>, log?: (m: string) => void) =>
    new Connector('creates', {
      book,
      switchTo: (origin) => shown.push(origin),
      fail: (code, message) => failed.push([code, message]),
      check: (address, app) => check(address.origin, app),
      log,
    })

  it('shows a server that was reached, and remembers it', async () => {
    const connector = make(async (origin) => ({ kind: 'reached', origin, app: 'creates' }))
    await connector.connect('demo.example.org')
    expect(shown).toEqual(['https://demo.example.org'])
    expect(book.entries().map((e) => e.origin)).toEqual(['https://demo.example.org'])
    expect(failed).toEqual([])
  })

  it('checks the address of the window\'s own app', async () => {
    const asked: string[] = []
    const connector = make(async (origin, app) => (asked.push(app), { kind: 'reached', origin, app }))
    await connector.connect('a.example')
    expect(asked).toEqual(['creates'])
  })

  it('reports a refusal with its code and message, and remembers nothing', async () => {
    const connector = make(async () => ({ kind: 'refused', code: 'wrong_app', message: 'That server runs Claudia Composes.' }))
    await connector.connect('a.example')
    expect(failed).toEqual([['wrong_app', 'That server runs Claudia Composes.']])
    expect(shown).toEqual([])
    expect(book.entries()).toEqual([])
  })

  it('refuses a bad address and plain http to another computer without asking the network', async () => {
    let asked = 0
    const connector = make(async (origin) => (asked++, { kind: 'reached', origin, app: null }))
    await connector.connect('https://a.example/path')
    await connector.connect('http://a.example')
    expect(failed.map(([code]) => code)).toEqual(['bad_address', 'insecure'])
    expect(asked).toBe(0)
  })

  it('says unreachable (and logs the bug) when the check itself fails', async () => {
    const logged: string[] = []
    const connector = make(async () => {
      throw new Error('boom')
    }, (m) => logged.push(m))
    await connector.connect('a.example')
    expect(failed[0]![0]).toBe('unreachable')
    expect(logged.join('')).toContain('boom')
  })

  it('lets the newest request win: an older one that finishes later is dropped', async () => {
    const release: Array<() => void> = []
    const connector = make(
      (origin) =>
        new Promise((resolve) => {
          release.push(() => resolve({ kind: 'reached', origin, app: 'creates' }))
        }),
    )
    const first = connector.connect('first.example')
    const second = connector.connect('second.example')
    release[1]!()
    await second
    release[0]!()
    await first
    expect(shown).toEqual(['https://second.example'])
  })
})
