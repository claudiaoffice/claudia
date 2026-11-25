import { describe, expect, it } from 'vitest'
import { STYLE_MODEL } from './style-model.fixture'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { TextSession } from '~/lib/text-session'

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'essay',
  app: 'composes',
  branch: 'main',
  revision: 'main:2',
  id: 1,
  color: '#e6194b',
  people: [],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
  branches: [{ name: 'main', head: 'main:2', active: true, forked_from: null }],
  proposal: null,
  returned: null,
}

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  handlers: Record<string, (params: any) => any> = {}
  events: EventHandler[] = []
  async connect() {
    return WELCOME
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
  onClose(_h: CloseHandler) {}
  close() {}
  push(name: string, data: any) {
    for (const h of this.events) h(name, data)
  }
  last(method: string) {
    return this.calls.filter((c) => c.method === method).at(-1)?.params
  }
}

const BODY = { id: 'body', name: 'Body text', purpose: '', based_on: null, css: {}, computed: {}, to_name: false }
const object = (id: string, kind = 'image') => ({
  id, kind, w: 400, h: 200, style: 'plain-image', paragraph: null, ref: null, imported: null,
  rotation: 0, snap: false, anchor: { kind: 'paragraph', holder: 'b1', offset: 0 },
})

async function opened() {
  const link = new FakeLink()
  const done = () => ({ revision: 'main:3' })
  link.handlers = {
    paragraphs: () => ({ revision: 'main:2', styles: [BODY], paragraphs: [{ id: 'b1', style: 'body', text: 'a😀b', runs: [] }, { id: 'b2', style: 'body', text: 'two', runs: [] }], lists: [], schemes: [] }),
    suggestions: () => [],
    style_model: () => STYLE_MODEL,
    palette: () => ({ type: 'palette', roles: [], readings: [] }),
    log: () => [],
    chat_log: () => [],
    checkpoints: () => [],
    history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
    branches: () => [{ name: 'main', head: 'main:2', active: true, forked_from: null }],
    restore_policy: () => ({ policy: 'consensus' }),
    objects: () => ({ revision: 'main:2', objects: [object('o1'), object('t1', 'table')] }),
    move_object: done,
    resize_object: done,
    rotate_object: done,
    describe_object: done,
    apply_style: done,
    deviate: done,
  }
  const session = new TextSession(() => link, { retryDelays: [0] })
  await session.open()
  return { link, session, state: session.state }
}

describe('the floating objects of a text, as the object interaction asks for them (D1221)', () => {
  it('hangs an object from another character and floats it at an offset, in the units the server counts', async () => {
    const { link, session } = await opened()
    expect(await session.moveObject('o1', { paragraph: 'b1', offset: 3 }, { dx: 40, dy: -12 })).toBe(true)
    // the page counts UTF-16 units, the server characters: the emoji is one character there
    expect(link.last('move_object')).toEqual({ id: 'o1', paragraph: 'b1', offset: 2, dx: 40, dy: -12, base: 'main:2' })
  })
  it('leaves the offset out when it is not given, so the server keeps what the object has', async () => {
    const { link, session } = await opened()
    await session.moveObject('o1', { paragraph: 'b2', offset: 0 })
    expect(link.last('move_object')).toEqual({ id: 'o1', paragraph: 'b2', offset: 0, base: 'main:2' })
  })
  it('turns an object to a whole number of degrees', async () => {
    const { link, session } = await opened()
    expect(await session.rotateObject('o1', 45)).toBe(true)
    expect(link.last('rotate_object')).toEqual({ id: 'o1', rotation: 45, base: 'main:2' })
  })
  it('describes an object, and sends no words for a decoration', async () => {
    const { link, session } = await opened()
    await session.describeObject('o1', '  a cat  ', false)
    expect(link.last('describe_object')).toMatchObject({ id: 'o1', description: 'a cat', decorative: false })
    await session.describeObject('o1', 'typed before it was ticked', true)
    expect(link.last('describe_object')).toMatchObject({ description: '', decorative: true })
  })
  it('styles an object through the one style API every app has', async () => {
    const { link, session } = await opened()
    await session.applyObjectStyle([{ object: 'o1' }], 'plain-image', 'box')
    expect(link.last('apply_style')).toEqual({ targets: [{ object: 'o1' }], style: 'plain-image', slot: 'box', base: 'main:2' })
    await session.deviateObjectStyle('plain-image', [{ object: 'o1' }], 'box', { set: { 'border-width': '2px' } } as never)
    expect(link.last('deviate')).toMatchObject({ parent: 'plain-image', targets: [{ object: 'o1' }], slot: 'box' })
  })
  it('offers every object of the document for the use counts of the style menu', async () => {
    const { session } = await opened()
    expect(session.bodies().map((o) => o.id).sort()).toEqual(['o1', 't1'])
    expect(session.styleViews().map((s) => s.id)).toEqual(['body'])
  })
  it('starts with no container being written in', async () => {
    const { state } = await opened()
    expect(state.editingObject).toBeNull()
    expect(state.selectedObject).toBeNull()
  })
})

describe('selecting an object locks it, as in creates (D1223)', () => {
  async function withLocks() {
    const opened_ = await opened()
    Object.assign(opened_.link.handlers, { lock: () => ({}), unlock: () => ({}), presence: () => ({}), hold: () => ({}) })
    return opened_
  }
  const count = (link: FakeLink, method: string) => link.calls.filter((c) => c.method === method).length

  it('locks the selected object so that nobody else changes it, and unlocks it', async () => {
    const { link, session, state } = await withLocks()
    await session.selectObject('o1')
    expect(state.selectedObject).toBe('o1')
    expect(link.last('lock').regions).toEqual([{ kind: 'objects', holder: 'b1', ids: ['o1'] }])
    await session.selectObject(null)
    expect(state.selectedObject).toBeNull()
    expect(count(link, 'unlock')).toBe(1)
    expect(link.last('presence').regions).toEqual([])
  })
  it('unlocks an object let go of before the server answered the lock', async () => {
    const { link, session } = await withLocks()
    let answer = () => {}
    link.handlers.lock = () => new Promise((done) => (answer = () => done({})))
    const selecting = session.selectObject('o1')
    const lettingGo = session.selectObject(null)
    answer()
    await Promise.all([selecting, lettingGo])
    expect(count(link, 'unlock')).toBe(1)
  })
  it('locks the object again where it hangs after it was moved to another paragraph', async () => {
    const { link, session } = await withLocks()
    await session.selectObject('o1')
    await session.moveObject('o1', { paragraph: 'b2', offset: 0 })
    expect(link.last('lock').regions).toEqual([{ kind: 'objects', holder: 'b2', ids: ['o1'] }])
  })
  it('unlocks the selected object when a colleague removes it', async () => {
    const { link, session, state } = await withLocks()
    await session.selectObject('o1')
    link.push('objects', { type: 'objects', holder: 'b1', changed: [], removed: ['o1'], order: [] })
    await session.settled()
    expect(state.selectedObject).toBeNull()
    expect(count(link, 'unlock')).toBe(1)
  })
  it('does not keep a selection a colleague has locked, and says why', async () => {
    const { link, session, state } = await withLocks()
    link.handlers.lock = () => {
      throw new ProtocolError('locked', 'ben is working on that')
    }
    await session.selectObject('o1')
    expect(state.selectedObject).toBeNull()
    expect(state.notice).toMatchObject({ kind: 'warning', text: 'ben is working on that' })
  })
  it('tells which objects colleagues have selected, whatever paragraph they hang from', async () => {
    const { link, session } = await withLocks()
    link.push('ephemeral', { kind: 'presence', sender: 'ben', data: { regions: [{ kind: 'objects', holder: 'b1', ids: ['t1'] }], locked: true } })
    expect(session.selectedByOthers()).toEqual([{ id: 't1', user: 'ben', locked: true }])
    link.push('ephemeral', { kind: 'presence', sender: 'ben', data: { regions: [], locked: false } })
    expect(session.selectedByOthers()).toEqual([])
  })
  it('does not hold the words round the caret while an object is selected, which would unlock it', async () => {
    const { link, session, state } = await withLocks()
    state.selection = { anchor: { paragraph: 'b2', offset: 1 }, focus: { paragraph: 'b2', offset: 1 } } as never
    await session.selectObject('o1')
    await session.placeNow()
    expect(count(link, 'hold')).toBe(0)
  })
  it('holds the words round the caret again after an object was unlocked', async () => {
    const { link, session, state } = await withLocks()
    state.selection = { anchor: { paragraph: 'b2', offset: 1 }, focus: { paragraph: 'b2', offset: 1 } } as never
    await session.placeNow()
    await session.selectObject('o1')
    await session.selectObject(null)
    await session.placeNow()
    expect(count(link, 'hold')).toBe(2)
  })
})
