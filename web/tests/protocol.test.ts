import { describe, expect, it } from 'vitest'
import { Link, ProtocolError, closeMessage, socketUrl, type SocketLike } from '~/lib/protocol'

class FakeSocket implements SocketLike {
  sent: any[] = []
  onopen: (() => void) | null = null
  onmessage: ((event: { data: unknown }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  closedWith: number | undefined
  send(data: string) {
    this.sent.push(JSON.parse(data))
  }
  close(code?: number) {
    this.closedWith = code
    this.onclose?.({ code: code ?? 1000 })
  }
  open() {
    this.onopen?.()
  }
  push(frame: unknown) {
    this.onmessage?.({ data: JSON.stringify(frame) })
  }
}

function link(create = false) {
  const socket = new FakeSocket()
  const l = new Link({ url: 'ws://x/api/docs/plan/ws', user: 'ann', password: 'pw', create, socket: () => socket })
  return { l, socket }
}

const WELCOME = { user: 'ann', role: 'owner', doc: 'plan', people: [] }

describe('Link', () => {
  it('says hello first and resolves with the welcome data', async () => {
    const { l, socket } = link(true)
    const welcome = l.connect()
    socket.open()
    expect(socket.sent[0]).toEqual({ id: 1, method: 'hello', params: { user: 'ann', password: 'pw', create: true } })
    socket.push({ id: 1, ok: true, result: WELCOME })
    expect(await welcome).toEqual(WELCOME)
  })

  it('comes in with a recovery key and a new password instead of creating or logging in', async () => {
    const socket = new FakeSocket()
    const l = new Link({
      url: 'ws://x/api/docs/plan/ws',
      user: 'ben',
      password: 'Fresh-Start-42',
      recoveryKey: 'ABCD-EFGH',
      create: true, // never both: a recovery is not a creation
      socket: () => socket,
    })
    const welcome = l.connect()
    socket.open()
    expect(socket.sent[0]).toEqual({
      id: 1,
      method: 'hello',
      params: { user: 'ben', password: 'Fresh-Start-42', recovery_key: 'ABCD-EFGH' },
    })
    socket.push({ id: 1, ok: true, result: WELCOME })
    await welcome
  })

  it('rejects the handshake with the server’s error', async () => {
    const { l, socket } = link()
    const welcome = l.connect()
    socket.open()
    socket.push({ id: 1, ok: false, error: { code: 'unauthorized', message: 'missing or wrong credentials' } })
    await expect(welcome).rejects.toMatchObject({ code: 'unauthorized' })
  })

  it('refuses requests once the connection is gone instead of waiting for ever', async () => {
    const { l, socket } = link()
    const welcome = l.connect()
    socket.open()
    socket.push({ id: 1, ok: true, result: WELCOME })
    await welcome
    socket.onclose?.({ code: 1006 })
    await expect(l.request('sheets')).rejects.toMatchObject({ code: 'closed' })
    expect(socket.sent).toHaveLength(1) // only the hello went out
  })

  it('gives up when the connection closes before the handshake is answered', async () => {
    const { l, socket } = link()
    const welcome = l.connect()
    socket.onclose?.({ code: 1006 }) // the server was not there at all
    await expect(welcome).rejects.toMatchObject({ code: 'closed' })
  })

  it('matches answers to requests by id, in any order', async () => {
    const { l, socket } = link()
    const welcome = l.connect()
    socket.open()
    socket.push({ id: 1, ok: true, result: WELCOME })
    await welcome
    const a = l.request('sheets')
    const b = l.request('users', { x: 1 })
    expect(socket.sent.slice(1)).toEqual([
      { id: 2, method: 'sheets', params: {} },
      { id: 3, method: 'users', params: { x: 1 } },
    ])
    socket.push({ id: 3, ok: true, result: ['ann'] })
    socket.push({ id: 2, ok: false, error: { code: 'locked', message: 'ben holds it' } })
    expect(await b).toEqual(['ann'])
    await expect(a).rejects.toBeInstanceOf(ProtocolError)
    await expect(a).rejects.toMatchObject({ code: 'locked', message: 'ben holds it' })
  })

  it('passes pushed events on, in order', async () => {
    const { l, socket } = link()
    const seen: string[] = []
    l.onEvent((name, data) => seen.push(`${name}:${data.n}`))
    const welcome = l.connect()
    socket.open()
    socket.push({ id: 1, ok: true, result: WELCOME })
    await welcome
    socket.push({ event: 'cells', data: { n: 1 } })
    socket.push({ event: 'command', data: { n: 2 } })
    expect(seen).toEqual(['cells:1', 'command:2'])
  })

  it('fails what is waiting when the connection goes, and says whether we closed it', async () => {
    const { l, socket } = link()
    const closes: [number, boolean][] = []
    l.onClose((code, requested) => closes.push([code, requested]))
    const welcome = l.connect()
    socket.open()
    socket.push({ id: 1, ok: true, result: WELCOME })
    await welcome
    const waiting = l.request('snapshot')
    socket.onclose?.({ code: 1006 })
    await expect(waiting).rejects.toMatchObject({ code: 'closed' })
    expect(closes).toEqual([[1006, false]])
    l.close()
    expect(closes.at(-1)).toEqual([1000, true])
  })

  it('ignores frames that are not JSON or that nobody waits for', async () => {
    const { l, socket } = link()
    const welcome = l.connect()
    socket.open()
    socket.onmessage?.({ data: 'not json' })
    socket.push({ id: 99, ok: true, result: 1 })
    socket.push({ id: 1, ok: true, result: WELCOME })
    expect(await welcome).toEqual(WELCOME)
  })
})

describe('addresses and messages', () => {
  it('builds the socket address from the page', () => {
    expect(socketUrl('my plan', { protocol: 'https:', host: 'h:8443' })).toBe('wss://h:8443/api/docs/my%20plan/ws')
    expect(socketUrl('p', { protocol: 'http:', host: 'localhost:8000' })).toBe('ws://localhost:8000/api/docs/p/ws')
  })
  it('explains close codes', () => {
    expect(closeMessage(4401)).toMatch(/password/)
    expect(closeMessage(4404)).toMatch(/no such document/)
    expect(closeMessage(1006)).toMatch(/lost/)
  })
})
