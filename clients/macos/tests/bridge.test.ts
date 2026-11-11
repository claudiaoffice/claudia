// The shell's side of the contract, TypeScript twin of clients/linux/tests/test_bridge.py.
import { describe, expect, it } from 'vitest'
import { Bridge, type BridgeOptions } from '../src/bridge.js'
import type { KnownAction } from '../src/menu-actions.js'

const KNOWN: KnownAction[] = [
  { id: 'file.new', checkable: false },
  { id: 'view.panel', checkable: true },
  { id: 'help.about', checkable: false },
]

function make(overrides: Partial<BridgeOptions> = {}) {
  const sent: Array<Record<string, unknown>> = []
  const calls = { states: [] as unknown[], ready: 0, connect: [] as string[], servers: [] as unknown[] }
  const bridge = new Bridge({
    app: 'creates',
    known: KNOWN,
    shell: { name: 'neutralino', platform: 'macos', version: '0.1.0' },
    send: (raw) => sent.push(JSON.parse(raw)),
    onStates: (s) => calls.states.push(s),
    onReady: () => calls.ready++,
    onConnect: (a) => calls.connect.push(a),
    onServers: (s) => calls.servers.push(s),
    ...overrides,
  })
  const say = (message: unknown) => bridge.receive(JSON.stringify(message))
  const hello = () => say({ type: 'hello', contract: 1, app: 'creates' })
  return { bridge, sent, calls, say, hello }
}

describe('hello', () => {
  it('is answered with a welcome that says who the shell is and what it offers', () => {
    const { sent, hello, calls, bridge } = make()
    hello()
    expect(sent).toEqual([
      { type: 'welcome', contract: 1, shell: { name: 'neutralino', platform: 'macos', version: '0.1.0' }, capabilities: ['native-menu', 'actions', 'connect', 'servers'] },
    ])
    expect(bridge.ready).toBe(true)
    expect(calls.ready).toBe(1)
  })

  it('offers connect and servers only when the shell can do them', () => {
    const { sent, hello } = make({ onConnect: undefined, onServers: undefined })
    hello()
    expect(sent[0]!.capabilities).toEqual(['native-menu', 'actions'])
  })

  it('passes the locale on', () => {
    const { sent, hello } = make({ locale: 'de-DE' })
    hello()
    expect(sent[0]!.locale).toBe('de-DE')
  })

  it('takes a page that does not say its app (it asks for a secret first) to be the shell\'s app', () => {
    const { sent, say } = make()
    say({ type: 'hello', contract: 1 })
    expect(sent[0]!.type).toBe('welcome')
  })

  it('refuses a page of another app', () => {
    const { sent, say, bridge } = make()
    say({ type: 'hello', contract: 1, app: 'composes' })
    expect(sent).toMatchObject([{ type: 'error', code: 'bad_message' }])
    expect(bridge.ready).toBe(false)
  })

  it('refuses a contract version it does not speak, naming the ones it does', () => {
    const { sent, say } = make()
    say({ type: 'hello', contract: 9, app: 'creates' })
    expect(sent).toMatchObject([{ type: 'error', code: 'unsupported_contract', supported: [1] }])
  })
})

describe('messages that need a hello first', () => {
  it('are refused before it', () => {
    const { sent, say, calls } = make()
    say({ type: 'connect', address: 'a.example' })
    say({ type: 'servers', servers: [] })
    say({ type: 'action_state', states: { 'file.new': { enabled: false } } })
    expect(sent.map((m) => m.code)).toEqual(['bad_message', 'bad_message', 'bad_message'])
    expect(calls.connect).toEqual([])
    expect(calls.servers).toEqual([])
    expect(calls.states).toEqual([])
  })
})

describe('after hello', () => {
  it('passes a connect request on', () => {
    const { say, hello, calls } = make()
    hello()
    say({ type: 'connect', address: 'demo.example.org' })
    expect(calls.connect).toEqual(['demo.example.org'])
  })

  it('refuses a connect request when the shell cannot connect', () => {
    const { say, hello, sent } = make({ onConnect: undefined })
    hello()
    say({ type: 'connect', address: 'a.example' })
    expect(sent.at(-1)).toMatchObject({ type: 'error', code: 'bad_message' })
  })

  it('passes the server list on', () => {
    const { say, hello, calls } = make()
    hello()
    say({ type: 'servers', servers: [{ origin: 'https://a.example', label: 'A', custom: false }] })
    expect(calls.servers).toHaveLength(1)
  })

  it('applies the states of known actions and says which it does not know', () => {
    const { say, hello, calls, sent } = make()
    hello()
    say({ type: 'action_state', states: { 'file.new': { enabled: false }, 'file.nope': { enabled: true } } })
    expect(calls.states).toEqual([{ 'file.new': { enabled: false } }])
    expect(sent.at(-1)).toMatchObject({ type: 'error', code: 'unknown_action', message: 'no such action: file.nope' })
  })

  it('does not call back for a report of unknown actions only', () => {
    const { say, hello, calls } = make()
    hello()
    say({ type: 'action_state', states: { 'file.nope': { enabled: true } } })
    expect(calls.states).toEqual([])
  })

  it('keeps what the page reports as wrong', () => {
    const { say, hello, bridge, sent } = make()
    hello()
    say({ type: 'error', code: 'bad_message', message: 'your action was odd' })
    expect(bridge.pageErrors).toEqual(['bad_message: your action was odd'])
    expect(sent).toHaveLength(1) // only the welcome: an error is not answered
  })

  it('refuses the shell-to-page message types from the page', () => {
    const { say, hello, sent } = make()
    hello()
    say({ type: 'action', action: 'file.new' })
    say({ type: 'welcome', contract: 1, shell: { name: 'x', platform: 'macos', version: '1' }, capabilities: [] })
    expect(sent.slice(1).map((m) => m.code)).toEqual(['bad_message', 'bad_message'])
  })
})

describe('what the page sends wrongly', () => {
  it('is answered with an error for bad JSON and for a message that breaks the contract', () => {
    const { bridge, sent } = make()
    bridge.receive('{nope')
    bridge.receive(JSON.stringify({ type: 'hello' }))
    expect(sent.map((m) => m.code)).toEqual(['bad_json', 'bad_message'])
  })

  it('is ignored for a type it does not know (a newer page may say more)', () => {
    const { bridge, sent } = make()
    bridge.receive(JSON.stringify({ type: 'dance' }))
    expect(sent).toEqual([])
  })
})

describe('to the page', () => {
  it('sends an action only to a page that has said hello, and only a known one', () => {
    const { bridge, sent, hello } = make()
    expect(bridge.sendAction('file.new')).toBe(false)
    hello()
    expect(bridge.sendAction('view.panel', 'on')).toBe(true)
    expect(sent.at(-1)).toEqual({ type: 'action', action: 'view.panel', target: 'on' })
    expect(() => bridge.sendAction('file.nope')).toThrow(/no such action/)
  })

  it('sends servers and a connect failure only to a page that is there', () => {
    const { bridge, sent, hello } = make()
    expect(bridge.sendServers([])).toBe(false)
    expect(bridge.sendConnectFailed('unreachable', 'x')).toBe(false)
    hello()
    expect(bridge.sendServers([{ origin: 'https://a.example', label: 'A', custom: false }])).toBe(true)
    expect(bridge.sendConnectFailed('wrong_app', 'That server runs another app.')).toBe(true)
    expect(sent.slice(1)).toEqual([
      { type: 'servers', servers: [{ origin: 'https://a.example', label: 'A', custom: false }] },
      { type: 'connect_failed', code: 'wrong_app', message: 'That server runs another app.' },
    ])
  })

  it('forgets the page on reset', () => {
    const { bridge, hello } = make()
    hello()
    bridge.reset()
    expect(bridge.ready).toBe(false)
    expect(bridge.sendAction('file.new')).toBe(false)
  })
})
