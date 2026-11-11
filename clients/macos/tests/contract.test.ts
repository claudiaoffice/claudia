// The TypeScript port of the shell contract (E5.12) against the contract itself: every message below is judged by
// the JSON schema in clients/contract/ *and* by `parse`, and the two must agree. Whatever the shell builds must pass
// the schema too.
import Ajv2020 from 'ajv/dist/2020.js'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import * as contract from '../src/contract.js'

const schema = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'contract', 'shell-contract.v1.schema.json'), 'utf8'))
// ajv is CommonJS: under NodeNext its default export arrives wrapped in `{ default }`
type AjvConstructor = new (options: { strict: boolean }) => { compile: (schema: unknown) => ((data: unknown) => boolean) }
const AjvClass = ((Ajv2020 as unknown as { default?: AjvConstructor }).default ?? Ajv2020) as unknown as AjvConstructor
const validate = new AjvClass({ strict: false }).compile(schema)
const SHELL = { name: 'neutralino', platform: 'macos', version: '0.1.0' } as const
const SERVER = { origin: 'https://a.example', label: 'A', custom: false }

const VALID: Array<[string, unknown]> = [
  ['hello', { type: 'hello', contract: 1, app: 'creates', frontend: '0.1.0' }],
  ['hello without an app', { type: 'hello', contract: 1 }],
  ['hello with an extra field', { type: 'hello', contract: 1, app: 'creates', future: true }],
  ['welcome', { type: 'welcome', contract: 1, shell: SHELL, capabilities: ['native-menu', 'actions', 'connect', 'servers'] }],
  ['welcome with a locale', { type: 'welcome', contract: 1, shell: SHELL, capabilities: [], locale: 'de-DE' }],
  ['action', { type: 'action', action: 'file.save' }],
  ['action with a target', { type: 'action', action: 'view.panel', target: 'on' }],
  ['action_state', { type: 'action_state', states: { 'file.save': { enabled: false }, 'view.panel': { checked: true, label: 'Panel' } } }],
  ['error', { type: 'error', code: 'bad_message', message: 'no' }],
  ['error with the versions', { type: 'error', code: 'unsupported_contract', message: 'no', supported: [1] }],
  ['connect', { type: 'connect', address: 'demo.example.org:8420' }],
  ['connect_failed', { type: 'connect_failed', code: 'wrong_app', message: 'That server runs another app.' }],
  ['servers', { type: 'servers', servers: [SERVER, { ...SERVER, origin: 'http://127.0.0.1:5000', local: true, custom: true }] }],
  ['no servers', { type: 'servers', servers: [] }],
]

const INVALID: Array<[string, unknown]> = [
  ['hello without a version', { type: 'hello' }],
  ['hello with version 0', { type: 'hello', contract: 0 }],
  ['hello with a version that is text', { type: 'hello', contract: '1' }],
  ['hello with an app that is not a word', { type: 'hello', contract: 1, app: 'Creates!' }],
  ['hello with a long frontend', { type: 'hello', contract: 1, frontend: 'x'.repeat(65) }],
  ['welcome without a shell', { type: 'welcome', contract: 1, capabilities: [] }],
  ['welcome with another platform', { type: 'welcome', contract: 1, shell: { ...SHELL, platform: 'beos' }, capabilities: [] }],
  ['welcome with a doubled capability', { type: 'welcome', contract: 1, shell: SHELL, capabilities: ['connect', 'connect'] }],
  ['welcome with a capability that is not a word', { type: 'welcome', contract: 1, shell: SHELL, capabilities: ['Native Menu'] }],
  ['welcome with a bad locale', { type: 'welcome', contract: 1, shell: SHELL, capabilities: [], locale: 'de_DE' }],
  ['action without a name', { type: 'action' }],
  ['action that is not namespaced', { type: 'action', action: 'save' }],
  ['action in capitals', { type: 'action', action: 'File.Save' }],
  ['action with a long target', { type: 'action', action: 'view.panel', target: 'x'.repeat(257) }],
  ['action_state without states', { type: 'action_state' }],
  ['action_state with no action', { type: 'action_state', states: {} }],
  ['action_state with a bad name', { type: 'action_state', states: { save: { enabled: true } } }],
  ['action_state with a flag that is text', { type: 'action_state', states: { 'file.save': { enabled: 'yes' } } }],
  ['error with an unknown code', { type: 'error', code: 'oops', message: 'x' }],
  ['error without a message', { type: 'error', code: 'bad_message' }],
  ['connect without an address', { type: 'connect' }],
  ['connect with an empty address', { type: 'connect', address: '' }],
  ['connect with a long address', { type: 'connect', address: 'a'.repeat(256) }],
  ['connect_failed with an unknown code', { type: 'connect_failed', code: 'nope', message: 'x' }],
  ['servers that is not a list', { type: 'servers', servers: 'x' }],
  ['a server without an origin', { type: 'servers', servers: [{ label: 'A', custom: false }] }],
  ['a server whose custom is text', { type: 'servers', servers: [{ ...SERVER, custom: 'yes' }] }],
  ['too many servers', { type: 'servers', servers: Array.from({ length: 65 }, () => SERVER) }],
  ['a type nobody knows', { type: 'dance' }],
  ['no type', { contract: 1 }],
]

describe('parse agrees with the contract schema', () => {
  it.each(VALID)('accepts %s', (_name, message) => {
    expect(validate(message)).toBe(true)
    expect(contract.parse(JSON.stringify(message))).toMatchObject(message as object)
  })

  it.each(INVALID)('refuses %s', (_name, message) => {
    expect(validate(message)).toBe(false)
    expect(() => contract.parse(JSON.stringify(message))).toThrow()
  })
})

describe('parse', () => {
  it('refuses what is not JSON, and what is JSON but not an object', () => {
    expect(() => contract.parse('{nope')).toThrow(contract.ContractError)
    try {
      contract.parse('{nope')
    } catch (problem) {
      expect((problem as contract.ContractError).code).toBe('bad_json')
    }
    for (const raw of ['[]', '"x"', 'null', '1']) {
      expect(() => contract.parse(raw)).toThrow(/object/)
    }
  })

  it('refuses a message that is too large', () => {
    expect(() => contract.parse(JSON.stringify({ type: 'servers', servers: [], pad: 'x'.repeat(contract.MAX_MESSAGE_BYTES) }))).toThrow(/too large/)
  })

  it('says a type it does not know apart from a message that is wrong (a newer page may say more)', () => {
    expect(() => contract.parse('{"type":"dance"}')).toThrow(contract.UnknownMessageType)
    expect(() => contract.parse('{"type":"hello"}')).toThrow(contract.ContractError)
    expect(() => contract.parse('{"type":"constructor"}')).toThrow(contract.UnknownMessageType)
    expect(() => contract.parse('{"type":"__proto__"}')).toThrow(contract.UnknownMessageType)
  })
})

describe('negotiate', () => {
  it('speaks the version the page asked for when it knows it', () => {
    expect(contract.negotiate({ type: 'hello', contract: 1 })).toBe(1)
  })

  it('refuses another version, saying which ones it speaks', () => {
    try {
      contract.negotiate({ type: 'hello', contract: 2 })
      throw new Error('accepted')
    } catch (problem) {
      expect((problem as contract.ContractError).code).toBe('unsupported_contract')
      expect((problem as contract.ContractError).supported).toEqual([1])
    }
  })
})

describe('what the shell builds passes the schema', () => {
  it('welcome, action, error, connect_failed, servers', () => {
    const built = [
      contract.welcome({ shell: SHELL, capabilities: ['native-menu', 'actions'], locale: 'de' }),
      contract.welcome({ shell: SHELL, capabilities: [] }),
      contract.action('file.new'),
      contract.action('view.panel', 'on'),
      contract.error('bad_message', 'x'),
      contract.error('unsupported_contract', 'x', [1]),
      contract.errorFor(new contract.ContractError('bad_json', 'x')),
      contract.connectFailed('unreachable', 'Could not reach a.example.'),
      contract.servers([SERVER]),
    ]
    for (const message of built) expect(validate(message), JSON.stringify(message)).toBe(true)
  })

  it('cuts a message text that is too long instead of breaking the contract', () => {
    const message = contract.connectFailed('unreachable', 'x'.repeat(2000))
    expect(validate(message)).toBe(true)
  })

  it('refuses to build a message that breaks the contract', () => {
    expect(() => contract.action('Save')).toThrow()
    expect(() => contract.servers([{ origin: '', label: '', custom: false }])).toThrow()
  })
})
