// A person's private server: its port and its proof (E8.5, D1620, D1621). The expected values are those of
// clients/contract/private-port.vectors.json, which the server's and the Linux client's tests read too.
import { randomBytes } from 'node:crypto'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { OWNER_KEY_FILE, ownerAnswer, ownerKey, proves } from '../src/owner-key.js'
import { PRIVATE_PORTS, privatePort, walkFrom } from '../src/private-port.js'

interface Vectors {
  ports: { byUid: Array<{ uid: number; port: number }>; byProfileFolder: Array<{ profileFolder: string; port: number }> }
  proofs: { cases: Array<{ key: string; port: number; challenge: string; answer: string }> }
}
const VECTORS = JSON.parse(
  readFileSync(join(import.meta.dirname, '..', '..', 'contract', 'private-port.vectors.json'), 'utf8'),
) as Vectors

describe('the port of a private server', () => {
  it.each(VECTORS.ports.byUid)('on macOS and Linux it follows the account number: uid $uid → $port', ({ uid, port }) => {
    expect(privatePort({ uid })).toBe(port)
  })

  it.each(VECTORS.ports.byProfileFolder)('on Windows it follows the profile folder: $profileFolder → $port', ({ profileFolder, port }) => {
    expect(privatePort({ profileFolder })).toBe(port)
  })

  it('stays in her range whatever number it is given (Windows says -1 for an account number)', () => {
    expect(privatePort({ uid: -1 })).toBe(29999)
    expect(privatePort({ uid: -10001 })).toBe(29999)
  })

  it('is never 8765, the port of every shared server, and stays below the ports the systems hand out', () => {
    expect(PRIVATE_PORTS).toEqual({ first: 20000, last: 29999 })
  })

  it('while her port is held, the others of her range are tried in one order: after her port, then from the first', () => {
    const order = [...walkFrom(29998)]
    expect(order.slice(0, 3)).toEqual([29999, 20000, 20001])
    expect(order).toHaveLength(9999)
    expect(order).not.toContain(29998)
  })
})

describe('her key', () => {
  it('is the one another of her windows wrote first, when it did so while this one was making its own', () => {
    const state = mkdtempSync(join(tmpdir(), 'claudia-key-'))
    try {
      const theirs = 'ab'.repeat(32)
      const key = ownerKey(state, () => {
        writeFileSync(join(state, OWNER_KEY_FILE), theirs + '\n') // the other window, a moment earlier
        return randomBytes(32)
      })
      expect(key.key.toString('hex')).toBe(theirs)
      expect(readFileSync(join(state, OWNER_KEY_FILE), 'utf8').trim()).toBe(theirs)
    } finally {
      rmSync(state, { recursive: true, force: true })
    }
  })
})

describe('the proof of a private server', () => {
  it.each(VECTORS.proofs.cases)('answers the challenge with its key and the port it listens on ($port)', (c) => {
    expect(ownerAnswer(Buffer.from(c.key, 'hex'), c.port, c.challenge)).toBe(c.answer)
  })

  it('takes an answer only when it is the right one', () => {
    const c = VECTORS.proofs.cases[0]!
    const key = Buffer.from(c.key, 'hex')
    expect(proves(key, c.port, c.challenge, c.answer)).toBe(true)
    expect(proves(key, c.port + 1, c.challenge, c.answer)).toBe(false)
    expect(proves(key, c.port, c.challenge, c.answer.toUpperCase())).toBe(false)
    expect(proves(key, c.port, c.challenge, c.answer.slice(0, -2))).toBe(false)
    expect(proves(key, c.port, c.challenge, 42)).toBe(false)
    expect(proves(key, c.port, c.challenge, 'ü'.repeat(64))).toBe(false) // whatever answers on the port
  })
})
