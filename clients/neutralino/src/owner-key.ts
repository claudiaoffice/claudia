// The key that makes a person's private server hers (E8.5, D1620; CODE-99). Her apps keep it in the server's state
// folder (hers alone), start the server with it (`--owner-key-file`), and use a server they find on her port only when
// it answers a fresh challenge with it (`GET /api/owner`, the server's owner_proof.py). The answer covers the port the
// server listens on, so a program on her usual address cannot pass the challenge on to her real server elsewhere. The
// twin of clients/linux/.../owner_key.py; both are held to clients/contract/private-port.vectors.json.

import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto'
import { linkSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

export const OWNER_KEY_FILE = 'owner.key'
const KEY_BYTES = 32
const HEX_KEY = /^[0-9a-fA-F]{64}$/

export interface OwnerKey {
  /** Where it is kept, for `--owner-key-file`. */
  readonly file: string
  readonly key: Buffer
}

/** The key in `state`, made the first time (readable by this person only). It is written whole under another name and
 * linked into place, so another of her windows never reads half of it; when another window was first, its key is the
 * one (§13). A file that holds no key is replaced: a server started with the old one then no longer proves to be hers,
 * and her apps start their own next to it. `make` is for the tests. */
export function ownerKey(state: string, make: () => Buffer = () => randomBytes(KEY_BYTES)): OwnerKey {
  const file = join(state, OWNER_KEY_FILE)
  const found = readKey(file)
  if (found !== null) return { file, key: found }
  mkdirSync(state, { recursive: true })
  const temporary = `${file}.${process.pid}`
  const made = make()
  writeFileSync(temporary, made.toString('hex') + '\n', { mode: 0o600 })
  try {
    linkSync(temporary, file) // only when there is no file yet
  } catch {
    if (readKey(file) === null) renameSync(temporary, file) // a file that holds no key: replaced
  } finally {
    rmSync(temporary, { force: true })
  }
  return { file, key: readKey(file) ?? made } // the key in the file, whoever wrote it
}

function readKey(file: string): Buffer | null {
  try {
    const text = readFileSync(file, 'utf8').trim()
    return HEX_KEY.test(text) ? Buffer.from(text, 'hex') : null
  } catch {
    return null
  }
}

/** What a server that listens on `port` with `key` answers to `challenge`. */
export function ownerAnswer(key: Buffer, port: number, challenge: string): string {
  return createHmac('sha256', key).update(`claudia owner proof\n${port}\n${challenge}`).digest('hex')
}

/** Is `answer` the one a server with `key` on `port` gives to `challenge`? Compared in constant time. */
export function proves(key: Buffer, port: number, challenge: string, answer: unknown): boolean {
  if (typeof answer !== 'string') return false
  const expected = Buffer.from(ownerAnswer(key, port, challenge))
  const given = Buffer.from(answer)
  return given.length === expected.length && timingSafeEqual(given, expected)
}

/** Does the server on `port` of this computer prove that it is the one with `key`? Any failure to ask is a no. */
export async function isOwnedBy(port: number, key: Buffer, timeoutMs = 1000): Promise<boolean> {
  const challenge = randomBytes(32).toString('hex') // fresh, 64 lower-case hex digits
  try {
    const response = await fetch(`http://127.0.0.1:${port}/api/owner?challenge=${challenge}`, { signal: AbortSignal.timeout(timeoutMs) })
    if (!response.ok) return false
    const body = (await response.json()) as { answer?: unknown }
    return proves(key, port, challenge, body.answer)
  } catch {
    return false
  }
}
