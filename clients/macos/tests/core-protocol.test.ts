import { describe, expect, it } from 'vitest'
import { isCoreMessage, isRequest } from '../src/core-protocol.js'

describe('isRequest', () => {
  it('accepts the four requests', () => {
    expect(isRequest({ kind: 'start' })).toBe(true)
    expect(isRequest({ kind: 'want_servers' })).toBe(true)
    expect(isRequest({ kind: 'connect', address: 'a.example' })).toBe(true)
    expect(isRequest({ kind: 'servers', servers: [] })).toBe(true)
  })

  it('refuses everything else', () => {
    for (const value of [null, undefined, 'start', [], {}, { kind: 'dance' }, { kind: 'connect' }, { kind: 'connect', address: 5 }, { kind: 'connect', address: 'x'.repeat(256) }, { kind: 'servers', servers: 'x' }]) {
      expect(isRequest(value)).toBe(false)
    }
  })
})

describe('isCoreMessage', () => {
  it('accepts the four messages', () => {
    expect(isCoreMessage({ kind: 'show', origin: 'https://a.example' })).toBe(true)
    expect(isCoreMessage({ kind: 'status', title: 'x', error: false })).toBe(true)
    expect(isCoreMessage({ kind: 'status', title: 'x', details: 'y', error: true })).toBe(true)
    expect(isCoreMessage({ kind: 'servers', servers: [] })).toBe(true)
    expect(isCoreMessage({ kind: 'connect_failed', code: 'unreachable', message: 'x' })).toBe(true)
  })

  it('refuses everything else', () => {
    for (const value of [null, 5, [], {}, { kind: 'show' }, { kind: 'show', origin: '' }, { kind: 'status', title: 'x' }, { kind: 'status', title: 'x', details: 5, error: false }, { kind: 'servers' }, { kind: 'connect_failed', code: 5, message: 'x' }, { kind: 'other' }]) {
      expect(isCoreMessage(value)).toBe(false)
    }
  })
})
