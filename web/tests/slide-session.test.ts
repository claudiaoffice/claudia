import { describe, expect, it } from 'vitest'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { SlideSession } from '~/lib/slide-session'

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'talk',
  app: 'creates',
  line: 'main',
  revision: 'main:0',
  id: 1,
  color: '#e6194b',
  people: [],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
}

const RECT = { format: 1, id: 'rectangle', name: 'Rectangle', path: 'M0 0 L100 0 L100 100 L0 100 Z', aspect: null, text_area: { x: 0, y: 0, w: 100, h: 100 } }
const CIRCLE = { format: 1, id: 'circle', name: 'Circle', path: 'M50 0 A50 50 0 1 1 50 100 A50 50 0 1 1 50 0 Z', aspect: 1, text_area: { x: 15, y: 15, w: 70, h: 70 } }
const BODY = { id: 'body-text', name: 'Body text', purpose: 'Running text', css: { color: '#1f1a33' } }
const SHAPE_STYLE = { id: 'plain-shape', name: 'Plain shape', purpose: 'A shape', css: { fill: '#e7e1f4' } }

const text = (id: string, extra: object = {}) => ({
  id,
  slide: 's1',
  kind: 'text',
  x: 100,
  y: 100,
  w: 400,
  h: 120,
  style: 'body-text',
  text: '',
  shape: null,
  image: null,
  imported: null,
  ...extra,
})
const ASSET = { id: 'a'.repeat(64), format: 'gif', width: 20, height: 10, animated: false, data: 'AA==', first_frame: null }
const IMPORT = { asset: ASSET.id, alt: 'a chart', imported_by: 'ann', imported_at: '2026-11-07T10:00:00.000Z', source: 'disk', source_name: 'chart.gif', source_path: '/Users/ann/chart.gif' }
const image = (id: string, extra: object = {}) => ({
  id,
  slide: 's1',
  kind: 'image',
  x: 0,
  y: 0,
  w: 400,
  h: 200,
  style: 'plain-image',
  text: '',
  shape: null,
  image: ASSET.id,
  imported: IMPORT,
  ...extra,
})

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  handlers: Record<string, (params: any) => any> = {}
  events: EventHandler[] = []
  closers: CloseHandler[] = []
  welcome = WELCOME
  async connect() {
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
  last(method: string) {
    return this.calls.filter((c) => c.method === method).at(-1)?.params
  }
  count(method: string) {
    return this.calls.filter((c) => c.method === method).length
  }
}

function server(link: FakeLink, objects: any[] = []) {
  link.handlers = {
    slides: () => [{ id: 's1', objects: objects.length }],
    slide: ({ slide }) => ({ revision: 'main:0', slide, objects: slide === 's1' ? objects : [] }),
    shapes: () => ({ library: [CIRCLE, RECT], document: [] }),
    images: () => [],
    styles: () => [BODY, SHAPE_STYLE],
    log: () => [],
    chat_log: () => [],
    checkpoints: () => [],
    history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
    add_object: () => ({ object: 'o1', revision: 'main:1' }),
    add_image: () => ({ object: 'o1', revision: 'main:1' }),
    move_object: () => ({ revision: 'main:2' }),
    resize_object: () => ({ revision: 'main:2' }),
    set_text: () => ({ revision: 'main:2' }),
    remove_object: () => ({ revision: 'main:2' }),
    add_slide: () => ({ slide: 's2', revision: 'main:2' }),
    lock: () => ({}),
    unlock: () => ({}),
    presence: () => ({}),
  }
}

async function opened(objects: any[] = []) {
  const link = new FakeLink()
  server(link, objects)
  const session = new SlideSession(() => link, { retryDelays: [1] })
  await session.open()
  return { link, session, state: session.state }
}

describe('opening a presentation', () => {
  it('loads the slides with their objects, the shapes on offer and the styles', async () => {
    const { state, session } = await opened([text('t1', { text: 'Hello' })])
    expect(state.status).toBe('open')
    expect(state.slides).toEqual([{ id: 's1', objects: 1 }])
    expect(state.activeSlide).toBe('s1')
    expect(session.objectsOn('s1').map((o) => o.id)).toEqual(['t1'])
    expect(state.library.map((s) => s.id)).toEqual(['circle', 'rectangle'])
    expect(state.styles['body-text']!.css.color).toBe('#1f1a33')
    expect(state.selected).toBeNull()
  })
  it('knows the outlines of the document by id', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.shapes = () => ({ library: [CIRCLE], document: [RECT] })
    const session = new SlideSession(() => link)
    await session.open()
    expect(session.state.shapes.rectangle!.path).toContain('L100 100')
    expect(session.state.shapes.circle).toBeUndefined()
  })
  it('knows the decoded pictures the document has taken in, by id (E10.8)', async () => {
    const link = new FakeLink()
    server(link, [image('i1')])
    link.handlers.images = () => [ASSET]
    const session = new SlideSession(() => link)
    await session.open()
    expect(session.state.images[ASSET.id]).toEqual(ASSET)
    const o = session.objectsOn('s1')[0]!
    expect(o.image).toBe(ASSET.id)
    expect(o.imported).toEqual(IMPORT)
  })
})

describe('what the server tells', () => {
  it('adds and changes objects, in the stacking order it sends', async () => {
    const { link, session, state } = await opened([text('a'), text('b')])
    link.push('objects', { type: 'objects', slide: 's1', changed: [text('c')], removed: [], order: ['a', 'b', 'c'] })
    expect(session.objectsOn('s1').map((o) => o.id)).toEqual(['a', 'b', 'c'])
    link.push('objects', { type: 'objects', slide: 's1', changed: [text('a', { x: 7 })], removed: [], order: ['a', 'b', 'c'] })
    expect(session.objectsOn('s1')[0]!.x).toBe(7)
    expect(state.slides[0]!.objects).toBe(3)
  })
  it('takes objects away', async () => {
    const { link, session, state } = await opened([text('a'), text('b')])
    link.push('objects', { type: 'objects', slide: 's1', changed: [], removed: ['a'], order: ['b'] })
    expect(session.objectsOn('s1').map((o) => o.id)).toEqual(['b'])
    expect(state.objects.a).toBeUndefined()
    expect(state.slides[0]!.objects).toBe(1)
  })
  it('learns and forgets outlines', async () => {
    const { link, state } = await opened()
    link.push('shape', { type: 'shape', id: 'circle', definition: CIRCLE })
    expect(state.shapes.circle!.aspect).toBe(1)
    link.push('shape', { type: 'shape', id: 'circle', definition: null })
    expect(state.shapes.circle).toBeUndefined()
  })
  it('learns and forgets decoded pictures (E10.8)', async () => {
    const { link, state } = await opened()
    link.push('image', { type: 'image', id: ASSET.id, asset: ASSET })
    expect(state.images[ASSET.id]!.width).toBe(20)
    link.push('image', { type: 'image', id: ASSET.id, asset: null })
    expect(state.images[ASSET.id]).toBeUndefined()
  })
  it('reloads when the slides change', async () => {
    const { link, session, state } = await opened()
    link.handlers.slides = () => [{ id: 's1', objects: 0 }, { id: 's2', objects: 0 }]
    link.push('slides', { type: 'slides' })
    await session.settled()
    expect(state.slides.map((s) => s.id)).toEqual(['s1', 's2'])
  })
  it('moves to a slide that exists when the one on screen is gone', async () => {
    const { link, session, state } = await opened()
    state.activeSlide = 's9'
    link.push('slides', { type: 'slides' })
    await session.settled()
    expect(state.activeSlide).toBe('s1')
  })
  it('drops the selection of an object that somebody else removed', async () => {
    const { link, session, state } = await opened([text('a')])
    await session.select('a')
    link.push('objects', { type: 'objects', slide: 's1', changed: [], removed: ['a'], order: [] })
    expect(state.selected).toBeNull()
    await session.settled()
    expect(link.count('unlock')).toBe(1)
  })
})

describe('making changes', () => {
  it('adds a text box where it is told to and selects it', async () => {
    const { link, session, state } = await opened()
    link.handlers.add_object = () => {
      link.push('objects', { type: 'objects', slide: 's1', changed: [text('o1')], removed: [], order: ['o1'] })
      return { object: 'o1', revision: 'main:1' }
    }
    expect(await session.addText({ x: 160, y: 120, w: 640, h: 140 })).toBe('o1')
    expect(link.last('add_object')).toEqual({ slide: 's1', kind: 'text', x: 160, y: 120, w: 640, h: 140, base: 'main:0' })
    expect(state.selected).toBe('o1')
    expect(link.last('lock').regions).toEqual([{ kind: 'objects', slide: 's1', ids: ['o1'] }])
  })
  it('adds a shape by the id of its outline', async () => {
    const { link, session } = await opened()
    await session.addShape('circle', { x: 10, y: 10, w: 240, h: 240 })
    expect(link.last('add_object')).toMatchObject({ kind: 'shape', shape: 'circle', w: 240, h: 240 })
  })
  it('imports a picture from disk and selects it (E10.8)', async () => {
    const { link, session, state } = await opened()
    link.handlers.add_image = () => {
      link.push('objects', { type: 'objects', slide: 's1', changed: [image('i1')], removed: [], order: ['i1'] })
      return { object: 'i1', revision: 'main:1' }
    }
    const id = await session.addImage(
      { data: 'AA==', alt: 'a chart', sourceName: 'chart.gif', sourcePath: null },
      { x: 0, y: 0, w: 400, h: 200 },
    )
    expect(id).toBe('i1')
    expect(link.last('add_image')).toEqual({
      slide: 's1',
      data: 'AA==',
      alt: 'a chart',
      source_name: 'chart.gif',
      source_path: null,
      x: 0,
      y: 0,
      w: 400,
      h: 200,
      base: 'main:0',
    })
    expect(state.selected).toBe('i1')
  })
  it('does not select anything when importing a picture failed, and says why', async () => {
    const { link, session, state } = await opened()
    link.handlers.add_image = () => {
      throw new ProtocolError('command_error', 'not a supported image')
    }
    const id = await session.addImage({ data: 'not base64', alt: 'x', sourceName: 'x.bin', sourcePath: null }, { x: 0, y: 0, w: 10, h: 10 })
    expect(id).toBeNull()
    expect(state.selected).toBeNull()
    expect(state.notice?.text).toContain('not a supported image')
  })
  it('does not select anything when adding failed, and says why', async () => {
    const { link, session, state } = await opened()
    link.handlers.add_object = () => {
      throw new ProtocolError('command_error', 'a slide holds at most 500 objects')
    }
    expect(await session.addText({ x: 0, y: 0, w: 100, h: 50 })).toBeNull()
    expect(state.selected).toBeNull()
    expect(state.notice?.text).toContain('500')
  })
  it('moves, resizes, edits and removes', async () => {
    const { link, session } = await opened([text('a')])
    expect(await session.move('a', 5, 6)).toBe(true)
    expect(link.last('move_object')).toEqual({ id: 'a', x: 5, y: 6, base: 'main:0' })
    await session.resize('a', { x: 1, y: 2, w: 300, h: 100 })
    expect(link.last('resize_object')).toEqual({ id: 'a', x: 1, y: 2, w: 300, h: 100, base: 'main:0' })
    await session.setText('a', 'Hello')
    expect(link.last('set_text')).toEqual({ id: 'a', text: 'Hello', base: 'main:0' })
    await session.remove('a')
    expect(link.last('remove_object')).toEqual({ id: 'a', base: 'main:0' })
  })
  it('a colleague holding the object refuses the change and the person is told', async () => {
    const { link, session, state } = await opened([text('a')])
    link.handlers.move_object = () => {
      throw new ProtocolError('locked', 'ben is working on that')
    }
    expect(await session.move('a', 1, 1)).toBe(false)
    expect(state.notice).toMatchObject({ kind: 'warning', text: 'ben is working on that' })
  })
  it('adds a slide and shows it', async () => {
    const { session, state } = await opened()
    expect(await session.addSlide()).toBe('s2')
    expect(state.activeSlide).toBe('s2')
  })
})

describe('selecting', () => {
  it('holds the selected object so that nobody else changes it, and lets go of it', async () => {
    const { link, session, state } = await opened([text('a'), text('b')])
    await session.select('a')
    expect(state.selected).toBe('a')
    expect(link.last('lock').regions).toEqual([{ kind: 'objects', slide: 's1', ids: ['a'] }])
    await session.select(null)
    expect(state.selected).toBeNull()
    expect(link.count('unlock')).toBe(1)
  })
  it('does not ask twice for the same object', async () => {
    const { link, session } = await opened([text('a')])
    await session.select('a')
    await session.select('a')
    expect(link.count('lock')).toBe(1)
  })
  it('does not keep a selection that a colleague holds', async () => {
    const { link, session, state } = await opened([text('a')])
    link.handlers.lock = () => {
      throw new ProtocolError('locked', 'ben is working on that')
    }
    await session.select('a')
    expect(state.selected).toBeNull()
    expect(state.notice?.text).toBe('ben is working on that')
  })
  it('only looks, for a viewer: the object is shown to the others without holding it', async () => {
    const link = new FakeLink()
    server(link, [text('a')])
    link.welcome = { ...WELCOME, role: 'viewer' }
    link.handlers.lock = () => {
      throw new ProtocolError('forbidden', 'lock needs the editor role')
    }
    const session = new SlideSession(() => link)
    await session.open()
    await session.select('a')
    expect(session.state.selected).toBe('a')
    expect(link.count('lock')).toBe(0)
    expect(link.last('presence').regions).toEqual([{ kind: 'objects', slide: 's1', ids: ['a'] }])
    expect(session.state.notice).toBeNull()
  })
  it('tells which objects colleagues have selected', async () => {
    const { link, session } = await opened([text('a'), text('b')])
    link.push('ephemeral', { kind: 'presence', sender: 'ben', data: { regions: [{ kind: 'objects', slide: 's1', ids: ['b'] }], locked: true } })
    expect(session.selectedByOthers('s1')).toEqual([{ id: 'b', user: 'ben', locked: true }])
    expect(session.selectedByOthers('s2')).toEqual([])
  })
  it('lets go of the selection when another slide is shown', async () => {
    const { link, session, state } = await opened([text('a')])
    link.handlers.slides = () => [{ id: 's1', objects: 1 }, { id: 's2', objects: 0 }]
    link.push('slides', { type: 'slides' })
    await session.settled()
    await session.select('a')
    await session.showSlide('s2')
    expect(state.activeSlide).toBe('s2')
    expect(state.selected).toBeNull()
    expect(link.count('unlock')).toBe(1)
  })
  it('stops showing where I am when nothing is selected', async () => {
    const { link, session } = await opened([text('a')])
    await session.select('a')
    await session.select(null)
    expect(link.last('presence').regions).toEqual([])
  })
})
