import { describe, expect, it } from 'vitest'
import { isSlides, openSession } from '~/lib/open'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { Session } from '~/lib/session'
import { SlideSession } from '~/lib/slide-session'

const welcome = (app: string, role: Welcome['role'] = 'owner'): Welcome => ({
  user: 'ann',
  role,
  doc: 'd',
  app,
  line: 'main',
  revision: null,
  id: 1,
  color: '#e6194b',
  people: [],
  presence: [],
  checkpoints: [],
  limits: { max_text: 100 },
  lines: [{ name: 'main', head: null, active: true, forked_from: null }],
  proposal: null,
  returned: null,
})

class FakeLink implements LinkLike {
  calls: string[] = []
  connects = 0
  events: EventHandler[] = []
  closers: CloseHandler[] = []
  sheets: unknown[] = []
  constructor(
    private hello: Welcome,
    public create: boolean,
  ) {}
  async connect() {
    this.connects++
    return this.hello
  }
  async request(method: string, params: any = {}) {
    this.calls.push(method)
    switch (method) {
      case 'sheets':
        return this.sheets
      case 'slides':
        return [{ id: 's1', objects: 0 }]
      case 'slide':
        return { revision: null, slide: params.slide, objects: [] }
      case 'shapes':
        return { library: [], document: [] }
      case 'images':
        return []
      case 'palette':
        return { type: 'palette', roles: [], readings: [] }
      case 'styles':
      case 'log':
      case 'chat_log':
      case 'checkpoints':
      case 'lines':
        return []
      case 'history':
        return { can_undo: false, can_redo: false, undo_label: '', redo_label: '' }
      case 'restore_policy':
        return { policy: 'consensus' }
      case 'add_sheet':
        return { sheet: 's1', revision: 'main:1' }
    }
    throw new ProtocolError('unknown_method', method)
  }
  onEvent(h: EventHandler) {
    this.events.push(h)
  }
  onClose(h: CloseHandler) {
    this.closers.push(h)
  }
  close() {}
}

/** A factory like the open dialog's: only the first connection may create the document. */
function links(hello: Welcome, create: boolean) {
  const made: FakeLink[] = []
  return { made, factory: () => (made.push(new FakeLink(hello, create && made.length === 0)), made.at(-1)!) }
}

describe('openSession', () => {
  it('opens a presentation in a slide session', async () => {
    const { made, factory } = links(welcome('creates'), true)
    const session = await openSession(factory)
    expect(session).toBeInstanceOf(SlideSession)
    expect(isSlides(session)).toBe(true)
    expect(made[0]!.create).toBe(true) // the first connection only finds out what the document is, and creates it
    expect(made.at(-1)!.create).toBe(false)
    expect(made.at(-1)!.calls).toContain('slides')
    expect(session.state.status).toBe('open')
    expect(session.state.app).toBe('creates')
  })

  it('remembers that the document was made by this very opening, so that the person can be shown its recovery key', async () => {
    const { factory } = links({ ...welcome('creates'), created: true }, true)
    const session = await openSession(factory)
    expect(session.justCreated).toBe(true)
  })

  it('does not say so for a document that was there before', async () => {
    const { factory } = links(welcome('creates'), false)
    expect((await openSession(factory)).justCreated).toBe(false)
  })

  it('opens a table in a table session', async () => {
    const { made, factory } = links(welcome('computes'), false)
    const session = await openSession(factory)
    expect(session).toBeInstanceOf(Session)
    expect(isSlides(session)).toBe(false)
    expect(made.at(-1)!.calls).toContain('sheets')
  })

  it('reconnects with a new connection that does not try to create the document again', async () => {
    const { made, factory } = links(welcome('creates'), true)
    const session = (await openSession(factory, { retryDelays: [1] })) as SlideSession
    const before = made.length
    for (const closed of made.at(-1)!.closers) closed(1006, false)
    await session.settled()
    expect(made).toHaveLength(before + 1)
    expect(made.at(-1)!.create).toBe(false)
    expect(session.state.status).toBe('open')
  })

  it('passes on a refused connection as it is', async () => {
    const refused = new FakeLink(welcome('creates'), false)
    refused.connect = async () => {
      throw new ProtocolError('unauthorized', 'no')
    }
    await expect(openSession(() => refused)).rejects.toMatchObject({ code: 'unauthorized' })
  })

  it('carries the server address options were given through to the session (E3.11)', async () => {
    const { factory } = links(welcome('computes'), false)
    const session = await openSession(factory, { host: 'demo.claudiaoffice.de:8420' })
    expect(session.state.host).toBe('demo.claudiaoffice.de:8420')
  })
})
