import { describe, expect, it } from 'vitest'
import { BaseSession, type BaseState, type Step } from '~/lib/base-session'
import type { LinkLike, Region, Welcome, WireData } from '~/lib/protocol'
import { PastLink } from '~/lib/replay'
import { FakeServer } from './support/fake-server'

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
const slideRegion = (holder: string): Region => ({ kind: 'objects', holder, ids: [] }) as Region

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
    this.state.followed = focus.map((r) => (r.kind === 'objects' ? r.holder : ''))
  }
  // reaches the protected link the way an app's own changes do
  async change() {
    return this.attempt('add_slide')
  }
}

/** A test holds `as_of` back with this, to see what a replay does while an answer is on its way. */
let gate: Promise<void> | null = null

function fake() {
  gate = null
  return new FakeServer('creates', { welcome: WELCOME })
    .on('log', () => [entry(1), entry(2, 'bo'), entry(3)])
    .on('chat_log', () => [{ number: 1, author: 'bo', to: '', text: 'hi', time: '', at: 'main:2' }])
    .on('history', () => ({ can_undo: true, can_redo: false, undo_label: '', redo_label: '' }))
    .on('branches', () => [{ name: 'main', head: 'main:3', active: true, forked_from: null }])
    .on('slides', () => ['live'])
    .on('peek_revision', ({ revision }: any) => ({
      revision,
      entry: entry(Number(revision.slice(5))),
      focus: [slideRegion(`s${revision.slice(5)}`)],
      app: 'creates',
    }))
    .on('as_of', async ({ revision }: any) => {
      if (gate) await gate
      return [`past ${revision}`]
    })
    .on('changes_since', ({ revision }: any) => ({ regions: [slideRegion(`later than ${revision}`)], truncated: revision === 'main:1' }))
    .on('propose_restore_step', () => ({ applied: false, proposal: null }))
    .on('chat', () => ({ number: 2 }))
    .on('add_slide', () => ({ revision: 'main:4' }))
}

/** The revisions the page asked the past of, in order. */
const asOf = (link: FakeServer) => link.sent('as_of').map((p) => p.revision)

async function opened() {
  const link = fake()
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
    expect(asOf(link)).toEqual(['main:2'])
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
    gate = new Promise((resolve) => (open = resolve))
    await session.startReplay()
    const steps = [session.replayStep(-1), session.replayStep(-1), session.replayStep(-1), session.replayStep(-1)]
    open()
    await Promise.all(steps)
    expect(state.replay!.revision).toBe('main:1')
    expect(asOf(link).length).toBeLessThanOrEqual(2)
    expect(asOf(link).at(-1)).toBe('main:1')
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
    const link = fake().on('log', [])
    const session = new TestSession(link)
    await session.open()
    await session.startReplay()
    expect(session.state.replay).toBeNull()
  })
})

describe('the link of a replay', () => {
  it('lets only reading and talking through', async () => {
    const link = fake()
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
