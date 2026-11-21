import { describe, expect, it } from 'vitest'
import { BaseSession, type BaseState, type Step } from '~/lib/base-session'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Region, type Welcome, type WireData } from '~/lib/protocol'
import { PastLink } from '~/lib/replay'

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

const entry = (n: number, author = 'ann'): Step => ({ revision: `main:${n}`, author, origin: 'do', time: '', label: `step ${n}`, summary: '' })
const slideRegion = (container: string): Region => ({ kind: 'objects', container, ids: [] }) as Region

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  events: EventHandler[] = []
  gate: Promise<void> | null = null
  async connect() {
    return WELCOME
  }
  async request(method: string, params: any = {}): Promise<any> {
    this.calls.push({ method, params })
    if (method === 'as_of' && this.gate) await this.gate
    switch (method) {
      case 'log':
        return [entry(1), entry(2, 'bo'), entry(3)]
      case 'chat_log':
        return [{ number: 1, author: 'bo', to: '', text: 'hi', time: '', at: 'main:2' }]
      case 'checkpoints':
        return []
      case 'history':
        return { can_undo: true, can_redo: false, undo_label: '', redo_label: '' }
      case 'branches':
        return [{ name: 'main', head: 'main:3', active: true, forked_from: null }]
      case 'restore_policy':
        return { policy: 'consensus' }
      case 'slides':
        return ['live']
      case 'peek_revision':
        return { revision: params.revision, entry: entry(Number(params.revision.slice(5))), focus: [slideRegion(`s${params.revision.slice(5)}`)], app: 'creates' }
      case 'as_of':
        return [`past ${params.revision}`]
      case 'changes_since':
        return { regions: [slideRegion(`later than ${params.revision}`)], truncated: params.revision === 'main:1' }
      case 'propose_restore_step':
        return { applied: false, proposal: null }
      case 'chat':
        return { number: 2 }
      case 'add_slide':
        return { revision: 'main:4' }
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
  asOf() {
    return this.calls.filter((c) => c.method === 'as_of').map((c) => c.params.revision)
  }
}

interface TestState extends BaseState {
  slides: string[]
  followed: string[]
}

class TestSession extends BaseSession<TestState> {
  constructor(link: LinkLike) {
    super(() => link, { retryDelays: [1] }, { slides: [], followed: [] })
  }
  protected async loadApp() {
    this.state.slides = await this.need().request<string[]>('slides')
  }
  protected onAppEvent(name: string, data: WireData) {
    if (name !== 'slides') return false
    this.state.slides = data.slides
    return true
  }
  protected followReplay(focus: Region[]) {
    this.state.followed = focus.map((r) => (r.kind === 'objects' ? r.container : ''))
  }
  // reaches the protected link the way an app's own changes do
  async change() {
    return this.attempt('add_slide')
  }
}

async function opened() {
  const link = new FakeLink()
  const session = new TestSession(link)
  await session.open()
  return { link, session, state: session.state }
}

describe('looking at the past', () => {
  it('answers the views from the step the playhead is on, and not from the present', async () => {
    const { link, session, state } = await opened()
    await session.startReplay()
    expect(state.replay).toMatchObject({ revision: 'main:3', filter: 'all' })
    await session.replayStep(-1)
    expect(link.asOf()).toEqual(['main:2'])
    expect(state.slides).toEqual(['past main:2'])
    expect(state.replay!.revision).toBe('main:2')
  })
  it('visits the rows of the history, a chat message showing the document as it was when it was written', async () => {
    const { session, state } = await opened()
    await session.startReplay()
    await session.replayStep(-1)
    expect(state.replay!.row).toBe('m:1') // the message written after step 2
    expect(state.replay!.revision).toBe('main:2')
    await session.replayStep(-1)
    expect(state.replay!.row).toBe('c:main:2')
    await session.replayStep(-1)
    expect(state.replay!.revision).toBe('main:1')
  })
  it('lets the view follow what a step touched, unless the person looks elsewhere', async () => {
    const { session, state } = await opened()
    await session.startReplay()
    await session.replayStep(-1)
    expect(state.followed).toEqual(['s2'])
    expect(state.replay!.focus).toHaveLength(1)
    session.setReplayFollow(false)
    await session.replayStep(-1)
    await session.replayStep(-1)
    expect(state.followed).toEqual(['s2'])
  })
  it('asks for the last step it was told of when the wheel runs ahead of the server', async () => {
    const { link, session, state } = await opened()
    let open!: () => void
    link.gate = new Promise((resolve) => (open = resolve))
    await session.startReplay()
    const steps = [session.replayStep(-1), session.replayStep(-1), session.replayStep(-1), session.replayStep(-1)]
    open()
    await Promise.all(steps)
    expect(state.replay!.revision).toBe('main:1')
    expect(link.asOf().length).toBeLessThanOrEqual(2)
    expect(link.asOf().at(-1)).toBe('main:1')
  })
  it('keeps the conversation live, and counts what colleagues do meanwhile', async () => {
    const { link, session, state } = await opened()
    await session.startReplay()
    await session.replayStep(-1)
    expect(await session.say('hello')).toBe(true)
    link.push('command', entry(4, 'bo'))
    link.push('slides', { slides: ['live 4'] })
    expect(state.replay!.newer).toBe(1)
    expect(state.slides).toEqual(['past main:2']) // the past is not disturbed by the present
    expect(state.entries.at(-1)!.revision).toBe('main:4')
  })
  it('refuses to change the document while looking at the past', async () => {
    const { link, session, state } = await opened()
    await session.startReplay()
    expect(await session.change()).toBe(false)
    expect(link.calls.some((c) => c.method === 'add_slide')).toBe(false)
    expect(state.notice!.kind).toBe('warning')
  })
  it('comes back to the present, loading it again', async () => {
    const { session, state } = await opened()
    await session.startReplay()
    await session.replayStep(-1)
    await session.endReplay()
    expect(state.replay).toBeNull()
    expect(state.slides).toEqual(['live'])
    expect(await session.change()).not.toBe(false)
  })
  it('is over when the document is rebuilt under it', async () => {
    const { link, session, state } = await opened()
    await session.startReplay()
    link.push('rebuilt', {})
    await session.settled()
    expect(state.replay).toBeNull()
    expect(state.slides).toEqual(['live'])
  })
  it('changes what the wheel visits without losing the place', async () => {
    const { session, state } = await opened()
    await session.startReplay()
    await session.replayStep(-1)
    await session.replayStep(-1) // on the chat message
    session.setReplayFilter('steps')
    expect(state.replay!.revision).toBe('main:2')
    expect(session.replayItems().every((i) => i.kind === 'change')).toBe(true)
    expect(session.replayIndex()).toBe(1)
  })
  it('marks what changed after the step only when asked, and for the step that is on show', async () => {
    const { link, session, state } = await opened()
    await session.startReplay()
    await session.replayStep(-1)
    expect(state.replay).toMatchObject({ differences: false, changed: [] })
    expect(link.calls.some((c) => c.method === 'changes_since')).toBe(false)
    await session.setReplayDifferences(true)
    expect(state.replay!.changed).toEqual([slideRegion('later than main:2')])
    await session.replayStep(-1)
    await session.replayStep(-1)
    expect(state.replay!.revision).toBe('main:1')
    expect(state.replay!.changed).toEqual([slideRegion('later than main:1')])
    expect(state.replay!.changedMore).toBe(true)
  })
  it('stops marking the differences when turned off', async () => {
    const { session, state } = await opened()
    await session.startReplay()
    await session.setReplayDifferences(true)
    await session.setReplayDifferences(false)
    expect(state.replay).toMatchObject({ differences: false, changed: [], changedMore: false })
  })
  it('suggests going back to the step on show, which the past may still ask', async () => {
    const { link, session } = await opened()
    await session.startReplay()
    await session.replayStep(-1)
    expect(await session.proposeRestoreStep()).toBe(true)
    expect(link.calls.at(-1)).toEqual({ method: 'propose_restore_step', params: { revision: 'main:2' } })
  })
  it('has no step to go back to in the present', async () => {
    const { link, session } = await opened()
    expect(await session.proposeRestoreStep()).toBe(false)
    expect(link.calls.some((c) => c.method === 'propose_restore_step')).toBe(false)
  })
  it('does not start without a history to look at', async () => {
    const link = new FakeLink()
    const log = link.request.bind(link)
    link.request = async (m: string, p: any = {}) => (m === 'log' ? [] : log(m, p))
    const session = new TestSession(link)
    await session.open()
    await session.startReplay()
    expect(session.state.replay).toBeNull()
  })
})

describe('the link of a replay', () => {
  it('lets only reading and talking through', async () => {
    const link = new FakeLink()
    const past = new PastLink(link, () => 'main:2')
    await past.request('cells', { sheet: 's' }).catch(() => {})
    expect(link.calls[0]).toEqual({ method: 'as_of', params: { revision: 'main:2', method: 'cells', params: { sheet: 's' } } })
    await past.request('chat', { text: 'x' })
    expect(link.calls[1]!.method).toBe('chat')
    await expect(past.request('delete_document')).rejects.toMatchObject({ code: 'forbidden' })
    await expect(past.request('set_text', {})).rejects.toMatchObject({ code: 'forbidden' })
    expect(link.calls).toHaveLength(2)
  })
})
