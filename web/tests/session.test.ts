import { describe, expect, it } from 'vitest'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { Session } from '~/lib/session'

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'plan',
  app: 'computes',
  line: 'main',
  revision: 'main:3',
  id: 1,
  color: '#e6194b',
  people: [{ id: 9, user: 'ai', color: '#5b4bc4' }],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
}

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  handlers: Record<string, (params: any) => any> = {}
  events: EventHandler[] = []
  closers: CloseHandler[] = []
  welcome = WELCOME
  failConnect: ProtocolError | null = null
  async connect() {
    if (this.failConnect) throw this.failConnect
    return this.welcome
  }
  async request(method: string, params: any = {}) {
    this.calls.push({ method, params })
    const handler = this.handlers[method]
    if (!handler) throw new ProtocolError('unknown_method', method)
    return handler(params)
  }
  onEvent(h: EventHandler) {
    this.events.push(h)
  }
  onClose(h: CloseHandler) {
    this.closers.push(h)
  }
  close() {}
  push(name: string, data: any) {
    for (const h of this.events) h(name, data)
  }
  drop(code = 1006) {
    for (const h of this.closers) h(code, false)
  }
  count(method: string) {
    return this.calls.filter((c) => c.method === method).length
  }
}

function server(link: FakeLink) {
  const cells: Record<string, any> = { '0,0': { t: 'text', v: 'Item' }, '1,1': { t: 'int', v: 40 } }
  link.handlers = {
    sheets: () => [{ id: 's1', name: 'Budget', rows: 2, cols: 2 }],
    log: () => [{ revision: 'main:3', author: 'ben', origin: 'do', time: 't', label: 'Edit cell', summary: 'B2 = 40', of: null }],
    chat_log: () => [{ number: 1, author: 'ben', to: '', text: 'hi', time: 't', at: null }],
    checkpoints: () => [],
    history: () => ({ can_undo: true, can_redo: false, undo_label: 'Edit cell', redo_label: '' }),
    cells: (p: any) => ({
      revision: 'main:3',
      cells: Object.entries(cells)
        .map(([k, v]) => [...k.split(',').map(Number), v] as [number, number, any])
        .filter(([r, c]) => r >= p.row0 && r <= p.row1 && c >= p.col0 && c <= p.col1),
    }),
    set_cells: () => ({ revision: 'main:4' }),
    undo: () => ({ applied: true, revision: 'main:5' }),
    presence: () => ({}),
    lock: () => ({}),
    unlock: () => ({}),
    chat: () => ({}),
  }
}

async function opened() {
  const link = new FakeLink()
  server(link)
  const links = [link]
  const session = new Session(() => links.shift() ?? link, { retryDelays: [0] })
  await session.open()
  return { link, session }
}

describe('opening', () => {
  it('connects and loads what the screen needs', async () => {
    const { session, link } = await opened()
    const s = session.state
    expect(s.status).toBe('open')
    expect(s.me).toMatchObject({ user: 'ann', role: 'owner', color: '#e6194b' })
    expect(s.people.map((p) => p.user)).toEqual(['ai'])
    expect(s.sheets.map((x) => x.name)).toEqual(['Budget'])
    expect(s.activeSheet).toBe('s1')
    expect(s.entries[0]).toMatchObject({ author: 'ben', summary: 'B2 = 40' })
    expect(s.chat.map((m) => m.text)).toEqual(['hi'])
    expect(s.canUndo).toBe(true)
    expect(s.revision).toBe('main:3')
    expect(link.count('sheets')).toBe(1)
  })

  it('reports a refused handshake and stays closed', async () => {
    const link = new FakeLink()
    link.failConnect = new ProtocolError('unauthorized', 'missing or wrong credentials')
    const session = new Session(() => link)
    await expect(session.open()).rejects.toMatchObject({ code: 'unauthorized' })
    expect(session.state.status).toBe('closed')
  })
})

describe('cells', () => {
  it('loads a window once and serves it from memory', async () => {
    const { session, link } = await opened()
    await session.ensure('s1', 0, 10, 0, 5)
    await session.ensure('s1', 0, 10, 0, 5)
    expect(link.count('cells')).toBe(1)
    expect(session.cell('s1', 0, 0)).toEqual({ t: 'text', v: 'Item' })
    expect(session.cell('s1', 1, 1)).toEqual({ t: 'int', v: 40 })
    expect(session.cell('s1', 5, 5)).toBeNull()
  })

  it('follows cell events, also for empty cells', async () => {
    const { session, link } = await opened()
    await session.ensure('s1', 0, 10, 0, 5)
    link.push('cells', { sheet: 's1', positions: [[0, 0]], cells: [[0, 0, { t: 'text', v: 'Thing' }], [1, 1, null]] })
    expect(session.cell('s1', 0, 0)).toEqual({ t: 'text', v: 'Thing' })
    expect(session.cell('s1', 1, 1)).toBeNull()
  })

  it('reloads the window when rows or columns moved', async () => {
    const { session, link } = await opened()
    await session.ensure('s1', 0, 10, 0, 5)
    const before = session.state.generation
    link.push('structure', { sheet: 's1', axis: 'row', insert: true, at: 0, count: 1 })
    expect(session.state.generation).toBe(before + 1)
    await session.ensure('s1', 0, 10, 0, 5)
    expect(link.count('cells')).toBe(2)
  })
})

describe('events', () => {
  it('keeps the history, the revision and the undo state', async () => {
    const { session, link } = await opened()
    link.push('command', { revision: 'main:4', author: 'ai', origin: 'do', time: 't2', label: 'Edit cells', summary: '3 cells in A1:A3' })
    expect(session.state.entries.at(-1)).toMatchObject({ author: 'ai', summary: '3 cells in A1:A3' })
    expect(session.state.revision).toBe('main:4')
    link.push('command', { revision: 'main:4', author: 'ai', origin: 'do', time: 't2', label: 'x', summary: 'again' })
    expect(session.state.entries.filter((e) => e.revision === 'main:4')).toHaveLength(1)
    link.push('history', { author: 'ann', can_undo: false, can_redo: true, undo_label: '', redo_label: 'Edit cell' })
    expect(session.state.canUndo).toBe(false)
    expect(session.state.canRedo).toBe(true)
  })

  it('collects chat and checkpoints', async () => {
    const { session, link } = await opened()
    link.push('chat', { number: 2, author: 'ai', to: 'ann', text: 'done', time: 't', at: null })
    link.push('checkpoint', { number: 1, label: 'first', author: 'ann', marks: 'main:3' })
    expect(session.state.chat.map((m) => m.text)).toEqual(['hi', 'done'])
    expect(session.state.checkpoints.map((c) => c.label)).toEqual(['first'])
  })

  it('knows who is here, where they are, and who is typing', async () => {
    const { session, link } = await opened()
    link.push('joined', { id: 2, user: 'ben', color: '#3cb44b' })
    expect(session.state.people.map((p) => p.user)).toEqual(['ai', 'ben'])
    const region = { kind: 'cells', range: { first: { row: 2, col: 1, sheet: 's1' }, last: { row: 2, col: 1, sheet: 's1' } } }
    link.push('ephemeral', { kind: 'presence', sender: 'ben', data: { regions: [region], locked: true } })
    expect(session.state.presence.ben).toMatchObject({ locked: true })
    expect(session.state.presence.ben!.regions).toEqual([region])
    link.push('ephemeral', { kind: 'typing', sender: 'ai', data: { on: true } })
    expect(session.state.typing).toEqual(['ai'])
    link.push('ephemeral', { kind: 'typing', sender: 'ai', data: { on: false } })
    expect(session.state.typing).toEqual([])
    link.push('left', { id: 2, user: 'ben' })
    link.push('ephemeral', { kind: 'presence', sender: 'ben', data: { regions: [], gone: true } })
    expect(session.state.people.map((p) => p.user)).toEqual(['ai'])
    expect(session.state.presence.ben).toBeUndefined()
  })

  it('reloads everything when the document changed line or was rebuilt', async () => {
    for (const name of ['branch', 'rebuilt', 'redacted']) {
      const { session, link } = await opened()
      await session.ensure('s1', 0, 10, 0, 5)
      link.push(name, {})
      await session.settled()
      expect(link.count('sheets')).toBe(2)
      expect(link.count('log')).toBe(2)
      expect(session.state.notice?.text).toMatch(/changed/i)
    }
  })

  it('reloads the sheets when they changed', async () => {
    const { session, link } = await opened()
    link.push('sheets', {})
    await session.settled()
    expect(link.count('sheets')).toBe(2)
  })
})

describe('doing things', () => {
  it('types into cells against the revision it is looking at', async () => {
    const { session, link } = await opened()
    await session.setCells('s1', [{ row: 0, col: 0, input: 'x' }])
    const call = link.calls.find((c) => c.method === 'set_cells')!
    expect(call.params).toEqual({ sheet: 's1', cells: [{ row: 0, col: 0, input: 'x' }], base: 'main:3' })
  })

  it('tells the person when a colleague holds the cell, and does not throw', async () => {
    const { session, link } = await opened()
    link.handlers.set_cells = () => {
      throw new ProtocolError('locked', 'ben is working on B2 right now')
    }
    expect(await session.setCells('s1', [{ row: 1, col: 1, input: '1' }])).toBe(false)
    expect(session.state.notice).toMatchObject({ kind: 'warning', text: 'ben is working on B2 right now' })
  })

  it('reloads when an edit was made against a view that is gone', async () => {
    const { session, link } = await opened()
    link.handlers.set_cells = () => {
      throw new ProtocolError('stale', 'the document went back')
    }
    expect(await session.setCells('s1', [{ row: 0, col: 0, input: '1' }])).toBe(false)
    await session.settled()
    expect(link.count('sheets')).toBe(2)
    expect(session.state.notice?.text).toMatch(/not applied|changed/i)
  })

  it('explains a viewer’s refusal', async () => {
    const { session, link } = await opened()
    link.handlers.set_cells = () => {
      throw new ProtocolError('forbidden', 'set_cells needs the editor role')
    }
    await session.setCells('s1', [{ row: 0, col: 0, input: '1' }])
    expect(session.state.notice?.text).toMatch(/only look/i)
  })

  it('undoes, and says when there was nothing to undo because of a colleague', async () => {
    const { session, link } = await opened()
    expect(await session.undo()).toBe(true)
    link.handlers.undo = () => {
      throw new ProtocolError('conflict', 'ben changed B2 after you')
    }
    expect(await session.undo()).toBe(false)
    expect(session.state.notice?.text).toBe('ben changed B2 after you')
  })

  it('locks a cell while it is edited and lets go afterwards', async () => {
    const { session, link } = await opened()
    expect(await session.beginEdit('s1', 2, 1)).toBe(true)
    expect(link.calls.find((c) => c.method === 'lock')!.params.regions[0].range.first).toMatchObject({ row: 2, col: 1, sheet: 's1' })
    await session.endEdit()
    expect(link.count('unlock')).toBe(1)
    link.handlers.lock = () => {
      throw new ProtocolError('locked', 'ben is working on C3 right now')
    }
    expect(await session.beginEdit('s1', 2, 2)).toBe(false)
    expect(session.state.notice?.text).toMatch(/ben/)
  })

  it('sends chat as it is typed', async () => {
    const { session, link } = await opened()
    await session.say('@ai hello')
    expect(link.calls.find((c) => c.method === 'chat')!.params).toEqual({ text: '@ai hello' })
  })
})

describe('losing the connection', () => {
  it('opens a new one and reloads', async () => {
    const first = new FakeLink()
    const second = new FakeLink()
    server(first)
    server(second)
    const links = [first, second]
    const session = new Session(() => links.shift()!, { retryDelays: [0] })
    await session.open()
    first.drop(1006)
    expect(session.state.status).toBe('reconnecting')
    await session.settled()
    expect(session.state.status).toBe('open')
    expect(second.count('sheets')).toBe(1)
  })

  it('loads the cells again on the new connection, even if a request was left hanging on the old one', async () => {
    const first = new FakeLink()
    const second = new FakeLink()
    server(first)
    server(second)
    first.handlers.cells = () => new Promise(() => undefined) // never answered
    const links = [first, second]
    const session = new Session(() => links.shift()!, { retryDelays: [0] })
    await session.open()
    void session.ensure('s1', 0, 10, 0, 5)
    first.drop(1006)
    await session.settled()
    await session.ensure('s1', 0, 10, 0, 5)
    expect(second.count('cells')).toBe(1)
    expect(session.cell('s1', 1, 1)).toEqual({ t: 'int', v: 40 })
  })

  it('does not retry when the server refused us', async () => {
    const { session, link } = await opened()
    link.drop(4401)
    expect(session.state.status).toBe('closed')
    expect(session.state.error).toMatch(/password/)
  })

  it('stays closed when we closed it ourselves', async () => {
    const { session, link } = await opened()
    session.close()
    for (const h of link.closers) h(1000, true)
    expect(session.state.status).toBe('closed')
  })
})

describe('reading what is loaded', () => {
  it('lists the filled cells of a rectangle', async () => {
    const { session } = await opened()
    await session.ensure('s1', 0, 10, 0, 5)
    expect(session.filledIn('s1', 0, 0, 5, 5).sort()).toEqual([[0, 0], [1, 1]])
    expect(session.filledIn('s1', 1, 0, 5, 0)).toEqual([])
  })
})
