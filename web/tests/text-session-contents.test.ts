// Tables of contents in a text (E9.31): what the session asks the server to put one in, change or take it away, how it
// follows the events that say what the server did, and how typing, Backspace and Delete treat a table: never as text.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { STYLE_MODEL } from './style-model.fixture'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import type { Block } from '~/lib/blocks'
import type { ContentsEntry, Toc } from '~/lib/contents'
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
  sent(method: string) {
    return this.calls.filter((c) => c.method === method).map((c) => c.params)
  }
}

const DEFAULT_TOC: Toc = { kind: 'toc', first: 1, last: 3, numbers: true, places: true, leader: 'dots' }
const plain = (id: string, text: string): Block => ({ id, style: 'body', text, runs: text ? [[text.length, 'ann', null]] : [] })
const entry = (target: string, text: string, number: string | null = null): ContentsEntry => ({ target, level: 1, number, text, style: 'contents-1', place: null })
const table = (id: string, entries: ContentsEntry[] = []): Block => ({ ...plain(id, ''), generated: { ...DEFAULT_TOC }, entries })

async function opened(blocks: Block[]) {
  const link = new FakeLink()
  const answer = { revision: 'main:9' }
  link.handlers = {
    blocks: () => ({
      revision: 'main:2',
      styles: [{ id: 'body', name: 'Body text', purpose: '', based_on: null, css: {}, computed: {}, to_name: false }],
      lists: [],
      schemes: [],
      blocks,
    }),
    suggestions: () => [],
    style_model: () => STYLE_MODEL,
    palette: () => ({ type: 'palette', roles: [], readings: [] }),
    log: () => [],
    chat_log: () => [],
    checkpoints: () => [],
    history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
    lines: () => [{ name: 'main', head: 'main:2', active: true, forked_from: null }],
    restore_policy: () => ({ policy: 'consensus' }),
    hold: () => ({}),
    look: () => ({}),
    unlock: () => ({}),
    replace_text: () => ({ ...answer, block: 'b1', offset: 0 }),
    insert_contents: () => ({ ...answer, block: 'toc' }),
    remove_contents: () => answer,
    set_contents: () => answer,
    insert_reference: () => answer,
    set_field: () => answer,
    reference_targets: () => [{ id: 'b1', kind: 'heading', level: 1, number: '1', text: 'Why', name: null }],
  }
  const session = new TextSession(() => link, { retryDelays: [0] })
  await session.open()
  return { link, session }
}

const at = (offset: number, block = 'b1') => ({ block, offset })


beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('knowing the tables of contents', () => {
  it('keeps a table’s options and entries as the server sends them, and follows its events', async () => {
    const { session, link } = await opened([plain('b1', 'Why'), table('toc', [entry('b1', 'Why', '1')]), plain('b2', 'How')])
    expect(session.state.blocks[1]!.entries?.map((e) => e.text)).toEqual(['Why'])
    link.push('generated', { type: 'generated', paragraph: 'toc', entries: [entry('b1', 'Why'), entry('b2', 'How')] })
    expect(session.state.blocks[1]!.entries?.map((e) => e.target)).toEqual(['b1', 'b2'])
    link.push('block_generated', { type: 'block_generated', block: 'toc', generated: null })
    expect(session.state.blocks[1]!.generated).toBeNull()
    expect(session.state.blocks[1]!.entries).toBeUndefined()
    link.push('block_generated', { type: 'block_generated', block: 'b2', generated: DEFAULT_TOC })
    await vi.runAllTimersAsync()
    expect(link.calls.filter((c) => c.method === 'blocks')).toHaveLength(2) // a paragraph with text cannot be one: reload
  })

  it('knows when the caret is on a table', async () => {
    const { session } = await opened([plain('b1', 'Why'), table('toc')])
    expect(session.currentContents()).toBeNull()
    session.setSelection(at(0, 'toc'))
    expect(session.currentContents()?.id).toBe('toc')
  })
})

describe('putting one in, changing and taking it away', () => {
  it('asks for a table after the caret’s paragraph and puts the caret on it', async () => {
    const { session, link } = await opened([plain('b1', 'Why')])
    session.setSelection(at(2))
    await session.insertContents()
    expect(link.sent('insert_contents')).toEqual([{ block: 'b1', base: 'main:2' }])
    expect(session.state.selection?.focus).toEqual(at(0, 'toc'))
  })

  it('sends other options and asks for a table to be taken away', async () => {
    const { session, link } = await opened([table('toc')])
    await session.setContents('toc', { ...DEFAULT_TOC, last: 2 })
    expect(link.sent('set_contents')).toEqual([{ paragraph: 'toc', options: { ...DEFAULT_TOC, last: 2 }, base: 'main:2' }])
    await session.removeContents('toc')
    expect(link.sent('remove_contents')).toEqual([{ block: 'toc', base: 'main:2' }])
  })
})

describe('a table is never text', () => {
  it('refuses typing and pasting on a table, with a word why', async () => {
    const { session, link } = await opened([table('toc')])
    session.setSelection(at(0, 'toc'))
    session.type('x')
    session.paste('words')
    await vi.runAllTimersAsync()
    expect(session.state.pending).toBeNull()
    expect(link.sent('replace_text')).toEqual([])
  })

  it('Backspace after a table selects it, a second Backspace takes it away', async () => {
    const { session, link } = await opened([table('toc'), plain('b1', 'Why')])
    session.setSelection(at(0))
    session.deleteBackward()
    await vi.runAllTimersAsync()
    expect(session.state.selection?.focus).toEqual(at(0, 'toc'))
    expect(link.sent('replace_text')).toEqual([])
    session.deleteBackward()
    await vi.runAllTimersAsync()
    expect(link.sent('remove_contents')).toEqual([{ block: 'toc', base: 'main:2' }])
  })

  it('Delete before a table selects it too', async () => {
    const { session, link } = await opened([plain('b1', 'Why'), table('toc')])
    session.setSelection(at(3))
    session.deleteForward()
    await vi.runAllTimersAsync()
    expect(session.state.selection?.focus).toEqual(at(0, 'toc'))
    expect(link.sent('replace_text')).toEqual([])
  })
})

describe('references (step H)', () => {
  const F = '\ufffc'
  const referring = (): Block => ({ ...plain('b2', `see ${F}`), fields: [{ kind: 'ref', target: 'b1', show: 'number' }], shown: [{ text: '1', state: 'ok' }] })

  it('lists the targets, puts a reference at the caret and puts the caret after it', async () => {
    const { session, link } = await opened([plain('b1', 'Why'), plain('b2', 'see ')])
    expect((await session.referenceTargets('why')).map((t) => t.id)).toEqual(['b1'])
    session.setSelection(at(4, 'b2'))
    await session.insertReference('b1', 'number')
    expect(link.sent('insert_reference')).toEqual([{ paragraph: 'b2', offset: 4, target: 'b1', show: 'number', base: 'main:2' }])
    expect(session.state.selection?.focus).toEqual(at(5, 'b2'))
  })

  it('finds the reference at a place, changes what it shows, and pastes no U+FFFC', async () => {
    const { session, link } = await opened([plain('b1', 'Why'), referring()])
    expect(session.referenceAt(at(4, 'b2'))).toMatchObject({ block: 'b2', index: 0, field: { target: 'b1' }, shown: { text: '1' } })
    expect(session.referenceAt(at(0, 'b2'))).toBeNull()
    await session.setFieldShow('b2', 0, 'text')
    expect(link.sent('set_field')).toEqual([{ paragraph: 'b2', index: 0, show: 'text', base: 'main:2' }])
    session.setSelection(at(0, 'b1'))
    session.paste(`a${F}b`)
    await vi.runAllTimersAsync()
    expect(link.sent('replace_text').at(-1)).toMatchObject({ text: 'ab' })
  })

  it('Backspace after a reference selects it first, so it is not lost by a slip', async () => {
    const { session, link } = await opened([plain('b1', 'Why'), referring()])
    session.setSelection(at(5, 'b2'))
    session.deleteBackward()
    await vi.runAllTimersAsync()
    expect(session.state.selection).toEqual({ anchor: at(4, 'b2'), focus: at(5, 'b2') })
    expect(link.sent('replace_text')).toEqual([])
  })
})
