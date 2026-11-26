import { describe, expect, it } from 'vitest'
import { STYLE_MODEL } from './style-model.fixture'
import { ProtocolError, type Welcome } from '~/lib/protocol'
import { SlideSession } from '~/lib/slide-session'
import { FakeServer } from './support/fake-server'

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'talk',
  app: 'creates',
  branch: 'main',
  revision: 'main:0',
  id: 1,
  color: '#e6194b',
  people: [],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
  branches: [{ name: 'main', head: 'main:0', active: true, forked_from: null }],
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

function server(link: FakeServer, objects: any[] = []) {
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
    branches: () => [{ name: 'main', head: 'main:0', active: true, forked_from: null }],
    restore_policy: () => ({ policy: 'consensus' }),
    add_object: () => ({ object: 'o1', revision: 'main:1' }),
    add_image: () => ({ object: 'o1', revision: 'main:1' }),
    move_object: () => ({ revision: 'main:2' }),
    resize_object: () => ({ revision: 'main:2' }),
    set_text: () => ({ revision: 'main:2' }),
    set_snap: () => ({ revision: 'main:2' }),
    describe_object: () => ({ revision: 'main:2' }),
    remove_object: () => ({ revision: 'main:2' }),
    add_slide: () => ({ slide: 's2', revision: 'main:2' }),
    lock: () => ({}),
    unlock: () => ({}),
    presence: () => ({}),
  }
}

async function opened(objects: any[] = []) {
  const link = new FakeServer('creates', { welcome: WELCOME })
  server(link, objects)
  const session = new SlideSession(() => link, { retryDelays: [1] })
  await session.open()
  return { link, session, state: session.state }
}


const TYPES = { types: [{ type: 'latex', title: 'LaTeX', example: 'x^2', params: [] }, { type: 'mermaid', title: 'Mermaid', example: 'graph TD\n  A --> B', params: [] }] }
const DEF = { format: 1, id: 'r1', type: 'latex', source: 'x^2', params: {}, image: null, renderer: '' }

async function withContainers(defs: object[] = [DEF]) {
  const link = new FakeServer('creates', { welcome: WELCOME })
  server(link)
  link.handlers.container_types = () => TYPES
  link.handlers.containers = () => defs
  link.handlers.add_container = () => ({ object: 'o1', container: 'r9', revision: 'main:1' })
  link.handlers.set_container_source = () => ({ container: 'r1', revision: 'main:2' })
  const session = new SlideSession(() => link, { retryDelays: [1] })
  await session.open()
  return { link, session, state: session.state }
}

describe('containers in a session', () => {
  it('loads what can be made and what the document holds', async () => {
    const { state } = await withContainers()
    expect(state.containerTypes.map((t) => t.type)).toEqual(['latex', 'mermaid'])
    expect(state.containers.r1!.source).toBe('x^2')
  })
  it('opens as before with a server that knows nothing of containers', async () => {
    const { state } = await opened()
    expect(state.status).toBe('open')
    expect(state.containerTypes).toEqual([])
    expect(state.containers).toEqual({})
  })
  it('follows the server when a definition changes or goes', async () => {
    const { link, state } = await withContainers()
    link.push('container', { type: 'container', id: 'r1', definition: { ...DEF, source: 'y', image: 'img' } })
    expect(state.containers.r1).toMatchObject({ source: 'y', image: 'img' })
    link.push('container', { type: 'container', id: 'r2', definition: { ...DEF, id: 'r2' } })
    expect(Object.keys(state.containers).sort()).toEqual(['r1', 'r2'])
    link.push('container', { type: 'container', id: 'r1', definition: null })
    expect(state.containers.r1).toBeUndefined()
  })
  it('keeps what the server said of the last try, and forgets it when the text changes', async () => {
    const { link, state } = await withContainers()
    link.push('render_result', { id: 'r1', ok: false, diagnostics: [], message: 'bad', unavailable: null })
    expect(state.renderOutcomes.r1!.message).toBe('bad')
    link.push('container', { type: 'container', id: 'r1', definition: { ...DEF, source: 'fixed' } })
    expect(state.renderOutcomes.r1).toBeUndefined()
    link.push('render_result', { id: 'r1', ok: true, diagnostics: [], message: '', unavailable: null })
    link.push('container', { type: 'container', id: 'r1', definition: { ...DEF, source: 'fixed', image: 'i' } })
    expect(state.renderOutcomes.r1!.ok).toBe(true) // the picture of the same text: the word stays
  })
  it('puts a container where the person points, with the example as its first text', async () => {
    const { link, session } = await withContainers()
    expect(await session.addContainerAt('latex', { slide: 's1', x: 10, y: 20 })).toBe('o1')
    expect(link.last('add_container')).toMatchObject({ slide: 's1', x: 10, y: 20, type: 'latex', source: 'x^2', base: 'main:0' })
  })
  it('does not put one of a type the server does not make', async () => {
    const { link, session } = await withContainers()
    expect(await session.addContainerAt('typst', { slide: 's1', x: 0, y: 0 })).toBeNull()
    expect(link.count('add_container')).toBe(0)
  })
  it('changes the text of a container', async () => {
    const { link, session } = await withContainers()
    expect(await session.setContainerSource('r1', 'z')).toBe(true)
    expect(link.last('set_container_source')).toMatchObject({ id: 'r1', source: 'z' })
  })
  it('does not send a text that did not change', async () => {
    const { link, session } = await withContainers()
    expect(await session.setContainerSource('r1', 'x^2')).toBe(true)
    expect(link.count('set_container_source')).toBe(0)
  })
  it('says why a text was refused', async () => {
    const { link, session, state } = await withContainers()
    link.handlers.set_container_source = () => {
      throw new ProtocolError('command_error', 'too long')
    }
    expect(await session.setContainerSource('r1', 'z')).toBe(false)
    expect(state.notice?.text).toBe('too long')
  })
  it('puts a container on the slide that is shown, in the frame given, and selects it', async () => {
    const { link, session, state } = await withContainers()
    link.handlers.add_object = () => ({})
    expect(await session.addContainer('mermaid', { x: 100, y: 50, w: 320, h: 180 })).toBe('o1')
    expect(link.last('add_container')).toMatchObject({ slide: 's1', x: 100, y: 50, w: 320, h: 180, type: 'mermaid' })
    expect(state.selected).toBe('o1')
  })
  it('turns a text box that holds a fenced block into a container in the same place', async () => {
    const { link, session } = await withContainers()
    link.handlers.add_container = (p: any) => ({ object: 'o7', container: 'r7', revision: 'main:3', p })
    const box = { id: 't1', kind: 'text', w: 400, h: 120, anchor: { kind: 'slide', holder: 's1', x: 30, y: 40 } }
    ;(session.state.objects as any).t1 = box
    expect(await session.fenceToContainer('t1', '```latex\n\\frac{a}{b}\n```')).toBe('o7')
    expect(link.last('add_container')).toMatchObject({ slide: 's1', x: 30, y: 40, w: 400, h: 120, type: 'latex', source: '\\frac{a}{b}' })
    expect(link.last('remove_object')).toMatchObject({ id: 't1' })
  })
  it('leaves a text that is not a fence of a type the server makes alone', async () => {
    const { link, session } = await withContainers()
    ;(session.state.objects as any).t1 = { id: 't1', kind: 'text', w: 400, h: 120, anchor: { kind: 'slide', holder: 's1', x: 0, y: 0 } }
    expect(await session.fenceToContainer('t1', 'just words')).toBeNull()
    expect(await session.fenceToContainer('t1', '```typst\nx\n```')).toBeNull() // the server makes no typst here
    expect(link.count('add_container')).toBe(0)
  })
})
