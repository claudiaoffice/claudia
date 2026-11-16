import { describe, expect, it } from 'vitest'
import { describeAuthInput, ExtensionLink, parseAuth, socketUrl, type SocketLike } from '../src/extension.js'

const AUTH = { nlPort: 4711, nlToken: 'tok', nlConnectToken: 'con nect', nlExtensionId: 'de.claudiaoffice.core' }

class FakeSocket implements SocketLike {
  sent: string[] = []
  closedByUs = false
  private listeners: Record<string, Array<(event: { data: unknown }) => void>> = {}
  send(data: string): void {
    this.sent.push(data)
  }
  close(): void {
    this.closedByUs = true
  }
  addEventListener(type: 'open' | 'error' | 'close', listener: () => void): void
  addEventListener(type: 'message', listener: (event: { data: unknown }) => void): void
  addEventListener(type: string, listener: (event: { data: unknown }) => void): void {
    ;(this.listeners[type] ??= []).push(listener)
  }
  emit(type: string, event?: unknown): void {
    for (const listener of this.listeners[type] ?? []) listener(event as { data: unknown })
  }
}

function link(handlers: Partial<ConstructorParameters<typeof ExtensionLink>[1]> = {}) {
  const socket = new FakeSocket()
  const urls: string[] = []
  const events: Array<[string, unknown]> = []
  let closed = 0
  const made = new ExtensionLink(
    AUTH,
    { onEvent: (event, data) => events.push([event, data]), onClosed: () => closed++, ...handlers },
    (url) => (urls.push(url), socket),
  )
  return { made, socket, urls, events, closed: () => closed }
}

describe('parseAuth', () => {
  it('reads what Neutralino sends on stdin', () => {
    expect(parseAuth(JSON.stringify(AUTH))).toEqual(AUTH)
  })

  it('is null until the JSON has arrived completely, and for anything else', () => {
    const text = JSON.stringify(AUTH)
    expect(parseAuth(text.slice(0, 10))).toBeNull()
    expect(parseAuth('')).toBeNull()
    expect(parseAuth('null')).toBeNull()
    expect(parseAuth('[]')).toBeNull()
    expect(parseAuth(JSON.stringify({ nlPort: 1 }))).toBeNull()
    expect(parseAuth(JSON.stringify({ ...AUTH, nlToken: 5 }))).toBeNull()
  })

  it('takes the port as a string of digits too: refusing what Neutralino may send would wait for ever', () => {
    expect(parseAuth(JSON.stringify({ ...AUTH, nlPort: '4711' }))).toEqual(AUTH)
    expect(parseAuth(JSON.stringify({ ...AUTH, nlPort: '47x1' }))).toBeNull()
    expect(parseAuth(JSON.stringify({ ...AUTH, nlPort: 0 }))).toBeNull()
    expect(parseAuth(JSON.stringify({ ...AUTH, nlPort: 70000 }))).toBeNull()
    expect(parseAuth(JSON.stringify({ ...AUTH, nlPort: 47.5 }))).toBeNull()
  })

  it('ignores other fields Neutralino may add, and does not pass them on', () => {
    expect(parseAuth(JSON.stringify({ ...AUTH, nlVersion: '6.8.0' }))).toEqual(AUTH)
  })
})

describe('describeAuthInput', () => {
  it('names the keys and their types and never a value (the values are tokens)', () => {
    const text = describeAuthInput(JSON.stringify({ nlPort: '4711', nlToken: 'SECRET', nlOther: null }))
    expect(text).toContain('nlPort: string')
    expect(text).toContain('nlToken: string')
    expect(text).not.toContain('SECRET')
    expect(text).not.toContain('4711')
  })

  it('says when it is not JSON (yet), or not an object', () => {
    expect(describeAuthInput('{"nlPo')).toContain('not (yet) complete JSON')
    expect(describeAuthInput('[1]')).toContain('object')
    expect(describeAuthInput('')).toContain('0 characters')
  })
})

describe('socketUrl', () => {
  it('connects to Neutralino on this computer with the extension id and the connect token (encoded)', () => {
    expect(socketUrl(AUTH)).toBe('ws://localhost:4711?extensionId=de.claudiaoffice.core&connectToken=con%20nect')
  })
})

describe('ExtensionLink', () => {
  it('connects to the address of Neutralino', () => {
    expect(link().urls).toEqual([socketUrl(AUTH)])
  })

  it('hands an event of the page on, with its data', () => {
    const { socket, events } = link()
    socket.emit('message', { data: JSON.stringify({ event: 'claudia.core', data: { kind: 'start' } }) })
    expect(events).toEqual([['claudia.core', { kind: 'start' }]])
  })

  it('ignores messages that are not events', () => {
    const { socket, events } = link()
    for (const data of ['not json', 'null', '"x"', JSON.stringify({ data: 1 }), JSON.stringify({ event: 5 })]) socket.emit('message', { data })
    expect(events).toEqual([])
  })

  it('broadcasts as Neutralino expects: app.broadcast, with the extension token', () => {
    const { made, socket } = link()
    made.broadcast('claudiaCore', { kind: 'show', origin: 'https://a.example' })
    const sent = JSON.parse(socket.sent[0]!)
    expect(sent).toMatchObject({ method: 'app.broadcast', accessToken: 'tok', data: { event: 'claudiaCore', data: { kind: 'show', origin: 'https://a.example' } } })
    expect(typeof sent.id).toBe('string')
  })

  it('ends when Neutralino closes the connection, once', () => {
    const { socket, closed } = link()
    socket.emit('close')
    socket.emit('close')
    expect(closed()).toBe(1)
  })

  it('ends when the connection cannot be made at all (Node reports an error and no close)', () => {
    const logged: string[] = []
    const { socket, closed } = link({ log: (m) => logged.push(m) })
    socket.emit('error')
    expect(closed()).toBe(1)
    expect(logged).toHaveLength(1)
  })

  it('does not send after it ended, and close() does not report an end it asked for itself', () => {
    const { made, socket, closed } = link()
    made.close()
    expect(socket.closedByUs).toBe(true)
    made.broadcast('x', 1)
    expect(socket.sent).toEqual([])
    socket.emit('close')
    expect(closed()).toBe(0)
  })

  it('tells when the connection is open', () => {
    let opened = 0
    const { socket } = link({ onOpen: () => opened++ })
    socket.emit('open')
    expect(opened).toBe(1)
  })
})
