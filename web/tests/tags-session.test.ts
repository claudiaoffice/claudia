import { describe, expect, it } from 'vitest'
import { BaseSession, type BaseState, type Step } from '~/lib/base-session'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome, type WireData } from '~/lib/protocol'
import type { Thing } from '~/lib/tags'

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'talk',
  app: 'creates',
  branch: 'main',
  revision: 'main:3',
  id: 1,
  color: '#e6194b',
  people: [],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
  branches: [{ name: 'main', head: 'main:3', active: true, forked_from: null }],
  proposal: null,
  returned: null,
}
const entry = (n: number): Step => ({ revision: `main:${n}`, author: 'ann', origin: 'do', time: '', label: `step ${n}`, summary: '' })

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  events: EventHandler[] = []
  seen: any = { present: false, revision: 'main:2' }
  async connect() {
    return WELCOME
  }
  async request(method: string, params: any = {}): Promise<any> {
    this.calls.push({ method, params })
    switch (method) {
      case 'log':
        return [entry(1), entry(2), entry(3)]
      case 'chat_log':
      case 'checkpoints':
        return []
      case 'history':
        return { can_undo: false, can_redo: false, undo_label: '', redo_label: '' }
      case 'branches':
        return [{ name: 'main', head: 'main:3', active: true, forked_from: null }]
      case 'restore_policy':
        return { policy: 'consensus' }
      case 'peek_revision':
        return { revision: params.revision, entry: entry(1), focus: [], app: 'creates' }
      case 'as_of':
        return []
      case 'thing_last_seen':
        return this.seen
      case 'name_unnamed':
        return { named: 2, revision: 'main:4' }
      default:
        throw new ProtocolError('unknown_method', method)
    }
  }
  onEvent(h: EventHandler) {
    this.events.push(h)
  }
  onClose(_h: CloseHandler) {}
  close() {}
  push(name: string, data: WireData) {
    for (const h of this.events) h(name, data)
  }
}

/** A document of two slides, `s1` with a figure on it and `s2` with a table, in which the person is looking at `s1`. */
class TestSession extends BaseSession<BaseState & { here: string }> {
  deck: Thing[] = [
    { id: 's1', name: 'Intro', kind: 'slide' },
    { id: 's2', name: 'Results', kind: 'slide' },
    { id: 'o1', name: 'Figure 1', kind: 'image' },
    { id: 'o2', name: 'Table 1', kind: 'shape' },
  ]
  on: Record<string, string> = { s1: 's1', s2: 's2', o1: 's1', o2: 's2' }
  constructor(link: LinkLike) {
    super(() => link, { retryDelays: [1] }, { here: 's1' })
  }
  protected async loadApp() {}
  protected onAppEvent() {
    return false
  }
  protected override things(): Thing[] {
    return this.deck.map((t) => ({ ...t, name: this.state.renamed[t.id] ?? t.name }))
  }
  protected override async inView(): Promise<Thing[]> {
    return this.things().filter((t) => this.on[t.id] === this.state.here)
  }
  protected override containerOf(id: string): string | null {
    return this.on[id] ?? null
  }
  protected override currentContainer(): string | null {
    return this.state.here
  }
  protected override showContainer(id: string): void {
    this.state.here = id
  }
}

async function opened() {
  const link = new FakeLink()
  const session = new TestSession(link)
  await session.open()
  return { link, session, state: session.state }
}

describe('what a tag can point at', () => {
  it('offers the named things in sight, not those on another slide', async () => {
    const { session } = await opened()
    expect((await session.taggableThings()).map((t) => t.name)).toEqual(['Intro', 'Figure 1'])
  })
  it('says how many things in sight still have no name, and names them in one request', async () => {
    const { link, session } = await opened()
    expect(await session.nameUnnamed()).toBe(2)
    expect(link.calls.find((c) => c.method === 'name_unnamed')!.params).toEqual({ base: 'main:3' })
  })
  it('knows the current name of a thing, and it follows a rename', async () => {
    const { link, session } = await opened()
    expect(session.nameOf('o1')).toBe('Figure 1')
    link.push('thing_renamed', { type: 'thing_renamed', id: 'o1', name: 'Revenue' })
    expect(session.nameOf('o1')).toBe('Revenue')
    expect(session.nameOf('nothing')).toBeUndefined()
  })
})

describe('going to what a tag points at', () => {
  it('switches to where the thing is and marks it, with a way back', async () => {
    const { session, state } = await opened()
    await session.goToThing('o2')
    expect(state.here).toBe('s2')
    expect(state.pointed).toEqual({ id: 'o2', container: 's2' })
    expect(state.wayBack).toEqual({ container: 's1', anchor: null })
    session.goBack()
    expect(state.here).toBe('s1')
    expect(state.pointed).toBeNull()
    expect(state.wayBack).toBeNull()
  })
  it('marks a thing that is in sight without moving; the way back is where the view was, scrolled or not (D1312)', async () => {
    const { session, state } = await opened()
    session.setAnchorProvider(() => 'top')
    await session.goToThing('o1')
    expect(state.here).toBe('s1')
    expect(state.pointed).toEqual({ id: 'o1', container: 's1' })
    expect(state.wayBack).toEqual({ container: 's1', anchor: 'top' })
  })
  it('takes a tag to something deleted to the last step it was there, in a replay', async () => {
    const { session, state } = await opened()
    await session.goToThing('gone')
    expect(state.replay).toMatchObject({ revision: 'main:2' })
    expect(state.notice!.text).toMatch(/last moment/i)
  })
  it('says so when the thing never was here', async () => {
    const { link, session, state } = await opened()
    link.seen = { present: false, revision: null }
    await session.goToThing('nope')
    expect(state.replay).toBeNull()
    expect(state.notice!.kind).toBe('warning')
  })
  it('leaves a replay for the present when the thing is there now but not in the past being shown', async () => {
    const { link, session, state } = await opened()
    await session.startReplay()
    link.seen = { present: true, revision: 'main:3' }
    session.deck = session.deck.filter((t) => t.id !== 'o2')
    await session.goToThing('o2')
    expect(state.replay).toBeNull()
  })
})
