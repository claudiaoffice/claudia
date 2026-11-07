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
  lines: [{ name: 'main', head: 'main:3', active: true, forked_from: null }],
  proposal: null,
  returned: null,
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
    lines: () => [{ name: 'main', head: 'main:3', active: true, forked_from: null }],
    restore_policy: () => ({ policy: 'consensus' }),
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
    peek_line: ({ line }: any) => ({ line, revision: 'main:3', app: 'computes', state_schema: 1, state: {} }),
    propose_restore: () => ({ applied: true, proposal: null }),
    propose_switch: () => ({ applied: true, proposal: null }),
    answer_restore: () => ({ resolved: 'agreed' }),
    withdraw_restore: () => ({}),
    discard_side_history: () => ({ discarded: [] }),
    set_restore_policy: ({ policy }: any) => ({ policy }),
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

  it('keeps trying while the document is sealed (an editor has not opened it since the server started)', async () => {
    const first = new FakeLink()
    const sealed = new FakeLink()
    const second = new FakeLink()
    server(first)
    server(second)
    sealed.failConnect = new ProtocolError('sealed', 'this document is sealed: an owner or editor has to open it first')
    const links = [first, sealed, second]
    const session = new Session(() => links.shift()!, { retryDelays: [0] })
    await session.open()
    first.drop(1006)
    await session.settled()
    expect(session.state.status).toBe('open')
    expect(second.count('sheets')).toBe(1)
  })

  it('gives up for good on a refusal that will not change', async () => {
    const first = new FakeLink()
    const refused = new FakeLink()
    server(first)
    refused.failConnect = new ProtocolError('unauthorized', 'missing or wrong credentials')
    const links = [first, refused]
    const session = new Session(() => links.shift()!, { retryDelays: [0] })
    await session.open()
    first.drop(1006)
    await session.settled()
    expect(session.state.status).toBe('closed')
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

describe('the recovery key', () => {
  it('asks the server for a new one and hands it over', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.new_recovery_key = () => ({ recovery_key: 'ABCD-EFGH' })
    const session = new Session(() => link)
    await session.open()
    expect(await session.newRecoveryKey()).toBe('ABCD-EFGH')
    expect(session.state.notice).toBeNull()
  })

  it('gives nothing back, and says why, if the server will not make one', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.new_recovery_key = () => {
      throw new ProtocolError('forbidden', 'only the owner of a document makes a recovery key')
    }
    const session = new Session(() => link)
    await session.open()
    expect(await session.newRecoveryKey()).toBeNull()
    expect(session.state.notice?.text).toBe('You can only look at this document.')
  })

  it('stays quiet when the server simply keeps no recovery keys (that is not the person’s doing)', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.new_recovery_key = () => {
      throw new ProtocolError('unavailable', 'this server does not keep recovery keys')
    }
    const session = new Session(() => link)
    await session.open()
    expect(await session.newRecoveryKey({ quiet: true })).toBeNull()
    expect(session.state.notice).toBeNull()
  })
})

describe('the Manage menu (leaving, handing over ownership, deleting, exporting)', () => {
  it('lists everybody, not just who is connected', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.roster = () => [
      { user: 'ann', role: 'owner' },
      { user: 'ben', role: 'editor' },
    ]
    const session = new Session(() => link)
    await session.open()
    expect(await session.roster()).toEqual([
      { user: 'ann', role: 'owner' },
      { user: 'ben', role: 'editor' },
    ])
  })

  it('leaves with a password, and closes for nobody but us', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.leave = () => ({ left: true })
    const session = new Session(() => link)
    await session.open()
    expect(await session.leave('Correct-Horse-9')).toBe(true)
    expect(session.state.status).toBe('open')
  })

  it('reports why leaving did not work', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.leave = () => {
      throw new ProtocolError('unauthorized', 'that is not your current password')
    }
    const session = new Session(() => link)
    await session.open()
    expect(await session.leave('wrong')).toBe(false)
    expect(session.state.notice?.text).toBe('that is not your current password')
  })

  it('proposes a new owner with our own password', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.propose_owner = (p) => ({ proposed: p.name })
    const session = new Session(() => link)
    await session.open()
    expect(await session.proposeOwner('ben', 'Correct-Horse-9')).toBe(true)
    expect(link.calls.at(-1)).toMatchObject({ method: 'propose_owner', params: { name: 'ben', password: 'Correct-Horse-9' } })
  })

  it('accepting ownership reconnects so the new role is recognised', async () => {
    const first = new FakeLink()
    const second = new FakeLink()
    server(first)
    server(second)
    first.handlers.accept_owner = () => ({ accepted: true })
    const links = [first, second]
    const session = new Session(() => links.shift()!)
    await session.open()
    expect(await session.acceptOwner('Battery-Staple-7')).toBe(true)
    expect(session.state.status).toBe('open')
    expect(second.count('sheets')).toBe(1)
  })

  it('deletes the document with a password, and closes the session', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.delete_document = () => ({ deleted: true })
    const session = new Session(() => link)
    await session.open()
    expect(await session.deleteDocument('Correct-Horse-9')).toBe(true)
    expect(session.state.status).toBe('closed')
  })

  it('does not close the session when deleting is refused', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.delete_document = () => {
      throw new ProtocolError('forbidden', 'only an owner of a document may delete it')
    }
    const session = new Session(() => link)
    await session.open()
    expect(await session.deleteDocument('Correct-Horse-9')).toBe(false)
    expect(session.state.status).toBe('open')
  })

  it('exports the current content as plain data', async () => {
    const link = new FakeLink()
    server(link)
    const exported = { format: 'claudia-export 1', app: 'computes', exported_at: 't', state_schema: 1, state: {} }
    link.handlers.export_content = () => exported
    const session = new Session(() => link)
    await session.open()
    expect(await session.exportContent()).toEqual(exported)
  })

  it('tells us when somebody else leaves', async () => {
    const { session, link } = await opened()
    link.push('ephemeral', { kind: 'person_left', sender: 'ben', data: { user: 'ben' } })
    expect(session.state.notice?.text).toMatch(/ben left/)
  })

  it('reconnects when the ownership of the document changed under us', async () => {
    const first = new FakeLink()
    const second = new FakeLink()
    server(first)
    server(second)
    const links = [first, second]
    const session = new Session(() => links.shift()!)
    await session.open()
    first.push('ephemeral', { kind: 'owner_changed', sender: 'ben', data: { owner: 'ben' } })
    await session.settled()
    expect(session.state.notice?.text).toMatch(/ben is now the owner/)
    expect(session.state.status).toBe('open')
    expect(second.count('sheets')).toBe(1)
  })

  it('closes the session when the document was deleted out from under us', async () => {
    const { session, link } = await opened()
    link.push('ephemeral', { kind: 'document_deleted', sender: 'ann', data: {} })
    expect(session.state.status).toBe('closed')
    expect(session.state.notice?.text).toMatch(/deleted/)
  })
})

const PROPOSAL = {
  id: 1,
  kind: 'restore' as const,
  by: 'ben',
  checkpoint: 1,
  line: null,
  label: 'checkpoint “good”',
  opened_at: 0,
  expires_at: 900,
  policy: 'consensus' as const,
  group: ['ann', 'ben'],
  agreed: ['ben'],
}

describe('lines, and restoring with consent', () => {
  it('loads the lines and the restore policy, and lets you peek at one', async () => {
    const { session, link } = await opened()
    expect(session.state.lines).toEqual([{ name: 'main', head: 'main:3', active: true, forked_from: null }])
    expect(session.state.restorePolicy).toBe('consensus')
    expect(await session.peekLine('main')).toMatchObject({ line: 'main', revision: 'main:3' })
    expect(link.calls.find((c) => c.method === 'peek_line')!.params).toEqual({ line: 'main' })
  })

  it('suggests a restore; the server may carry it out at once', async () => {
    const { session, link } = await opened()
    expect(await session.proposeRestore(1)).toBe(true)
    expect(link.calls.find((c) => c.method === 'propose_restore')!.params).toEqual({ checkpoint: 1 })
    expect(session.state.proposal).toBeNull()
  })

  it('suggests switching to another line', async () => {
    const { session, link } = await opened()
    expect(await session.proposeSwitch('restore-1')).toBe(true)
    expect(link.calls.find((c) => c.method === 'propose_switch')!.params).toEqual({ line: 'restore-1' })
  })

  it('tracks an open suggestion from the restore_proposed event', async () => {
    const { session, link } = await opened()
    link.push('restore_proposed', PROPOSAL)
    expect(session.state.proposal).toEqual(PROPOSAL)
  })

  it('answers the open suggestion', async () => {
    const { session, link } = await opened()
    link.push('restore_proposed', PROPOSAL)
    expect(await session.answerRestore(true)).toBe(true)
    expect(link.calls.find((c) => c.method === 'answer_restore')!.params).toEqual({ agree: true })
  })

  it('clears the proposal and tells everybody once it is agreed', async () => {
    const { session, link } = await opened()
    link.push('restore_proposed', PROPOSAL)
    link.push('restore_resolved', { outcome: 'agreed' })
    expect(session.state.proposal).toBeNull()
    expect(session.state.notice).toMatchObject({ kind: 'info', text: expect.stringContaining('checkpoint “good”') })
  })

  it('warns when the suggestion was declined', async () => {
    const { session, link } = await opened()
    link.push('restore_proposed', PROPOSAL)
    link.push('restore_resolved', { outcome: 'declined' })
    expect(session.state.proposal).toBeNull()
    expect(session.state.notice).toMatchObject({ kind: 'warning', text: expect.stringMatching(/declined/i) })
  })

  it('says when the suggestion was withdrawn', async () => {
    const { session, link } = await opened()
    link.push('restore_proposed', PROPOSAL)
    link.push('restore_resolved', { outcome: 'withdrawn' })
    expect(session.state.notice?.text).toMatch(/withdrawn/i)
  })

  it('takes back the open suggestion', async () => {
    const { session, link } = await opened()
    expect(await session.withdrawRestore()).toBe(true)
    expect(link.count('withdraw_restore')).toBe(1)
  })

  it('discards the hidden lines and reloads what the screen shows', async () => {
    const { session, link } = await opened()
    expect(await session.discardSideHistory()).toBe(true)
    await session.settled()
    expect(link.count('discard_side_history')).toBe(1)
    expect(link.count('sheets')).toBe(2)
  })

  it('sets the restore policy', async () => {
    const { session, link } = await opened()
    expect(await session.setRestorePolicy('veto')).toBe(true)
    expect(session.state.restorePolicy).toBe('veto')
    expect(link.calls.find((c) => c.method === 'set_restore_policy')!.params).toEqual({ policy: 'veto' })
  })

  it('tells a returning person what happened to the line they were on', async () => {
    const link = new FakeLink()
    server(link)
    link.welcome = { ...link.welcome, returned: { by: 'ben', kind: 'restore', label: 'checkpoint “good”', agreed: ['ann', 'ben'] } }
    const session = new Session(() => link)
    await session.open()
    expect(session.state.notice?.text).toMatch(/ben restored to checkpoint “good”/i)
  })
})
