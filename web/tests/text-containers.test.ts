import { describe, expect, it } from 'vitest'
import { STYLE_MODEL } from './style-model.fixture'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { TextSession } from '~/lib/text-session'

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'essay',
  app: 'composes',
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
const CIRCLE = { format: 1, id: 'circle', name: 'Circle', path: 'M0 0Z', aspect: 1, text_area: { x: 0, y: 0, w: 100, h: 100 } }
const STAR = { ...CIRCLE, id: 'star', name: 'Star', aspect: null }
const TYPES = { types: [{ type: 'latex', title: 'LaTeX', example: 'x^2' }] }
const object = (id: string, block = 'b1', offset = 0, extra: object = {}) => ({
  id, kind: 'rendered', w: 400, h: 200, style: 'plain-image', paragraph: null, ref: 'r1', imported: null,
  rotation: 0, snap: false, anchor: { kind: 'block', container: block, offset }, ...extra,
})

async function opened(objects: object[] = [], text = 'a😀b') {
  const link = new FakeLink()
  link.handlers = {
    blocks: () => ({ revision: 'main:2', styles: [BODY], blocks: [{ id: 'b1', style: 'body', text, runs: [] }, { id: 'b2', style: 'body', text: 'two', runs: [] }], lists: [], schemes: [] }),
    suggestions: () => [],
    style_model: () => STYLE_MODEL,
    palette: () => ({ type: 'palette', roles: [], readings: [] }),
    log: () => [],
    chat_log: () => [],
    checkpoints: () => [],
    history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
    lines: () => [{ name: 'main', head: 'main:2', active: true, forked_from: null }],
    restore_policy: () => ({ policy: 'consensus' }),
    rendering_types: () => TYPES,
    renderings: () => [{ format: 1, id: 'r1', type: 'latex', source: 'x', params: {}, image: null, renderer: '' }],
    objects: () => ({ revision: 'main:2', objects }),
    shapes: () => ({ library: [CIRCLE, STAR], document: [CIRCLE] }),
    add_object: () => ({ object: 'o8', revision: 'main:3' }),
    set_wrap: () => ({ revision: 'main:3' }),
    add_image: () => ({ object: 'o7', revision: 'main:3' }),
    images: () => [{ id: 'i1', format: 'svg', width: 3, height: 2, animated: false, data: 'AA==', first_frame: null }],
    add_rendering: () => ({ object: 'o9', rendering: 'r9', revision: 'main:3' }),
    move_object: () => ({ revision: 'main:3' }),
    resize_object: () => ({ revision: 'main:3' }),
    remove_object: () => ({ revision: 'main:3' }),
  }
  const session = new TextSession(() => link, { retryDelays: [0] })
  await session.open()
  return { link, session, state: session.state }
}

describe('containers in a text', () => {
  it('knows the objects and their pictures, by paragraph', async () => {
    const { session, state } = await opened([object('o1'), object('o2', 'b2', 1)])
    expect(session.objectsIn('b1').map((o) => o.id)).toEqual(['o1'])
    expect(session.objectsIn('b2').map((o) => o.id)).toEqual(['o2'])
    expect(state.images.i1!.width).toBe(3)
    expect(state.renderTypes.map((t) => t.type)).toEqual(['latex'])
  })
  it('opens as before with a server that has no objects', async () => {
    const link = new FakeLink()
    const { link: full } = await opened()
    link.handlers = { ...full.handlers }
    delete link.handlers.objects
    delete link.handlers.images
    delete link.handlers.rendering_types
    delete link.handlers.renderings
    const session = new TextSession(() => link, { retryDelays: [0] })
    await session.open()
    expect(session.state.status).toBe('open')
    expect(session.state.objects).toEqual({})
  })
  it('follows the server when objects change, move to another paragraph or go', async () => {
    const { link, session } = await opened([object('o1')])
    link.push('objects', { type: 'objects', container: 'b1', changed: [object('o3', 'b1', 2)], removed: [], order: ['o1', 'o3'] })
    expect(session.objectsIn('b1').map((o) => o.id)).toEqual(['o1', 'o3'])
    link.push('objects', { type: 'objects', container: 'b2', changed: [object('o1', 'b2', 0)], removed: [], order: ['o1'] })
    expect(session.objectsIn('b1').map((o) => o.id)).toEqual(['o3'])
    expect(session.objectsIn('b2').map((o) => o.id)).toEqual(['o1'])
    link.push('objects', { type: 'objects', container: 'b1', changed: [], removed: ['o3'], order: [] })
    expect(session.objectsIn('b1')).toEqual([])
  })
  it('takes in a picture when the server sends one', async () => {
    const { link, state } = await opened()
    link.push('image', { type: 'image', id: 'i2', asset: { id: 'i2', format: 'svg', width: 1, height: 1, animated: false, data: 'AA==', first_frame: null } })
    expect(state.images.i2).toBeDefined()
  })
  it('knows the outlines the shapes in the text are drawn with, and takes in a new one', async () => {
    const { link, state } = await opened()
    expect(state.shapes.circle!.path).toBe('M0 0Z')
    link.push('shape', { type: 'shape', id: 'star', definition: { format: 1, id: 'star', name: 'Star', path: 'M1 1Z', aspect: null, text_area: { x: 0, y: 0, w: 1, h: 1 } } })
    expect(state.shapes.star).toBeDefined()
    link.push('shape', { type: 'shape', id: 'star', definition: null })
    expect(state.shapes.star).toBeUndefined()
  })
  it('keeps the offset of an object off its character, and an object that is not rendered', async () => {
    const { session } = await opened([object('o1', 'b1', 0, { kind: 'image', rendered: null, image: 'i1', anchor: { kind: 'block', container: 'b1', offset: 0, dx: 12, dy: -4 } })])
    expect(session.objectsIn('b1')[0]!.anchor).toMatchObject({ dx: 12, dy: -4 })
  })
  it('tells where an object hangs in the units of the screen, though the server counts characters', async () => {
    const { session } = await opened([object('o1', 'b1', 2), object('o2', 'zz', 5)])
    // 'a😀b': character 2 is after the emoji, which is unit 3 here
    expect(session.placeOf(session.state.objects.o1!)).toEqual({ block: 'b1', offset: 3 })
    // a paragraph that is not known (yet): no place to hang it at
    expect(session.placeOf(session.state.objects.o2!)).toBeNull()
  })
  it('puts a picture where the caret is, counting characters the way the server does, and selects it', async () => {
    const { link, session, state } = await opened()
    const picture = { data: 'AAAA', alt: 'a cat', sourceName: 'cat.png', sourcePath: null }
    expect(await session.addImage(picture, { block: 'b1', offset: 3 }, { w: 300, h: 200 })).toBe('o7')
    expect(link.last('add_image')).toEqual({ block: 'b1', offset: 2, w: 300, h: 200, data: 'AAAA', alt: 'a cat', source_name: 'cat.png', source_path: null, base: 'main:2' })
    expect(state.selectedObject).toBe('o7')
  })
  it('says that a picture is only decoration, and then needs no words', async () => {
    const { link, session } = await opened()
    await session.addImage({ data: 'AAAA', alt: '', sourceName: 'line.png', sourcePath: null, decorative: true }, { block: 'b2', offset: 0 }, { w: 100, h: 20 })
    expect(link.last('add_image')).toMatchObject({ decorative: true, alt: '' })
  })
  it('puts a container where the text is, counting characters the way the server does', async () => {
    const { link, session, state } = await opened()
    // 'a😀b': after the emoji is unit 3 here, character 2 there
    expect(await session.addContainer('latex', { block: 'b1', offset: 3 }, { w: 300, h: 100 })).toBe('o9')
    expect(link.last('add_rendering')).toMatchObject({ block: 'b1', offset: 2, w: 300, h: 100, type: 'latex', source: 'x^2' })
    expect(state.selectedObject).toBe('o9')
  })
  it('offers the shapes the server has, and keeps the ones the document uses apart', async () => {
    const { session, state } = await opened()
    expect(state.library.map((s) => s.id)).toEqual(['circle', 'star'])
    expect(Object.keys(state.shapes)).toEqual(['circle'])
  })
  it('still opens with a server whose `shapes` is only the list of the outlines the document uses', async () => {
    const { link: full } = await opened()
    const link = new FakeLink()
    link.handlers = { ...full.handlers, shapes: () => [CIRCLE] }
    const session = new TextSession(() => link, { retryDelays: [0] })
    await session.open()
    expect(Object.keys(session.state.shapes)).toEqual(['circle'])
    expect(session.state.library).toEqual([])
  })
  it('puts a shape and a text box where the caret is, as the server counts, and selects them', async () => {
    const { link, session, state } = await opened()
    expect(await session.addShape('circle', { block: 'b1', offset: 3 }, { w: 120, h: 120 })).toBe('o8')
    expect(link.last('add_object')).toEqual({ block: 'b1', offset: 2, kind: 'shape', shape: 'circle', w: 120, h: 120, base: 'main:2' })
    expect(state.selectedObject).toBe('o8')
    expect(await session.addTextBox({ block: 'b2', offset: 1 }, { w: 200, h: 80 })).toBe('o8')
    expect(link.last('add_object')).toEqual({ block: 'b2', offset: 1, kind: 'text', w: 200, h: 80, base: 'main:2' })
  })
  it('says how the text flows round a new picture, shape or text box when it is asked to', async () => {
    const { link, session } = await opened()
    await session.addShape('circle', { block: 'b1', offset: 0 }, { w: 100, h: 100 }, 'above-below')
    expect(link.last('add_object')).toMatchObject({ wrap: 'above-below' })
    await session.addTextBox({ block: 'b1', offset: 0 }, { w: 100, h: 100 }, 'around')
    expect(link.last('add_object')).toMatchObject({ wrap: 'around' })
    await session.addImage({ data: 'AAAA', alt: 'a cat', sourceName: 'cat.png', sourcePath: null }, { block: 'b1', offset: 0 }, { w: 100, h: 100 }, 'above-below')
    expect(link.last('add_image')).toMatchObject({ wrap: 'above-below' })
  })
  it('sets how the text flows round an object, keeping the gap when none is given', async () => {
    const { link, session } = await opened([object('o1')])
    expect(await session.setWrap('o1', 'around')).toBe(true)
    expect(link.last('set_wrap')).toEqual({ id: 'o1', wrap: 'around', base: 'main:2' })
    expect(await session.setWrap('o1', 'around', 24)).toBe(true)
    expect(link.last('set_wrap')).toMatchObject({ gap: 24 })
  })
  it('lets one key move an object through the four modes and back, one step each press (D1064)', async () => {
    const { link, session, state } = await opened([object('o1')])
    const seen: string[] = []
    for (let press = 0; press < 5; press++) {
      const now = await session.cycleWrap('o1')
      seen.push(now!)
      // the server tells everyone (this window too) what the object is now
      link.push('objects', { type: 'objects', container: 'b1', changed: [object('o1', 'b1', 0, { anchor: { kind: 'block', container: 'b1', offset: 0, wrap: now } })], removed: [], order: ['o1'] })
    }
    expect(seen).toEqual(['around', 'above-below', 'behind', 'over', 'around'])
    expect(state.objects.o1!.anchor.wrap).toBe('around')
  })
  it('cycles nothing for an object that is not there', async () => {
    const { link, session } = await opened()
    expect(await session.cycleWrap('nope')).toBeNull()
    expect(link.last('set_wrap')).toBeUndefined()
  })
  it('moves, sizes and removes an object', async () => {
    const { link, session } = await opened([object('o1')])
    expect(await session.moveObject('o1', { block: 'b1', offset: 3 })).toBe(true)
    expect(link.last('move_object')).toMatchObject({ id: 'o1', block: 'b1', offset: 2 })
    expect(await session.resizeObject('o1', 320, 120)).toBe(true)
    expect(link.last('resize_object')).toMatchObject({ id: 'o1', w: 320, h: 120 })
    expect(await session.removeObject('o1')).toBe(true)
    expect(link.last('remove_object')).toMatchObject({ id: 'o1' })
  })
  it('selects an object, and lets go of it when it goes', async () => {
    const { link, session, state } = await opened([object('o1')])
    session.selectObject('o1')
    expect(state.selectedObject).toBe('o1')
    link.push('objects', { type: 'objects', container: 'b1', changed: [], removed: ['o1'], order: [] })
    expect(state.selectedObject).toBeNull()
  })
  it('turns pasted text that is one fenced block into a container at the caret', async () => {
    const { link, session } = await opened()
    expect(await session.pasteFence('```latex\nE=mc^2\n```', { block: 'b2', offset: 1 })).toBe('o9')
    expect(link.last('add_rendering')).toMatchObject({ block: 'b2', offset: 1, type: 'latex', source: 'E=mc^2' })
  })
  it('leaves other text to be pasted as text', async () => {
    const { link, session } = await opened()
    expect(await session.pasteFence('plain words', { block: 'b1', offset: 0 })).toBeNull()
    expect(await session.pasteFence('```python\nx\n```', { block: 'b1', offset: 0 })).toBeNull()
    expect(link.last('add_rendering')).toBeUndefined()
  })
})
