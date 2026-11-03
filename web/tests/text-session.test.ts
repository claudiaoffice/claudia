import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { IDLE_FLUSH_MS, PLACE_MS, TextSession } from '~/lib/text-session'

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'essay',
  app: 'composes',
  line: 'main',
  revision: 'main:2',
  id: 1,
  color: '#e6194b',
  people: [{ id: 9, user: 'ai', color: '#5b4bc4' }],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
}

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  handlers: Record<string, (params: any) => any> = {}
  events: EventHandler[] = []
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
  onClose(_h: CloseHandler) {}
  close() {}
  push(name: string, data: any) {
    for (const h of this.events) h(name, data)
  }
  sent(method: string) {
    return this.calls.filter((c) => c.method === method).map((c) => c.params)
  }
}

const view = (id: string, name: string, css: Record<string, string>, based_on: string | null = null, to_name = false) => ({ id, name, purpose: '', based_on, css, computed: css, to_name })
const STYLES = [view('body', 'Body text', { 'font-size': '11pt', color: '#1F1A33' }), view('title', 'Title', { 'font-size': '26pt' }, 'body')]

/** A server that holds one paragraph and answers `replace_text` the way the real one does: events first, then the answer. */
function server(link: FakeLink, text = 'hello world') {
  const doc = { text }
  link.handlers = {
    blocks: () => ({ revision: 'main:2', styles: STYLES, blocks: [{ id: 'b1', style: 'body', text: doc.text, runs: doc.text ? [[[...doc.text].length, 'ann', null]] : [] }] }),
    suggestions: () => [],
    log: () => [],
    chat_log: () => [],
    checkpoints: () => [],
    history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
    hold: () => ({}),
    look: () => ({}),
    unlock: () => ({}),
    undo: () => ({ applied: true }),
    set_style: () => ({ revision: 'main:9' }),
    change_style: () => ({ revision: 'main:9' }),
    deviate_style: () => ({ style: 'body-changed', name: 'Body text (changed)', revision: 'main:9' }),
    rename_style: () => ({ revision: 'main:9' }),
    check_css: (p: any) => ({ css: {}, text: p.text, problems: [] }),
    accept_suggestion: () => ({ revision: 'main:9' }),
    reject_suggestion: () => ({ revision: 'main:9' }),
    replace_text: (p: any) => {
      const chars = [...doc.text]
      if (p.removed_by_test) return {}
      const removed = p.end - p.start
      if (removed) link.push('text', { type: 'text', block: 'b1', offset: p.start, removed, inserted: '', runs: [] })
      if (p.text) {
        link.push('text', { type: 'text', block: 'b1', offset: p.start, removed: 0, inserted: p.text, runs: [[[...p.text].length, 'ann', null]] })
      }
      chars.splice(p.start, removed, ...p.text)
      doc.text = chars.join('')
      return { revision: 'main:9', block: 'b1', offset: p.start + [...p.text].length }
    },
  }
  return doc
}

async function opened(text = 'hello world') {
  const link = new FakeLink()
  const doc = server(link, text)
  const session = new TextSession(() => link, { retryDelays: [0] })
  await session.open()
  return { link, session, doc }
}

const text = (session: TextSession) => session.state.blocks.map((b) => b.text)
const at = (offset: number, block = 'b1') => ({ block, offset })

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('opening', () => {
  it('loads the paragraphs, the styles and puts the caret at the start', async () => {
    const { session } = await opened()
    expect(text(session)).toEqual(['hello world'])
    expect(session.state.styles.map((s) => s.id)).toEqual(['body', 'title'])
    expect(session.state.selection).toEqual({ anchor: at(0), focus: at(0) })
    expect(session.state.status).toBe('open')
  })
})

describe('typing', () => {
  it('shows the characters at once and sends the word when it ends', async () => {
    const { session, link } = await opened('')
    for (const c of 'Hi') session.type(c)
    expect(session.state.pending?.text).toBe('Hi')
    expect(link.sent('replace_text')).toHaveLength(0)
    session.type(' ')
    await session.flush()
    expect(link.sent('replace_text')).toEqual([{ block: 'b1', start: 0, end_block: 'b1', end: 0, text: 'Hi ', base: 'main:2' }])
    expect(text(session)).toEqual(['Hi '])
    expect(session.state.pending).toBeNull()
    expect(session.state.sending).toBeNull()
    expect(session.state.selection?.focus).toEqual(at(3))
  })

  it('sends after a pause, too', async () => {
    const { session, link } = await opened('')
    session.type('a')
    await vi.advanceTimersByTimeAsync(IDLE_FLUSH_MS + 10)
    await session.settled()
    expect(link.sent('replace_text')).toHaveLength(1)
    expect(text(session)).toEqual(['a'])
  })

  it('keeps what is typed while a word is on its way, in order', async () => {
    const { session, link } = await opened('')
    for (const c of 'one ') session.type(c)
    for (const c of 'two ') session.type(c) // typed while the first request is out
    await session.flush()
    expect(link.sent('replace_text').map((p) => p.text)).toEqual(['one ', 'two '])
    expect(text(session)).toEqual(['one two '])
  })

  it('backspace takes back what has not been sent without asking the server', async () => {
    const { session, link } = await opened('')
    for (const c of 'abc') session.type(c)
    session.deleteBackward()
    expect(session.state.pending?.text).toBe('ab')
    session.deleteBackward(true)
    expect(session.state.pending).toBeNull()
    await session.flush()
    expect(link.sent('replace_text')).toHaveLength(0)
  })

  it('typing over a selection replaces it with the first character, the rest follows', async () => {
    const { session, link } = await opened('hello world')
    session.setSelection(at(0), at(5))
    session.type('J')
    session.type('o')
    await session.flush()
    expect(link.sent('replace_text')[0]).toMatchObject({ start: 0, end: 5, text: 'J' })
    expect(text(session)).toEqual(['Jo world'])
  })

  it('a viewer is told, not obeyed', async () => {
    const { session, link } = await opened()
    session.state.me.role = 'viewer'
    session.type('x')
    await session.flush()
    expect(session.state.pending).toBeNull()
    expect(link.sent('replace_text')).toHaveLength(0)
    expect(session.state.notice?.kind).toBe('warning')
  })
})

describe('editing', () => {
  it('Enter replaces the selection by a line break', async () => {
    const { session, link } = await opened('hello world')
    session.setSelection(at(5))
    await session.newline()
    expect(link.sent('replace_text')[0]).toMatchObject({ start: 5, end: 5, text: '\n' })
  })

  it('backspace deletes the character before the caret, ctrl+backspace the word', async () => {
    const { session, link } = await opened('hello world')
    session.setSelection(at(11))
    session.deleteBackward()
    await session.flush()
    expect(text(session)).toEqual(['hello worl'])
    session.deleteBackward(true)
    await session.flush()
    expect(text(session)).toEqual(['hello '])
    expect(link.sent('replace_text').map((p) => [p.start, p.end])).toEqual([[10, 11], [6, 10]])
  })

  it('delete at the end of a paragraph and backspace at its start join paragraphs', async () => {
    const { session, link } = await opened('ab')
    session.state.blocks.push({ id: 'b2', style: 'body', text: 'cd', runs: [[2, 'ann', null]] })
    session.setSelection({ block: 'b2', offset: 0 })
    session.deleteBackward()
    await session.flush()
    expect(link.sent('replace_text')[0]).toMatchObject({ block: 'b1', start: 2, end_block: 'b2', end: 0, text: '' })
  })

  it('counts characters like the server does, not like javascript', async () => {
    const { session, link } = await opened('a😀b')
    session.setSelection(at(3))
    session.deleteBackward() // the whole emoji
    await session.flush()
    expect(link.sent('replace_text')[0]).toMatchObject({ start: 1, end: 2 })
    expect(text(session)).toEqual(['ab'])
  })

  it('cut returns the selected text and takes it out', async () => {
    const { session } = await opened('hello world')
    session.setSelection(at(0), at(6))
    expect(session.cut()).toBe('hello ')
    await session.flush()
    expect(text(session)).toEqual(['world'])
  })

  it('paste puts text in, line breaks as they come', async () => {
    const { session, link } = await opened('')
    session.paste('a\r\nb')
    await session.flush()
    expect(link.sent('replace_text')[0].text).toBe('a\nb')
  })

  it('setting a style asks for every paragraph of the selection that has another one', async () => {
    const { session, link } = await opened('hello')
    await session.setStyle('title')
    expect(link.sent('set_style')).toEqual([{ block: 'b1', style: 'title', base: 'main:2' }])
    await session.setStyle('body') // b1 is still body in the replica (no event arrived in this fake)
    expect(link.sent('set_style')).toHaveLength(1)
  })
})

describe('following the others', () => {
  it('text typed before my caret moves it, and a colleague\'s zone moves too', async () => {
    const { session, link } = await opened('hello world')
    link.push('ephemeral', { kind: 'presence', sender: 'ben', data: { regions: [{ kind: 'text', block: 'b1', start: 6, end: 11 }, { kind: 'text', block: 'b1', start: 8, end: 8 }], locked: true } })
    session.setSelection(at(6))
    link.push('text', { type: 'text', block: 'b1', offset: 0, removed: 0, inserted: 'Oh, ', runs: [[4, 'ben', null]] })
    expect(text(session)).toEqual(['Oh, hello world'])
    expect(session.state.selection?.focus).toEqual(at(10))
    expect(session.state.presence.ben!.regions[0]).toMatchObject({ start: 10, end: 15 })
  })

  it('my unsent words stay where I typed them', async () => {
    const { session, link } = await opened('ab')
    session.setSelection(at(2))
    session.type('x')
    link.push('text', { type: 'text', block: 'b1', offset: 0, removed: 0, inserted: '>>', runs: [[2, 'ben', null]] })
    expect(session.state.pending).toMatchObject({ at: at(4), text: 'x' })
  })

  it('a split and a join move the caret between paragraphs', async () => {
    const { session, link } = await opened('hello world')
    session.setSelection(at(8))
    link.push('split', { type: 'split', block: 'b1', offset: 5, new_id: 'b2', style: 'body' })
    expect(text(session)).toEqual(['hello', ' world'])
    expect(session.state.selection?.focus).toEqual({ block: 'b2', offset: 3 })
    link.push('join', { type: 'join', block: 'b2', into: 'b1', at: 5 })
    expect(session.state.selection?.focus).toEqual(at(8))
  })

  it('reloads when an event does not fit', async () => {
    const { session, link } = await opened('hello')
    link.push('text', { type: 'text', block: 'b7', offset: 0, removed: 0, inserted: 'x', runs: [[1, 'ben', null]] })
    await session.settled()
    expect(link.calls.filter((c) => c.method === 'blocks')).toHaveLength(2)
  })

  it('knows the suggestions and drops them when they are over', async () => {
    const { session, link } = await opened('the quick fox')
    const item = { id: 's1', author: 'ai', block: 'b1', start: 4, end: 9, original: 'quick', replacement: 'fast', reason: 'shorter', state: 'open', outdated: false }
    link.push('suggestions', { type: 'suggestions', items: [item] })
    expect(session.state.suggestions).toHaveLength(1)
    link.push('suggestions', { type: 'suggestions', items: [{ ...item, start: 6, end: 11, outdated: true }] })
    expect(session.state.suggestions[0]).toMatchObject({ start: 6, outdated: true })
    link.push('suggestions', { type: 'suggestions', items: [{ ...item, state: 'accepted' }] })
    expect(session.state.suggestions).toEqual([])
  })

  it('accepts and rejects through the server', async () => {
    const { session, link } = await opened()
    await session.accept('s1')
    await session.reject('s2')
    expect(link.sent('accept_suggestion')).toEqual([{ id: 's1', base: 'main:2' }])
    expect(link.sent('reject_suggestion')).toEqual([{ id: 's2', base: 'main:2' }])
  })
})

describe('showing where I am', () => {
  it('holds the zone around the caret, a little after it moved', async () => {
    const { session, link } = await opened('hello world')
    session.setSelection(at(3))
    session.setSelection(at(4))
    await vi.advanceTimersByTimeAsync(PLACE_MS + 10)
    await session.settled()
    expect(link.sent('hold')).toEqual([{ block: 'b1', offset: 4, words: 3 }])
  })

  it('looks only, when a colleague holds the place', async () => {
    const { session, link } = await opened('hello world')
    link.handlers.hold = () => {
      throw new ProtocolError('locked', 'ben is writing here')
    }
    session.setSelection(at(3))
    await vi.advanceTimersByTimeAsync(PLACE_MS + 10)
    await session.settled()
    expect(link.sent('look')).toEqual([{ block: 'b1', offset: 3, words: 3 }])
  })

  it('viewers look instead of holding', async () => {
    const { session, link } = await opened('hello world')
    session.state.me.role = 'viewer'
    session.setSelection(at(3))
    await vi.advanceTimersByTimeAsync(PLACE_MS + 10)
    await session.settled()
    expect(link.sent('hold')).toHaveLength(0)
    expect(link.sent('look')).toHaveLength(1)
  })

  it('translates a colleague\'s zone from code points to the units it displays', async () => {
    const { session, link } = await opened('😀 hi')
    link.push('ephemeral', { kind: 'presence', sender: 'ben', data: { regions: [{ kind: 'text', block: 'b1', start: 2, end: 4 }], locked: false } })
    expect(session.state.presence.ben!.regions[0]).toMatchObject({ start: 3, end: 5 })
  })
})

describe('undo', () => {
  it('waits for the words that were typed', async () => {
    const { session, link } = await opened('')
    session.type('a')
    expect(await session.undo()).toBe(true)
    expect(link.calls.map((c) => c.method).filter((m) => m === 'replace_text' || m === 'undo')).toEqual(['replace_text', 'undo'])
  })
})

describe('typing faster than the network', () => {
  it('loses nothing and keeps the order when words are typed while others are on their way', async () => {
    const { session, link } = await opened('')
    const fast = link.handlers.replace_text!
    link.handlers.replace_text = (p: any) => new Promise((resolve) => setTimeout(() => resolve(fast(p)), 40))
    for (const c of 'Why we write together') session.type(c)
    await vi.advanceTimersByTimeAsync(2000)
    await session.flush()
    expect(text(session)).toEqual(['Why we write together'])
    expect(link.sent('replace_text').map((p) => p.text).join('')).toBe('Why we write together')
  })

  it('keeps Enter behind the words typed before it', async () => {
    const { session, link, doc } = await opened('')
    const fast = link.handlers.replace_text!
    link.handlers.replace_text = (p: any) => new Promise((resolve) => setTimeout(() => resolve(fast(p)), 40))
    void doc
    for (const c of 'one two') session.type(c)
    void session.newline()
    for (const c of 'three') session.type(c)
    await vi.advanceTimersByTimeAsync(3000)
    await session.flush()
    expect(link.sent('replace_text').map((p) => p.text)).toEqual(['one ', 'two', '\n', 'three'])
  })
})


describe('styles', () => {
  it('keeps the styles as the server sends them, and takes the whole book from a styles event', async () => {
    const { link, session } = await opened()
    expect(session.styleView('title')?.based_on).toBe('body')
    link.push('styles', { type: 'styles', styles: [...STYLES, view('note', 'Note', { color: 'red' }, 'body')] })
    expect(session.state.styles.map((s) => s.id)).toEqual(['body', 'title', 'note'])
  })

  it('counts how many paragraphs use each style', async () => {
    const { session } = await opened()
    session.state.blocks.push({ id: 'b2', style: 'title', text: 'x', runs: [[1, 'ann', null]] })
    expect(session.uses()).toEqual({ body: 1, title: 1 })
  })

  it('changing a style sends the properties to set and to remove, after what was typed', async () => {
    const { link, session } = await opened('')
    session.type('hi')
    await session.changeStyle('body', { set: { color: 'red' }, unset: ['font-size'] })
    expect(link.calls.map((c) => c.method).filter((m) => m === 'replace_text' || m === 'change_style')).toEqual(['replace_text', 'change_style'])
    expect(link.sent('change_style')).toEqual([{ style: 'body', set: { color: 'red' }, unset: ['font-size'], base: 'main:2' }])
  })

  it('changing a style with the text of its CSS sends the text', async () => {
    const { link, session } = await opened()
    await session.changeStyle('body', { text: 'color: red;' })
    expect(link.sent('change_style')).toEqual([{ style: 'body', text: 'color: red;', base: 'main:2' }])
  })

  it('deviating asks once per style among the selected paragraphs, and puts the caret in the new style by the event', async () => {
    const { link, session } = await opened()
    session.state.blocks.push({ id: 'b2', style: 'title', text: 'x', runs: [[1, 'ann', null]] }, { id: 'b3', style: 'body', text: 'y', runs: [[1, 'ann', null]] })
    session.setSelection(at(0, 'b1'), at(1, 'b3'))
    await session.deviateStyle({ set: { 'font-weight': 'bold' } })
    expect(link.sent('deviate_style')).toEqual([
      { parent: 'body', blocks: ['b1', 'b3'], set: { 'font-weight': 'bold' }, base: 'main:2' },
      { parent: 'title', blocks: ['b2'], set: { 'font-weight': 'bold' }, base: 'main:2' },
    ])
  })

  it('renaming a style asks the server', async () => {
    const { link, session } = await opened()
    expect(await session.renameStyle('body-changed', 'Accent')).toBe(true)
    expect(link.sent('rename_style')).toEqual([{ style: 'body-changed', name: 'Accent', base: 'main:2' }])
  })

  it('checking CSS is a read that does not wait for the queue', async () => {
    const { link, session } = await opened()
    link.handlers.check_css = () => ({ css: { color: 'red' }, text: 'color: red;', problems: [] })
    expect(await session.checkCss('color: red')).toEqual({ css: { color: 'red' }, text: 'color: red;', problems: [] })
    expect(link.sent('check_css')).toEqual([{ text: 'color: red' }])
  })

  it('a refused change tells the person why and answers false', async () => {
    const { link, session } = await opened()
    link.handlers.change_style = () => {
      throw new ProtocolError('command_error', 'color: “nope” is not a colour')
    }
    expect(await session.changeStyle('body', { set: { color: 'nope' } })).toBe(false)
    expect(session.state.notice?.text).toContain('not a colour')
  })

  it('does nothing in a document one can only look at', async () => {
    const { link, session } = await opened()
    session.state.me.role = 'viewer'
    expect(await session.changeStyle('body', { set: { color: 'red' } })).toBe(false)
    expect(link.sent('change_style')).toEqual([])
  })
})
