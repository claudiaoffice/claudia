import { describe, expect, it } from 'vitest'
import { BaseSession, type BaseState, type Entry } from '~/lib/base-session'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Region, type Welcome, type WireData } from '~/lib/protocol'
import { PlannedLink, lookOnly, roleNow } from '~/lib/replay'
import type { RedactionPlan } from '~/lib/redaction'
import { viewTints } from '~/lib/replay-tint'

const WELCOME: Welcome = {
  user: 'ana',
  role: 'owner',
  doc: 'pay',
  app: 'creates',
  line: 'main',
  revision: 'main:2',
  id: 1,
  color: '#e6194b',
  people: [],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
  lines: [{ name: 'main', head: 'main:2', active: true, forked_from: null }],
  proposal: null,
  returned: null,
}

const entry = (n: number, author = 'bob'): Entry => ({ revision: `main:${n}`, author, origin: 'do', time: '', label: `step ${n}`, summary: '', kind: 'creates.AddObject', redacted: false })
const place: Region = { kind: 'objects', container: 's1', ids: ['t1'] } as Region
const PLAN: RedactionPlan = {
  targets: ['main:2'],
  dependents: [],
  chat: [],
  imports: [],
  changes_now: true,
  allowed: true,
  others: [],
  steps: [entry(2)],
  app: 'creates',
  plan: 'tok',
  regions: [place],
}

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  events: EventHandler[] = []
  async connect() {
    return WELCOME
  }
  async request(method: string, params: any = {}): Promise<any> {
    this.calls.push({ method, params })
    switch (method) {
      case 'log':
        return [entry(1, 'ana'), entry(2)]
      case 'chat_log':
        return []
      case 'checkpoints':
        return []
      case 'history':
        return { can_undo: true, can_redo: false, undo_label: '', redo_label: '' }
      case 'lines':
        return WELCOME.lines
      case 'restore_policy':
        return { policy: 'consensus' }
      case 'slides':
        return ['live']
      case 'as_planned':
        return [`planned ${params.plan}`]
      case 'redaction_plan':
        return PLAN
      case 'redact':
        return { revision: 'main:3' }
      case 'chat':
        return { number: 1 }
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
  methods() {
    return this.calls.map((c) => c.method)
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
  async change() {
    return this.attempt('add_slide')
  }
}

async function opened() {
  const link = new FakeLink()
  const session = new TestSession(link)
  await session.open()
  return { link, session }
}

describe('working a redaction out', () => {
  it('asks the server for the plan of a pick, without the state', async () => {
    const { link, session } = await opened()
    const plan = await session.planRedaction({ revisions: ['main:2'], chat: [1], parts: { 'main:2': ['t1'] } })
    expect(plan).toEqual(PLAN)
    expect(link.calls.at(-1)).toEqual({ method: 'redaction_plan', params: { revisions: ['main:2'], chat: [1], parts: { 'main:2': ['t1'] }, state: false } })
  })
})

describe('the preview of a redaction (D721)', () => {
  it('shows the planned state in the views, marks the places and goes to them', async () => {
    const { link, session } = await opened()
    await session.previewRedaction(PLAN)
    expect(session.state.slides).toEqual(['planned tok'])
    expect(link.calls.at(-1)).toEqual({ method: 'as_planned', params: { plan: 'tok', method: 'slides', params: {} } })
    expect(viewTints(session.state).object('t1')).toBe('now')
    expect(session.state.followed).toEqual(['s1'])
    expect(lookOnly(session.state)).toBe(true)
    expect(roleNow(session.state)).toBe('viewer')
  })
  it('lets nothing that changes the document through while it is shown', async () => {
    const { link, session } = await opened()
    await session.previewRedaction(PLAN)
    const before = link.calls.length
    expect(await session.change()).toBe(false)
    expect(link.calls).toHaveLength(before)
  })
  it('keeps the views on the preview when the present changes, and goes back to it at the end', async () => {
    const { session, link } = await opened()
    await session.previewRedaction(PLAN)
    link.push('slides', { slides: ['someone else'] })
    expect(session.state.slides).toEqual(['planned tok'])
    await session.endPreview()
    expect(session.state.preview).toBeNull()
    expect(session.state.slides).toEqual(['live'])
    expect(viewTints(session.state).object('t1')).toBeNull()
  })
  it('shows the present for a plan that changes nothing people see, or that is not allowed', async () => {
    const { session } = await opened()
    await session.previewRedaction({ ...PLAN, changes_now: false })
    expect(session.state.preview).toBeNull()
    await session.previewRedaction({ ...PLAN, allowed: false, plan: undefined })
    expect(session.state.preview).toBeNull()
  })
  it('does not start a replay while a preview is on', async () => {
    const { session } = await opened()
    await session.previewRedaction(PLAN)
    await session.startReplay()
    expect(session.state.replay).toBeNull()
  })
})

describe('carrying a redaction out', () => {
  it('ends the preview, confirms the dependents it was shown and sends the note', async () => {
    const { link, session } = await opened()
    await session.previewRedaction(PLAN)
    const picked = { revisions: ['main:2'], chat: [] }
    expect(await session.redact(picked, { ...PLAN, dependents: ['main:3'] }, '@bob I redacted it. ')).toBe(true)
    expect(session.state.preview).toBeNull()
    const redact = link.calls.find((c) => c.method === 'redact')!
    expect(redact.params).toEqual({ revisions: ['main:2'], chat: [], dependents: ['main:3'] })
    expect(link.calls.at(-1)).toMatchObject({ method: 'chat', params: { text: '@bob I redacted it.' } })
  })
  it('sends no note when there is none', async () => {
    const { link, session } = await opened()
    await session.redact({ revisions: ['main:2'], chat: [] }, PLAN, '  ')
    expect(link.methods()).not.toContain('chat')
  })
  it('says once that the history was redacted and reloads', async () => {
    const { link, session } = await opened()
    const before = link.methods().filter((m) => m === 'log').length
    link.push('redacted', { revisions: ['main:2'], chat: [] })
    link.push('rebuilt', {})
    await new Promise((r) => setTimeout(r, 0))
    expect(session.state.notice?.text).toContain('redacted')
    expect(link.methods().filter((m) => m === 'log').length).toBe(before + 1)
  })
})

describe('the link of a preview', () => {
  it('lets reading, talking and planning through, nothing else', async () => {
    const link = new FakeLink()
    const planned = new PlannedLink(link, () => 'tok')
    await planned.request('cells', { sheet: 's' }).catch(() => {})
    expect(link.calls[0]).toEqual({ method: 'as_planned', params: { plan: 'tok', method: 'cells', params: { sheet: 's' } } })
    await planned.request('redaction_plan', {})
    expect(link.calls[1]!.method).toBe('redaction_plan')
    await expect(planned.request('redact', {})).rejects.toMatchObject({ code: 'forbidden' })
  })
})
