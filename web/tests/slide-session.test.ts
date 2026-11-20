import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { STYLE_MODEL } from './style-model.fixture'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { SlideSession } from '~/lib/slide-session'
import { POINT_MS } from '~/lib/base-session'

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
  lines: [{ name: 'main', head: 'main:0', active: true, forked_from: null }],
  proposal: null,
  returned: null,
}

const RECT = { format: 1, id: 'rectangle', name: 'Rectangle', path: 'M0 0 L100 0 L100 100 L0 100 Z', aspect: null, text_area: { x: 0, y: 0, w: 100, h: 100 } }
const CIRCLE = { format: 1, id: 'circle', name: 'Circle', path: 'M50 0 A50 50 0 1 1 50 100 A50 50 0 1 1 50 0 Z', aspect: 1, text_area: { x: 15, y: 15, w: 70, h: 70 } }
// A style names the palette's roles in `css`/`computed` and carries the colours in `resolved`, which is what the
// page is drawn from (D200).
const BODY = { id: 'body-text', name: 'Body text', purpose: 'Running text', based_on: null, to_name: false, kind: 'paragraph', css: { color: '@text' }, computed: { color: '@text' }, resolved: { color: '#1f1a33' } }
const SHAPE_STYLE = { id: 'plain-shape', name: 'Plain shape', purpose: 'A shape', based_on: null, to_name: false, kind: 'outline', css: { fill: '@accent/14' }, computed: { color: '@text', fill: '@accent/14' }, resolved: { color: '#1f1a33', fill: 'rgba(91, 75, 196, 0.14)' } }
const PALETTE = {
  type: 'palette',
  roles: [
    { id: 'text', name: 'Text', purpose: 'the words you read', colour: '#1F1A33' },
    { id: 'accent', name: 'Accent', purpose: 'the one thing to notice', colour: '#5B4BC4' },
  ],
  readings: [{ foreground: 'text', background: 'page', ratio: 15.14, floor: 4.5, ok: true, words: true }],
}

// An object as the server sends it (E10.16, D177): the shared body's fields flat, the anchor nested — the same
// shape in all three apps, only `anchor` differing.
const paragraph = (id: string, words = '') => ({
  id,
  style: 'body-text',
  text: words,
  runs: words ? [[words.length, 'ana', null]] : [],
})

const text = (id: string, extra: object = {}) => ({
  id,
  kind: 'text',
  w: 400,
  h: 120,
  style: 'body-text',
  paragraph: paragraph(id),
  ref: null,
  imported: null,
  rotation: 0,
  snap: true,
  anchor: { kind: 'slide', container: 's1', x: 100, y: 100 },
  ...extra,
})
const ASSET = { id: 'a'.repeat(64), format: 'gif', width: 20, height: 10, animated: false, data: 'AA==', first_frame: null }
const IMPORT = { asset: ASSET.id, alt: 'a chart', imported_by: 'ann', imported_at: '2026-11-07T10:00:00.000Z', source: 'disk', source_name: 'chart.gif', source_path: '/Users/ann/chart.gif' }
const image = (id: string, extra: object = {}) => ({
  id,
  kind: 'image',
  w: 400,
  h: 200,
  style: 'plain-image',
  paragraph: null,
  ref: ASSET.id,
  imported: IMPORT,
  rotation: 0,
  snap: true,
  anchor: { kind: 'slide', container: 's1', x: 0, y: 0 },
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
    style_model: () => STYLE_MODEL,
    palette: () => PALETTE,
    log: () => [],
    chat_log: () => [],
    checkpoints: () => [],
    history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
    lines: () => [{ name: 'main', head: 'main:0', active: true, forked_from: null }],
    restore_policy: () => ({ policy: 'consensus' }),
    ping: () => ({ revision: 'main:3', line: 'main' }),
    add_object: () => ({ object: 'o1', revision: 'main:1' }),
    add_image: () => ({ object: 'o1', revision: 'main:1' }),
    move_object: () => ({ revision: 'main:2' }),
    resize_object: () => ({ revision: 'main:2' }),
    write_words: () => ({ revision: 'main:2' }),
    set_snap: () => ({ revision: 'main:2' }),
    describe_object: () => ({ revision: 'main:2' }),
    rotate_object: () => ({ revision: 'main:2' }),
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
    const { state, session } = await opened([text('t1', { paragraph: paragraph('t1', 'Hello') })])
    expect(state.status).toBe('open')
    expect(state.slides).toEqual([{ id: 's1', objects: 1 }])
    expect(state.activeSlide).toBe('s1')
    expect(session.objectsOn('s1').map((o) => o.id)).toEqual(['t1'])
    expect(state.library.map((s) => s.id)).toEqual(['circle', 'rectangle'])
    expect(state.styles['body-text']!.css.color).toBe('@text')
    expect(state.styles['body-text']!.resolved.color).toBe('#1f1a33')
    expect(state.palette!.roles.map((r) => r.id)).toEqual(['text', 'accent'])
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
    expect(o.ref).toBe(ASSET.id)
    expect(o.imported).toEqual(IMPORT)
  })
})

describe('what the server tells', () => {
  it('adds and changes objects, in the stacking order it sends', async () => {
    const { link, session, state } = await opened([text('a'), text('b')])
    link.push('objects', { type: 'objects', container: 's1', changed: [text('c')], removed: [], order: ['a', 'b', 'c'] })
    expect(session.objectsOn('s1').map((o) => o.id)).toEqual(['a', 'b', 'c'])
    link.push('objects', { type: 'objects', container: 's1', changed: [text('a', { anchor: { kind: 'slide', container: 's1', x: 7, y: 100 } })], removed: [], order: ['a', 'b', 'c'] })
    expect(session.objectsOn('s1')[0]!.anchor.x).toBe(7)
    expect(state.slides[0]!.objects).toBe(3)
  })
  it('takes objects away', async () => {
    const { link, session, state } = await opened([text('a'), text('b')])
    link.push('objects', { type: 'objects', container: 's1', changed: [], removed: ['a'], order: ['b'] })
    expect(session.objectsOn('s1').map((o) => o.id)).toEqual(['b'])
    expect(state.objects.a).toBeUndefined()
    expect(state.slides[0]!.objects).toBe(1)
  })
  it('follows a style change, so a palette role reaches the slide without reopening it', async () => {
    // Found by driving a real browser: the styles were requested once at open and never again, so a colleague's
    // style change — and `set_role`, which recolours every style that named the role — did nothing visible here.
    const { link, state } = await opened([text('a')])
    const recoloured = { ...SHAPE_STYLE, resolved: { color: '#1f1a33', fill: 'rgba(0, 128, 128, 0.14)' } }
    link.push('styles', { type: 'styles', styles: [BODY, recoloured] })
    expect(state.styles['plain-shape']!.resolved.fill).toBe('rgba(0, 128, 128, 0.14)')
    expect(state.styles['plain-shape']!.computed.fill).toBe('@accent/14')
  })
  it('keeps the palette the server sends, roles and readings alike', async () => {
    const { link, state } = await opened()
    link.push('palette', { type: 'palette', roles: [{ id: 'accent', name: 'Accent', purpose: '', colour: '#008080' }], readings: [] })
    expect(state.palette!.roles[0]!.colour).toBe('#008080')
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
    link.push('objects', { type: 'objects', container: 's1', changed: [], removed: ['a'], order: [] })
    expect(state.selected).toBeNull()
    await session.settled()
    expect(link.count('unlock')).toBe(1)
  })
})

describe('renaming a slide (D550)', () => {
  it('asks the server to rename the thing, against the revision it is looking at', async () => {
    const { link, session } = await opened()
    link.handlers.rename_thing = () => ({ revision: 'main:1' })
    expect(await session.renameThing('s1', 'Agenda')).toBe(true)
    expect(link.last('rename_thing')).toEqual({ id: 's1', name: 'Agenda', base: 'main:0' })
  })

  it('asks what the dialog shows about a thing, and gives name and description in one request (D1317)', async () => {
    const { link, session } = await opened()
    const details = { id: 't1', kind: 'text', name: 'Title', name_fixed: false, description: '', drawn: true, decorative: false }
    link.handlers.thing_details = () => details
    expect(await session.thingDetails('t1')).toEqual(details)
    expect(link.last('thing_details')).toEqual({ id: 't1' })
    link.handlers.name_and_describe = () => ({ revision: 'main:1', name: 'Headline', description: 'The title', decorative: false })
    expect(await session.nameAndDescribe({ id: 't1', name: 'Headline', description: 'The title', decorative: false })).toBe(true)
    expect(link.last('name_and_describe')).toEqual({ id: 't1', name: 'Headline', description: 'The title', decorative: false, base: 'main:0' })
  })
  it('asks which fonts the document lacks, and takes a server that cannot say as having nothing to report', async () => {
    const { link, session } = await opened()
    link.handlers.font_report = () => ({ checked: true, missing: [{ family: 'Calibri', stand_in: 'Carlito', closeness: 'same-widths' }] })
    expect((await session.fontReport()).missing.map((m) => m.family)).toEqual(['Calibri'])
    delete link.handlers.font_report
    expect(await session.fontReport()).toEqual({ checked: false, missing: [] })
  })
  it('says no, with the server\'s words, when it refuses a name', async () => {
    const { link, session } = await opened()
    link.handlers.name_and_describe = () => {
      throw new ProtocolError('command_error', 'somebody else has that name')
    }
    expect(await session.nameAndDescribe({ id: 't1', name: 'Title', description: '', decorative: false })).toBe(false)
    expect(session.state.notice?.text).toMatch(/somebody else/)
  })
  it('labels a slide by its name, or by its place while it has none', async () => {
    const { link, session } = await opened()
    expect(session.slideLabel('s1', 0)).toBe('Slide 1')
    link.handlers.slides = () => [{ id: 's1', objects: 0, name: 'Intro' }]
    link.push('thing_renamed', { type: 'thing_renamed', id: 's1', name: 'Agenda' })
    await session.settled()
    expect(session.slideLabel('s1', 0)).toBe('Agenda')
  })
})

describe('making changes', () => {
  it('adds a text box where it is told to and selects it', async () => {
    const { link, session, state } = await opened()
    link.handlers.add_object = () => {
      link.push('objects', { type: 'objects', container: 's1', changed: [text('o1')], removed: [], order: ['o1'] })
      return { object: 'o1', revision: 'main:1' }
    }
    expect(await session.addText({ x: 160, y: 120, w: 640, h: 140 })).toBe('o1')
    expect(link.last('add_object')).toEqual({ slide: 's1', kind: 'text', x: 160, y: 120, w: 640, h: 140, base: 'main:0' })
    expect(state.selected).toBe('o1')
    expect(link.last('lock').regions).toEqual([{ kind: 'objects', container: 's1', ids: ['o1'] }])
  })
  it('adds a shape by the id of its outline', async () => {
    const { link, session } = await opened()
    await session.addShape('circle', { x: 10, y: 10, w: 240, h: 240 })
    expect(link.last('add_object')).toMatchObject({ kind: 'shape', shape: 'circle', w: 240, h: 240 })
  })
  it('imports a picture from disk and selects it (E10.8)', async () => {
    const { link, session, state } = await opened()
    link.handlers.add_image = () => {
      link.push('objects', { type: 'objects', container: 's1', changed: [image('i1')], removed: [], order: ['i1'] })
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
  it('imports a decorative picture with the mark and no words (BITV 1.1.1)', async () => {
    const { link, session } = await opened()
    await session.addImage({ data: 'AA==', alt: '', sourceName: 'rule.gif', sourcePath: null, decorative: true }, { x: 0, y: 0, w: 400, h: 200 })
    expect(link.last('add_image')).toMatchObject({ alt: '', decorative: true })
  })
  it('asks the server to size a picture from a file, and only then (D1332)', async () => {
    const { link, session } = await opened()
    await session.addImage({ data: 'AA==', alt: 'a dot', sourceName: 'dot.png', sourcePath: null, fit: true }, { x: 0, y: 0, w: 20, h: 20 })
    expect(link.last('add_image')).toMatchObject({ fit: true })
    await session.addImage({ data: 'AA==', alt: 'a dot', sourceName: 'dot.png', sourcePath: null }, { x: 0, y: 0, w: 20, h: 20 })
    expect(link.last('add_image')).not.toHaveProperty('fit')
  })
  it('does not send the decorative mark for a picture that is described', async () => {
    const { link, session } = await opened()
    await session.addImage({ data: 'AA==', alt: 'a chart', sourceName: 'chart.gif', sourcePath: null }, { x: 0, y: 0, w: 400, h: 200 })
    expect(link.last('add_image')).not.toHaveProperty('decorative')
  })
  it('describes an object, trimmed, as its own step', async () => {
    const { link, session } = await opened([text('a')])
    expect(await session.describe('a', '  the greeting ', false)).toBe(true)
    expect(link.last('describe_object')).toEqual({ id: 'a', description: 'the greeting', decorative: false, base: 'main:0' })
  })
  it('marks an object as decoration and sends no words with it', async () => {
    const { link, session } = await opened([text('a')])
    await session.describe('a', 'typed before the tick', true)
    expect(link.last('describe_object')).toEqual({ id: 'a', description: '', decorative: true, base: 'main:0' })
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
    await session.writeWords('a', 'Hello')
    expect(link.last('write_words')).toEqual({ id: 'a', text: 'Hello', base: 'main:0' })
    await session.setSnap('a', false)
    expect(link.last('set_snap')).toEqual({ id: 'a', snap: false, base: 'main:0' })
    await session.remove('a')
    expect(link.last('remove_object')).toEqual({ id: 'a', base: 'main:0' })
  })
  it('turns an object by sending the whole-degree turn, and is told when the server says no', async () => {
    const { link, session, state } = await opened([text('a')])
    expect(await session.rotate('a', 30)).toBe(true)
    expect(link.last('rotate_object')).toEqual({ id: 'a', rotation: 30, base: 'main:0' })
    link.handlers.rotate_object = () => {
      throw new ProtocolError('command_error', 'this object is too large to turn that way')
    }
    expect(await session.rotate('a', 45)).toBe(false)
    expect(state.notice).toMatchObject({ kind: 'error', text: 'this object is too large to turn that way' })
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
    expect(link.last('lock').regions).toEqual([{ kind: 'objects', container: 's1', ids: ['a'] }])
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
    expect(link.last('presence').regions).toEqual([{ kind: 'objects', container: 's1', ids: ['a'] }])
    expect(session.state.notice).toBeNull()
  })
  it('tells which objects colleagues have selected', async () => {
    const { link, session } = await opened([text('a'), text('b')])
    link.push('ephemeral', { kind: 'presence', sender: 'ben', data: { regions: [{ kind: 'objects', container: 's1', ids: ['b'] }], locked: true } })
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


describe('speaker notes and planned times (D342, D343)', () => {
  async function planned() {
    const link = new FakeLink()
    server(link)
    link.handlers.slides = () => [
      { id: 's1', objects: 0, seconds: 120, has_notes: true },
      { id: 's2', objects: 0, seconds: null, has_notes: false },
      { id: 's3', objects: 0, seconds: 30, has_notes: false },
    ]
    link.handlers.slide = ({ slide }) => ({
      revision: 'main:0',
      slide,
      objects: [],
      notes: slide === 's1' ? 'Open with **the story**' : '',
      seconds: { s1: 120, s2: null, s3: 30 }[slide as string],
    })
    link.handlers.set_slide_notes = () => ({ revision: 'main:3' })
    link.handlers.set_slide_time = () => ({ revision: 'main:4' })
    const session = new SlideSession(() => link, { retryDelays: [1] })
    await session.open()
    return { link, session, state: session.state }
  }

  it('loads the notes and the planned time of every slide', async () => {
    const { session } = await planned()
    expect(session.notesOf('s1')).toBe('Open with **the story**')
    expect(session.notesOf('s2')).toBe('')
    expect(session.secondsOf('s1')).toBe(120)
    expect(session.secondsOf('s2')).toBeNull()
  })
  it('adds up the planned times, and says how many slides have none', async () => {
    const { session } = await planned()
    expect(session.plan()).toEqual({ seconds: 150, planned: 2, unplanned: 1 })
  })
  it('follows a colleague who changes notes or a time', async () => {
    const { link, session } = await planned()
    link.push('slide_notes', { type: 'slide_notes', slide: 's2', notes: 'now there are some' })
    link.push('slide_time', { type: 'slide_time', slide: 's2', seconds: 45 })
    expect(session.notesOf('s2')).toBe('now there are some')
    expect(session.secondsOf('s2')).toBe(45)
    link.push('slide_notes', { type: 'slide_notes', slide: 's1', notes: '' })
    link.push('slide_time', { type: 'slide_time', slide: 's1', seconds: null })
    expect(session.notesOf('s1')).toBe('')
    expect(session.secondsOf('s1')).toBeNull()
    expect(session.plan()).toEqual({ seconds: 75, planned: 2, unplanned: 1 })
  })
  it('sends changed notes against the revision it knows', async () => {
    const { link, session } = await planned()
    expect(await session.setNotes('s2', 'Remember the demo')).toBe(true)
    expect(link.last('set_slide_notes')).toEqual({ slide: 's2', notes: 'Remember the demo', base: 'main:0' })
  })
  it('sends a planned time, and null to clear it', async () => {
    const { link, session } = await planned()
    expect(await session.setTime('s2', 90)).toBe(true)
    expect(link.last('set_slide_time')).toEqual({ slide: 's2', seconds: 90, base: 'main:0' })
    expect(await session.setTime('s1', null)).toBe(true)
    expect(link.last('set_slide_time')).toEqual({ slide: 's1', seconds: null, base: 'main:0' })
  })
  it('does not ask a viewer\'s server to change anything', async () => {
    const { link, session, state } = await planned()
    state.me.role = 'viewer'
    expect(await session.setNotes('s1', 'x')).toBe(false)
    expect(await session.setTime('s1', 5)).toBe(false)
    expect(link.count('set_slide_notes') + link.count('set_slide_time')).toBe(0)
  })
  it('copes with a server that does not know notes or times', async () => {
    const { session } = await opened()
    expect(session.notesOf('s1')).toBe('')
    expect(session.secondsOf('s1')).toBeNull()
    expect(session.plan()).toEqual({ seconds: 0, planned: 0, unplanned: 1 })
  })
})

describe('tags to things on slides (E5.20, D551)', () => {
  const named = (id: string, name: string, slide = 's1') => text(id, { name, anchor: { kind: 'slide', container: slide, x: 100, y: 100 } })

  it('offers the named things on the slide in sight, and the slide itself', async () => {
    const { link, session } = await opened([named('t1', 'Title'), text('t2')])
    link.handlers.slides = () => [{ id: 's1', objects: 2, name: 'Intro' }]
    await session.open()
    const offered = await session.taggableThings()
    expect(offered.map((t) => [t.name, t.kind])).toEqual([
      ['Intro', 'slide'],
      ['Title', 'text'],
    ])
    expect(await session.unnamedInView()).toBe(1)
  })
  it('takes a tag to a thing on another slide by showing that slide, and back', async () => {
    const link = new FakeLink()
    server(link, [named('t1', 'Title'), named('t9', 'Chart on two', 's2')])
    link.handlers.slides = () => [
      { id: 's1', objects: 1, name: 'One' },
      { id: 's2', objects: 1, name: 'Two' },
    ]
    link.handlers.slide = ({ slide }: any) => ({
      revision: 'main:0',
      slide,
      objects: slide === 's1' ? [named('t1', 'Title')] : [named('t9', 'Chart on two', 's2')],
    })
    const session = new SlideSession(() => link)
    await session.open()
    expect(session.state.activeSlide).toBe('s1')
    await session.goToThing('t9')
    expect(session.state.activeSlide).toBe('s2')
    expect(session.state.pointed).toEqual({ id: 't9', container: 's2' })
    expect(session.state.wayBack).toEqual({ container: 's1', anchor: null })
    session.goBack()
    expect(session.state.activeSlide).toBe('s1')
    expect(session.state.wayBack).toBeNull()
  })

  describe('the way back (D1312)', () => {
    const two = async () => {
      const link = new FakeLink()
      server(link, [named('t1', 'Title'), named('t9', 'Chart on two', 's2')])
      link.handlers.slides = () => [
        { id: 's1', objects: 1, name: 'One' },
        { id: 's2', objects: 1, name: 'Two' },
      ]
      link.handlers.slide = ({ slide }: any) => ({
        revision: 'main:0',
        slide,
        objects: slide === 's1' ? [named('t1', 'Title')] : [named('t9', 'Chart on two', 's2')],
      })
      const session = new SlideSession(() => link)
      await session.open()
      return session
    }
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    it('outlives the mark on the thing, and goes only when it is used', async () => {
      const session = await two()
      await session.goToThing('t9')
      vi.advanceTimersByTime(POINT_MS + 10)
      expect(session.state.pointed).toBeNull()
      expect(session.state.wayBack).toEqual({ container: 's1', anchor: null })
    })
    it('is kept even when the view does not move, with the place the view reports', async () => {
      const session = await two()
      session.setAnchorProvider(() => 'top-of-s1')
      await session.goToThing('t1')
      expect(session.state.wayBack).toEqual({ container: 's1', anchor: 'top-of-s1' })
    })
    it('is taken afresh by the next jump, so that it leads to where the person was last', async () => {
      const session = await two()
      await session.goToThing('t9')
      await session.goToThing('t1')
      expect(session.state.wayBack).toEqual({ container: 's2', anchor: null })
    })
    it('asks the view to scroll to the place it was, once, when used', async () => {
      const session = await two()
      session.setAnchorProvider(() => 'top-of-s1')
      await session.goToThing('t9')
      session.goBack()
      expect(session.state.scrollBack).toEqual({ anchor: 'top-of-s1', nonce: 1 })
      await session.goToThing('t9')
      session.goBack()
      expect(session.state.scrollBack?.nonce).toBe(2)
    })
    it('goes when the person starts to type or clicks into the text', async () => {
      const session = await two()
      await session.goToThing('t9')
      session.clearBack()
      expect(session.state.wayBack).toBeNull()
      expect(session.state.activeSlide).toBe('s2')
    })
    it('does nothing when there is no way back', async () => {
      const session = await two()
      session.goBack()
      expect(session.state.activeSlide).toBe('s1')
      expect(session.state.scrollBack).toBeNull()
    })
  })
  it('shows the name a thing has now, and knows a thing that is gone', async () => {
    const { link, session } = await opened([named('t1', 'Title')])
    link.handlers.slides = () => [{ id: 's1', objects: 1, name: 'Intro' }]
    await session.open()
    link.push('thing_renamed', { type: 'thing_renamed', id: 't1', name: 'Headline' })
    expect(session.nameOf('t1')).toBe('Headline')
    expect(session.isGone('t1')).toBe(false)
    expect(session.isGone('long-gone')).toBe(true)
  })
})

describe('lists in text boxes (E9.21, E9.22)', () => {
  const NUMBERS = { id: 'numbers', name: 'Numbers', kind: 'number', indent: 2, gap: 0.25, levels: [] }
  const item = (id: string, list: string, level = 0) => text(id, { paragraph: { ...paragraph(id, id), item: { list, level } } })
  async function listed(objects: any[]) {
    const link = new FakeLink()
    server(link, objects)
    link.handlers.lists = () => ({ lists: [{ id: 'l1', scheme: 'numbers', start: 1, name: null }, { id: 'l2', scheme: 'numbers', start: 1, name: null }], schemes: [NUMBERS], labels: { a: { marker: '1.', path: [1], number: '1' }, b: { marker: 'a.', path: [1, 1], number: '1.a' } } })
    for (const method of ['make_list', 'indent_item', 'continue_list', 'list_start', 'number_headings']) link.handlers[method] = () => ({ revision: 'main:3' })
    const session = new SlideSession(() => link, { retryDelays: [1] })
    await session.open()
    return { link, session, state: session.state }
  }

  it('loads the lists, the schemes and the markers, and draws a box’s marker moved in by its level', async () => {
    const { session } = await listed([item('a', 'l1'), item('b', 'l1', 1), text('c')])
    expect(session.markOf('a')).toEqual({ marker: '1.', indent: 0 })
    expect(session.markOf('b')).toEqual({ marker: 'a.', indent: 2 })
    expect(session.markOf('c')).toBeNull()
  })

  it('follows the labels the server tells, and takes one away when it says none', async () => {
    const { link, session } = await listed([item('a', 'l1'), text('t')])
    link.push('labels', { type: 'labels', labels: { a: null, t: { marker: '1', path: [1], number: '1' } } })
    expect(session.markOf('a')).toBeNull()
    expect(session.markOf('t')).toEqual({ marker: '1', indent: 0 }) // a numbered title is not moved in
  })

  it('asks for the selected box to be made an item, and may continue a list only from its first box', async () => {
    const { link, session, state } = await listed([item('a', 'l1'), item('b', 'l2'), text('c')])
    state.selected = 'c'
    expect(session.canList()).toBe(true)
    await session.makeList('numbers')
    expect(link.last('make_list')).toMatchObject({ blocks: ['c'], scheme: 'numbers' })
    state.selected = 'b'
    expect(session.canContinue()).toBe(true)
    state.selected = 'a'
    expect(session.canContinue()).toBe(false)
    await session.numberHeadings(true)
    expect(link.last('number_headings')).toMatchObject({ on: true })
  })
})

describe('agendas (E9.31)', () => {
  const TOC = { kind: 'toc', first: 1, last: 1, numbers: true, places: true, leader: 'dots' }
  const agenda = (id: string) => text(id, { paragraph: { ...paragraph(id), generated: TOC } })
  const line = (target: string, words: string, place: string) => ({ target, level: 1, number: null, text: words, style: 'slide-agenda', place })
  async function withAgenda(objects: any[]) {
    const link = new FakeLink()
    server(link, objects)
    link.handlers.contents = () => ({ revision: 'main:0', entries: { ag: [line('t1', 'Why', '1')] } })
    link.handlers.insert_agenda = () => ({ object: 'ag2', revision: 'main:1' })
    link.handlers.set_contents = () => ({ revision: 'main:2' })
    const session = new SlideSession(() => link, { retryDelays: [1] })
    await session.open()
    return { link, session, state: session.state }
  }

  it('loads the lines of every agenda, follows the server’s, and tells an agenda from a text box', async () => {
    const { link, session } = await withAgenda([agenda('ag'), text('t1')])
    expect(session.agendaOf('ag')?.map((e) => e.text)).toEqual(['Why'])
    expect(session.agendaOf('t1')).toBeNull()
    link.push('generated', { type: 'generated', paragraph: 'ag', entries: [line('t1', 'Why', '1'), line('t2', 'How', '2')] })
    expect(session.agendaOf('ag')?.map((e) => e.place)).toEqual(['1', '2'])
    link.push('generated', { type: 'generated', paragraph: 'ag', entries: null })
    expect(session.agendaOf('ag')).toEqual([])
  })

  it('puts an agenda on the slide shown and sends other options', async () => {
    const { link, session } = await withAgenda([agenda('ag')])
    await session.insertAgenda()
    expect(link.last('insert_agenda')).toMatchObject({ slide: 's1' })
    await session.setContents('ag', { ...TOC, numbers: false } as any)
    expect(link.last('set_contents')).toMatchObject({ paragraph: 'ag', options: { numbers: false } })
  })

  it('an older server without agendas shows none', async () => {
    const { session } = await opened([text('t1')])
    expect(session.state.agendas).toEqual({})
  })
})

describe('references in the words of text boxes (step H)', () => {
  async function referring() {
    const link = new FakeLink()
    const words = { ...paragraph('a', 'see ￼'), fields: [{ kind: 'ref', target: 't2', show: 'page' }] }
    server(link, [text('a', { paragraph: words }), text('t2')])
    link.handlers.fields = () => ({ revision: 'main:0', fields: { a: [{ text: '2', state: 'ok' }] } })
    link.handlers.reference_targets = () => [{ id: 't2', kind: 'heading', level: 1, number: null, text: 'Results', name: null }]
    link.handlers.insert_reference = () => ({ revision: 'main:1' })
    const session = new SlideSession(() => link, { retryDelays: [1] })
    await session.open()
    return { link, session, state: session.state }
  }

  it('loads and follows what the references read as, and finds the first one of a box', async () => {
    const { link, session, state } = await referring()
    expect(state.referenced.a).toEqual([{ text: '2', state: 'ok' }])
    expect(session.referenceIn('a')).toMatchObject({ field: { target: 't2' }, shown: { text: '2' } })
    expect(session.referenceIn('t2')).toBeNull()
    link.push('fields', { type: 'fields', paragraph: 'a', fields: [{ text: '3', state: 'ok' }] })
    expect(state.referenced.a).toEqual([{ text: '3', state: 'ok' }])
  })

  it('lists the targets and puts a reference into a box at an offset of its words', async () => {
    const { link, session } = await referring()
    expect((await session.referenceTargets()).map((t) => t.id)).toEqual(['t2'])
    await session.insertReference('a', 99, 't2', 'text')
    expect(link.last('insert_reference')).toMatchObject({ paragraph: 'a', offset: 5, target: 't2', show: 'text' })
  })
})
