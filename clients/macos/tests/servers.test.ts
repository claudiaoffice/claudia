// The address and list rules (E5.8), the same cases clients/linux/tests/test_servers.py holds the Linux client to.
import { describe, expect, it } from 'vitest'
import { AddressRefused, MAX_SERVERS, defaultLabel, forPage, isLoopbackHost, parseAddress, remember, sanitize } from '../src/servers.js'

const refusedWith = (raw: string, code?: string) => {
  try {
    parseAddress(raw)
  } catch (problem) {
    expect(problem).toBeInstanceOf(AddressRefused)
    if (code) expect((problem as AddressRefused).code).toBe(code)
    return
  }
  throw new Error(`'${raw}' was accepted`)
}

describe('parseAddress', () => {
  it('takes a bare host as https, with or without a port', () => {
    expect(parseAddress('demo.claudia-office.de').origin).toBe('https://demo.claudia-office.de')
    expect(parseAddress('demo.example.org:8420').origin).toBe('https://demo.example.org:8420')
  })

  it('makes the spelling canonical: lower case, no default port, no trailing slash', () => {
    expect(parseAddress('HTTPS://Demo.Example.ORG:443/').origin).toBe('https://demo.example.org')
    expect(parseAddress('http://127.0.0.1:80').origin).toBe('http://127.0.0.1')
  })

  it('accepts plain http for this computer only', () => {
    expect(parseAddress('http://127.0.0.1:8123').isLoopback).toBe(true)
    expect(parseAddress('http://localhost:8123').origin).toBe('http://localhost:8123')
    expect(parseAddress('http://[::1]:8123').origin).toBe('http://[::1]:8123')
    refusedWith('http://example.com', 'insecure')
    refusedWith('http://192.168.1.10:8000', 'insecure')
  })

  it('an https address to this computer is fine too', () => {
    expect(parseAddress('https://localhost:8443').isLoopback).toBe(true)
  })

  it('refuses everything that is more than an origin', () => {
    for (const raw of [
      '',
      '   ',
      'ftp://example.org',
      'javascript:alert(1)',
      'file:///etc/passwd',
      'https://user:secret@example.org',
      'https://example.org/path',
      'https://example.org/?q=1',
      'https://example.org/#frag',
      'https://example.org:0',
      'https://example.org:99999',
      'https://exa mple.org',
      'https://münchen.example',
      'https://',
      'x'.repeat(300),
    ]) {
      refusedWith(raw, 'bad_address')
    }
  })

  it('refuses a host that only starts like this computer', () => {
    refusedWith('http://127.0.0.1.evil.example', 'insecure')
    expect(isLoopbackHost('localhost.evil.example')).toBe(false)
    expect(isLoopbackHost('127.0.0.2')).toBe(true)
    expect(isLoopbackHost('::1')).toBe(true)
    expect(isLoopbackHost('10.0.0.1')).toBe(false)
  })

  it('has a message for the person in every refusal', () => {
    try {
      parseAddress('ftp://x')
    } catch (problem) {
      expect((problem as Error).message).toMatch(/address of a server/)
    }
  })
})

describe('sanitize', () => {
  it('keeps valid entries, makes origins canonical, names an unnamed server by its host', () => {
    expect(sanitize([{ origin: 'HTTPS://Demo.Example.org:443', label: '  ', custom: false }])).toEqual([
      { origin: 'https://demo.example.org', label: 'demo.example.org', custom: false },
    ])
  })

  it('drops what is not a valid stored origin, this computer\'s own entry, and duplicates (the first wins)', () => {
    const kept = sanitize([
      { origin: 'https://a.example', label: 'A', custom: true },
      { origin: 'https://a.example/', label: 'again', custom: false },
      { origin: 'a.example', label: 'bare', custom: false },
      { origin: 'http://evil.example', label: 'plain', custom: false },
      { origin: 'http://127.0.0.1:5000', label: 'me', custom: true, local: true },
      { origin: 42 },
      'rubbish',
      null,
    ])
    expect(kept).toEqual([{ origin: 'https://a.example', label: 'A', custom: true }])
  })

  it('cuts a long label and the list at the maximum', () => {
    const many = Array.from({ length: MAX_SERVERS + 10 }, (_, i) => ({ origin: `https://h${i}.example`, label: 'x'.repeat(500), custom: false }))
    const kept = sanitize(many)
    expect(kept).toHaveLength(MAX_SERVERS)
    expect(kept[0]!.label).toHaveLength(128)
  })

  it('something that is not a list is no list', () => {
    expect(sanitize({})).toEqual([])
    expect(sanitize('x')).toEqual([])
    expect(sanitize(undefined)).toEqual([])
  })
})

describe('forPage and remember', () => {
  const saved = [{ origin: 'https://a.example', label: 'A', custom: true }]

  it("puts this computer's server first and never twice", () => {
    const shown = forPage(saved, { localOrigin: 'http://127.0.0.1:5000', localLabel: 'This computer' })
    expect(shown[0]).toEqual({ origin: 'http://127.0.0.1:5000', label: 'This computer', custom: true, local: true })
    expect(shown).toHaveLength(2)
    const same = forPage([{ origin: 'http://127.0.0.1:5000', label: 'old', custom: false }, ...saved], {
      localOrigin: 'http://127.0.0.1:5000',
      localLabel: 'This computer',
    })
    expect(same.filter((e) => e.origin === 'http://127.0.0.1:5000')).toHaveLength(1)
  })

  it('shows only the remembered ones when no server of this computer runs', () => {
    expect(forPage(saved, { localOrigin: null, localLabel: 'This computer' })).toEqual(saved)
  })

  it('remembers a new server and keeps the name a person gave an old one', () => {
    expect(remember(saved, 'b.example:8420').map((e) => e.origin)).toEqual(['https://a.example', 'https://b.example:8420'])
    expect(remember(saved, 'https://A.example')).toEqual(saved)
  })

  it('names a server by host and port', () => {
    expect(defaultLabel('https://demo.example.org:8420')).toBe('demo.example.org:8420')
  })
})
