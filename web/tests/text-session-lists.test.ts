// Lists in a text (E9.21): what the session asks the server when a person makes, nests or leaves a list, and how it
// follows the events that say what the server did. The numbering itself is the server's; here it only arrives.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { STYLE_MODEL } from './style-model.fixture'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import type { Block } from '~/lib/blocks'
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

const SCHEMES = [
  { id: 'bullets', name: 'Bullets', kind: 'bullet', indent: 1.6, gap: 0.25 },
  { id: 'numbers', name: 'Numbers', kind: 'number', indent: 1.6, gap: 0.25 },
]
const plain = (id: string, text: string): Block => ({ id, style: 'body', text, runs: text ? [[text.length, 'ann', null]] : [] })
const item = (id: string, text: string, level = 0, marker = '1.'): Block => ({
  ...plain(id, text),
  item: { list: 'l1', level },
  label: { marker, path: [1] },
})

async function opened(blocks: Block[]) {
  const link = new FakeLink()
  const answer = { revision: 'main:9' }
  link.handlers = {
    blocks: () => ({
      revision: 'main:2',
      styles: [{ id: 'body', name: 'Body text', purpose: '', based_on: null, css: {}, computed: {}, to_name: false }],
      lists: [{ id: 'l1', scheme: 'numbers', start: 1, name: null }],
      schemes: SCHEMES,
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
    make_list: () => answer,
    indent_item: () => ({ ...answer, changed: 1 }),
    continue_list: () => answer,
    list_start: () => answer,
  }
  const session = new TextSession(() => link, { retryDelays: [0] })
  await session.open()
  return { link, session }
}

const at = (offset: number, block = 'b1') => ({ block, offset })

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('knowing the lists', () => {
  it('keeps the lists, the schemes and the items with their labels as the server sends them', async () => {
    const { session } = await opened([item('b1', 'one'), plain('b2', 'note')])
    expect(session.state.lists).toEqual([{ id: 'l1', scheme: 'numbers', start: 1, name: null }])
    expect(session.state.schemes.map((s) => s.id)).toEqual(['bullets', 'numbers'])
    expect(session.state.blocks[0]!.label).toEqual({ marker: '1.', path: [1] })
    expect(session.currentItem()).toEqual({ list: 'l1', level: 0 })
    session.setSelection(at(0, 'b2'))
    expect(session.currentItem()).toBeNull()
  })

  it('follows the events of items, labels and lists', async () => {
    const { session, link } = await opened([plain('b1', 'one'), plain('b2', 'two')])
    link.push('item', { type: 'item', block: 'b1', item: { list: 'l1', level: 0 } })
    link.push('labels', { type: 'labels', labels: { b1: { marker: '1.', path: [1] } } })
    link.push('lists', { type: 'lists', lists: [{ id: 'l1', scheme: 'numbers', start: 4, name: 'Steps' }] })
    expect(session.state.blocks[0]!.item).toEqual({ list: 'l1', level: 0 })
    expect(session.state.blocks[0]!.label?.marker).toBe('1.')
    expect(session.state.lists[0]).toMatchObject({ start: 4, name: 'Steps' })
  })

  it('an Enter in an item makes an item of the new paragraph at once, its number comes with the labels', async () => {
    const { session, link } = await opened([item('b1', 'one two')])
    link.push('split', { type: 'split', block: 'b1', offset: 3, new_id: 'b2', style: 'body' })
    expect(session.state.blocks[1]!.item).toEqual({ list: 'l1', level: 0 })
    expect(session.state.blocks[1]!.label).toBeUndefined()
    link.push('labels', { type: 'labels', labels: { b2: { marker: '2.', path: [2] } } })
    expect(session.state.blocks[1]!.label?.marker).toBe('2.')
  })
})

describe('making lists', () => {
  it('asks for bullets or numbers for the paragraphs of the selection, and for none', async () => {
    const { session, link } = await opened([plain('b1', 'one'), plain('b2', 'two'), plain('b3', 'three')])
    session.setSelection(at(1), at(2, 'b2'))
    await session.makeList('bullets')
    await session.makeList(null)
    expect(link.sent('make_list')).toEqual([
      { blocks: ['b1', 'b2'], scheme: 'bullets', base: 'main:2' },
      { blocks: ['b1', 'b2'], scheme: null, base: 'main:2' },
    ])
  })

  it('does nothing in a document one can only look at', async () => {
    const { session, link } = await opened([plain('b1', 'one')])
    session.state.me.role = 'viewer'
    await session.makeList('numbers')
    await session.indent(1)
    expect(link.sent('make_list')).toHaveLength(0)
    expect(link.sent('indent_item')).toHaveLength(0)
    expect(session.state.notice?.kind).toBe('warning')
  })

  it('continues a list and starts one at a number', async () => {
    const { session, link } = await opened([item('b1', 'one'), plain('b2', 'x'), item('b3', 'three')])
    session.setSelection(at(0, 'b3'))
    await session.continueList()
    await session.startAt(5)
    expect(link.sent('continue_list')).toEqual([{ block: 'b3', base: 'main:2' }])
    expect(link.sent('list_start')).toEqual([{ list: 'l1', start: 5, base: 'main:2' }])
  })

  it('startAt and continue need the caret in an item', async () => {
    const { session, link } = await opened([plain('b1', 'one')])
    expect(await session.continueList()).toBe(false)
    expect(await session.startAt(3)).toBe(false)
    expect(link.sent('continue_list')).toHaveLength(0)
    expect(link.sent('list_start')).toHaveLength(0)
  })
})

describe('the keys', () => {
  it('Tab indents an item and Shift+Tab outdents it; in a plain paragraph they are left to the browser', async () => {
    const { session, link } = await opened([item('b1', 'one'), item('b2', 'two', 0, '2.'), plain('b3', 'x')])
    session.setSelection(at(0, 'b2'))
    expect(session.tab(false)).toBe(true)
    expect(session.tab(true)).toBe(true)
    await session.settled()
    expect(link.sent('indent_item')).toEqual([
      { blocks: ['b2'], by: 1, base: 'main:2' },
      { blocks: ['b2'], by: -1, base: 'main:2' },
    ])
    session.setSelection(at(0, 'b3'))
    expect(session.tab(false)).toBe(false)
  })

  it('Enter in an item with words is an ordinary line break: the server makes the new item', async () => {
    const { session, link } = await opened([item('b1', 'one')])
    session.setSelection(at(3))
    await session.newline()
    expect(link.sent('replace_text')[0]).toMatchObject({ text: '\n' })
    expect(link.sent('make_list')).toHaveLength(0)
  })

  it('Enter in an empty item goes out one level, and out of the list at the first level', async () => {
    const { session, link } = await opened([item('b1', 'one'), item('b2', '', 1, 'a.'), item('b3', '', 0, '2.')])
    session.setSelection(at(0, 'b2'))
    await session.newline()
    session.setSelection(at(0, 'b3'))
    await session.newline()
    expect(link.sent('indent_item')).toEqual([{ blocks: ['b2'], by: -1, base: 'main:2' }])
    expect(link.sent('make_list')).toEqual([{ blocks: ['b3'], scheme: null, base: 'main:2' }])
    expect(link.sent('replace_text')).toHaveLength(0)
  })

  it('Enter with a selection inside an item replaces the selection as always', async () => {
    const { session, link } = await opened([item('b1', 'one two')])
    session.setSelection(at(1), at(4))
    await session.newline()
    expect(link.sent('replace_text')[0]).toMatchObject({ start: 1, end: 4, text: '\n' })
  })

  it('Backspace at the start of an item goes out a level, then out of the list, and only then joins', async () => {
    const { session, link } = await opened([plain('b0', 'before'), item('b1', 'one', 1, 'a.'), item('b2', 'two', 0, '1.')])
    session.setSelection(at(0, 'b1'))
    session.deleteBackward()
    await session.settled()
    session.setSelection(at(0, 'b2'))
    session.deleteBackward()
    await session.settled()
    expect(link.sent('indent_item')).toEqual([{ blocks: ['b1'], by: -1, base: 'main:2' }])
    expect(link.sent('make_list')).toEqual([{ blocks: ['b2'], scheme: null, base: 'main:2' }])
    expect(link.sent('replace_text')).toHaveLength(0)
    // a plain paragraph joins as ever
    session.state.blocks[2]!.item = null
    session.deleteBackward()
    await session.settled()
    expect(link.sent('replace_text')).toHaveLength(1)
  })

  it('Backspace inside the words of an item is a plain deletion', async () => {
    const { session, link } = await opened([item('b1', 'one')])
    session.setSelection(at(2))
    session.deleteBackward()
    await session.flush()
    expect(link.sent('replace_text')[0]).toMatchObject({ start: 1, end: 2, text: '' })
    expect(link.sent('make_list')).toHaveLength(0)
  })
})

describe('what the menu may offer', () => {
  const second = (id: string, list: string, scheme: string): [Block, { id: string; scheme: string; start: number; name: null }] => [
    { ...item(id, id), item: { list, level: 0 } },
    { id: list, scheme, start: 1, name: null },
  ]

  it('continuing is for the first item of a list when an earlier list of its kind exists', async () => {
    const { session } = await opened([item('b1', 'one'), plain('b2', 'note'), { ...item('b3', 'three'), item: { list: 'l2', level: 0 } }, { ...item('b4', 'four'), item: { list: 'l2', level: 0 } }])
    session.state.lists.push({ id: 'l2', scheme: 'numbers', start: 1, name: null })
    session.setSelection(at(0, 'b3'))
    expect(session.canContinue()).toBe(true)
    session.setSelection(at(0, 'b4'))
    expect(session.canContinue()).toBe(false) // not the first item of its list
    session.setSelection(at(0, 'b1'))
    expect(session.canContinue()).toBe(false) // nothing before it
    session.setSelection(at(0, 'b2'))
    expect(session.canContinue()).toBe(false) // no item
  })

  it('an earlier list of another kind is nothing to continue', async () => {
    const [b2, bullets] = second('b2', 'l2', 'bullets')
    const { session } = await opened([item('b1', 'one'), b2])
    session.state.lists.push(bullets)
    session.setSelection(at(0, 'b2'))
    expect(session.canContinue()).toBe(false)
  })

  it('knows which kind of list the caret is in', async () => {
    const { session } = await opened([item('b1', 'one'), plain('b2', 'x')])
    expect(session.currentScheme()).toBe('numbers')
    session.setSelection(at(0, 'b2'))
    expect(session.currentScheme()).toBeNull()
  })
})
