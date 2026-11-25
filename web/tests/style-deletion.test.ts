import { describe, expect, it, vi } from 'vitest'
import { ProtocolError, type LinkLike, type EventHandler, type CloseHandler } from '~/lib/protocol'
import { TextSession } from '~/lib/text-session'
import { galleryFor } from '~/lib/style-host'
import { STYLE_MODEL } from './style-model.fixture'
import type { StyleView } from '~/lib/style-css'
import {
  DELETE_HOWS,
  DeletionChoice,
  accessKeyOf,
  actionForKey,
  basedOnLine,
  deletedLine,
  deletionHost,
  lookDifference,
  lookDifferentLine,
  lookLostLine,
  mnemonic,
  pickable,
  usedByLine,
  wasRefused,
  type StyleDeletion,
} from '~/lib/style-deletion'

const view = (id: string, name: string, over: Partial<StyleView> = {}): StyleView => ({
  id,
  name,
  purpose: '',
  based_on: 'body',
  css: {},
  computed: {},
  resolved: {},
  to_name: false,
  kind: 'paragraph',
  ...over,
})

const deletion = (over: Partial<StyleDeletion> = {}): StyleDeletion => ({
  style: 'quote',
  name: 'Quote',
  protected: false,
  hidden: false,
  uses: 14,
  children: [{ id: 'small', name: 'Small quote' }],
  suggested: { id: 'body', name: 'Body text' },
  targets: [
    { id: 'body', name: 'Body text', changes_look: true, holds: true, reason: null },
    { id: 'note', name: 'Note', changes_look: true, holds: true, reason: null },
    { id: 'callout', name: 'Callout', changes_look: true, holds: false, reason: 'it sets a colour that Quote does not' },
  ],
  ...over,
})

describe('the two ways, in the order the dialog offers them (D785)', () => {
  it('are assign and then re-base', () => {
    expect(DELETE_HOWS).toEqual(['assign', 'rebase'])
  })

  it('start on assigning, with the plain style of the kind chosen', () => {
    const choice = new DeletionChoice(deletion())
    expect(choice.how).toBe('assign')
    expect(choice.target('assign')?.id).toBe('body')
    expect(choice.target('rebase')).toBeUndefined()
    expect(choice.ready).toBe(true)
    expect(choice.request).toEqual({ how: 'assign', target: 'body' })
  })

  it('count what changes first: only assigning can change a look, and only when it does', () => {
    const choice = new DeletionChoice(deletion())
    expect(choice.looksChange).toBe(true)
    choice.pick('rebase', 'note')
    expect(choice.how).toBe('rebase')
    expect(choice.looksChange).toBe(false)
    const same = new DeletionChoice(deletion({ targets: [{ id: 'body', name: 'Body text', changes_look: false, holds: true, reason: null }] }))
    expect(same.looksChange).toBe(false)
  })

  it('want a style to re-base on, and take only one that keeps the look', () => {
    const choice = new DeletionChoice(deletion())
    choice.pick('rebase', null)
    expect(choice.ready).toBe(false)
    choice.pick('rebase', 'callout') // cannot hold the look: refused, nothing is picked
    expect(choice.target('rebase')).toBeUndefined()
    expect(choice.ready).toBe(false)
    choice.pick('rebase', 'note')
    expect(choice.ready).toBe(true)
    expect(choice.request).toEqual({ how: 'rebase', target: 'note' })
    expect(choice.isOffered(deletion().targets[2]!, 'rebase')).toBe(false)
    expect(choice.isOffered(deletion().targets[2]!, 'assign')).toBe(true)
  })

  it('keep what was picked for the other way when the person switches', () => {
    const choice = new DeletionChoice(deletion())
    choice.pick('assign', 'note')
    choice.pick('rebase', 'body')
    choice.how = 'assign'
    expect(choice.request.target).toBe('note')
  })

  it('start on nothing when the plain style is not among the targets', () => {
    const choice = new DeletionChoice(deletion({ suggested: null }))
    expect(choice.target('assign')).toBeUndefined()
    expect(choice.ready).toBe(false)
  })

  it('ask for no style at all when nothing has the style and nothing is based on it', () => {
    const choice = new DeletionChoice(deletion({ uses: 0, children: [] }))
    expect(choice.needsTarget).toBe(false)
    expect(choice.ready).toBe(true)
    expect(choice.request.target).toBeNull()
  })
})

describe('what the dialog says before anything happens', () => {
  it('counts what has the style and what is based on it, one noun to a sentence', () => {
    expect(usedByLine('paragraph', deletion())).toBe('Used by: 14 paragraphs')
    expect(usedByLine('cell', deletion({ uses: 1 }))).toBe('Used by: 1 cell')
    expect(usedByLine('paragraph', deletion({ uses: 0 }))).toBe('Nothing has this style.')
    expect(basedOnLine(deletion())).toBe('Based on it: 1 style (Small quote)')
    expect(basedOnLine(deletion({ children: [{ id: 'a', name: 'A' }, { id: 'b', name: 'B' }] }))).toBe('Based on it: 2 styles (A, B)')
    expect(basedOnLine(deletion({ children: [] }))).toBe('')
  })

  it('says what will look different, counting first', () => {
    expect(lookDifferentLine('paragraph', deletion())).toBe('Will look different: 14 paragraphs, 1 style')
    expect(lookDifferentLine('paragraph', deletion({ children: [] }))).toBe('Will look different: 14 paragraphs')
    expect(lookDifferentLine('paragraph', deletion({ uses: 0, children: [{ id: 'a', name: 'A' }, { id: 'b', name: 'B' }] }))).toBe('Will look different: 2 styles')
    expect(lookDifferentLine('paragraph', deletion({ uses: 0, children: [] }))).toBe('')
  })

  it('names in words what differs between two looks', () => {
    expect(lookDifference({ 'font-style': 'italic', 'margin-left': '2em' }, {})).toEqual(['italic', 'spacing'])
    expect(lookDifference({ color: 'red' }, { color: 'red' })).toEqual([])
    expect(lookDifference({}, { 'font-weight': 'bold', 'border-top': '1px solid #000' })).toEqual(['bold', 'border'])
    expect(lookDifference({ 'font-family': 'x', 'text-align': 'left', 'line-height': '1.2' }, {})).toEqual(['font', 'alignment', 'line height'])
    expect(lookDifference({ 'white-space': 'nowrap' }, {})).toEqual(['other settings'])
    expect(lookDifference({ 'margin-left': '1em', 'margin-right': '1em' }, {})).toEqual(['spacing'])
  })

  it('says what differs under the style that takes the place, or nothing when nothing does', () => {
    const quote = view('quote', 'Quote', { resolved: { 'font-style': 'italic' } })
    expect(lookLostLine(quote, view('body', 'Body text', { resolved: {} }))).toBe('What differs: italic')
    expect(lookLostLine(quote, view('same', 'Same', { resolved: { 'font-style': 'italic' } }))).toBe('')
    expect(lookLostLine(quote, undefined)).toBe('')
  })

  it('announces a deletion in words: where what had the style is now', () => {
    expect(deletedLine('Quote', 'assign', null, 'Body text')).toBe('“Quote” deleted. What had it now has “Body text”.')
    expect(deletedLine('Quote', 'rebase', 'Quote (kept)', 'Note')).toBe('“Quote” deleted. What had it now has “Quote (kept)”, built on “Note”.')
    expect(deletedLine('Quote', 'rebase', null, 'Note')).toBe('“Quote” deleted. What had it now has “Note”.')
    expect(deletedLine('Quote', 'assign', null, undefined)).toBe('“Quote” deleted.')
  })
})

describe('hidden styles are not picked from (D780)', () => {
  const styles = [view('body', 'Body text'), view('remark', 'Remark', { hidden: true, origin: 'builtin' }), view('note', 'Note')]

  it('are left out of what a person picks, unless the selection has one', () => {
    expect(pickable(styles).map((s) => s.id)).toEqual(['body', 'note'])
    expect(pickable(styles, 'remark').map((s) => s.id)).toEqual(['body', 'remark', 'note'])
  })

  it('are left out of the gallery, but a selected one stays', () => {
    const slot = { name: 'paragraph', label: 'Paragraph', reads: ['text', 'paragraph', 'box'], kind: 'paragraph', takes: ['paragraph'] }
    expect(galleryFor(styles, slot, STYLE_MODEL).own.map((s) => s.id)).toEqual(['body', 'note'])
    expect(galleryFor(styles, slot, STYLE_MODEL, 'remark').own.map((s) => s.id)).toEqual(['body', 'remark', 'note'])
  })
})

describe('access keys of the row actions', () => {
  it('are the first letter of the label, so that a translation brings its own', () => {
    expect(accessKeyOf('Delete…')).toBe('d')
    expect(accessKeyOf('Löschen…')).toBe('l')
    expect(accessKeyOf('…Ärger')).toBe('ä')
    expect(accessKeyOf('…')).toBe('')
  })

  it('pick the action a key means among the labels a row has, in English and in German', () => {
    const english = { edit: 'Edit', rename: 'Rename', delete: 'Delete…', hide: 'Hide' }
    expect(actionForKey('d', english)).toBe('delete')
    expect(actionForKey('H', english)).toBe('hide')
    expect(actionForKey('e', english)).toBe('edit')
    expect(actionForKey('x', english)).toBeUndefined()
    expect(actionForKey('Enter', english)).toBeUndefined()
    const german = { edit: 'Bearbeiten', rename: 'Umbenennen', delete: 'Löschen…', show: 'Einblenden' }
    expect(actionForKey('l', german)).toBe('delete')
    expect(actionForKey('e', german)).toBe('show')
    expect(actionForKey('u', german)).toBe('rename')
  })

  it('split a label around the letter that is underlined', () => {
    expect(mnemonic('Delete…')).toEqual({ head: '', key: 'D', tail: 'elete…' })
    expect(mnemonic('…Ärger')).toEqual({ head: '…', key: 'Ä', tail: 'rger' })
    expect(mnemonic('…')).toEqual({ head: '…', key: '', tail: '' })
  })
})

describe('the host the dialog talks to', () => {
  it('passes the four calls on, and says nothing of one that is refused', async () => {
    const session = {
      styleDeletion: vi.fn(async () => deletion()),
      deleteStyle: vi.fn(async (_s: string, _h: string, _t: string | null) => ({ standIn: 'quote-kept' }) as { standIn: string | null } | { refused: string } | false),
      hideStyle: vi.fn(async () => true),
      undo: vi.fn(async () => true),
    }
    const host = deletionHost(session)!
    expect((await host.preview('quote'))?.name).toBe('Quote')
    expect(await host.remove('quote', 'rebase', 'note')).toEqual({ standIn: 'quote-kept' })
    expect(session.deleteStyle).toHaveBeenCalledWith('quote', 'rebase', 'note')
    expect(await host.hide('remark', true)).toBe(true)
    expect(await host.undo()).toBe(true)
    session.deleteStyle.mockResolvedValueOnce({ refused: 'Somebody began to use it' })
    const refused = await host.remove('quote', 'assign', 'body')
    expect(refused && wasRefused(refused)).toBe(true)
    session.deleteStyle.mockResolvedValueOnce(false)
    expect(await host.remove('quote', 'assign', 'body')).toBeNull()
  })

  it('is left out of a session that cannot', () => {
    expect(deletionHost({})).toBeUndefined()
    expect(deletionHost({ styleDeletion: async () => null })).toBeUndefined()
  })
})

// ------------------------------------------------------------------------------------------------ over the wire
class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  handlers: Record<string, (params: any) => any> = {}
  events: EventHandler[] = []
  async connect() {
    return { user: 'ann', role: 'owner', doc: 'essay', app: 'composes', branch: 'main', revision: 'main:2', id: 1, color: '#e6194b', people: [], presence: [], checkpoints: [], limits: { max_text: 32767 }, branches: [{ name: 'main', head: 'main:2', active: true, forked_from: null }], proposal: null, returned: null } as never
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
  sent(method: string) {
    return this.calls.filter((c) => c.method === method).map((c) => c.params)
  }
}

async function opened(role = 'owner') {
  const link = new FakeLink()
  link.handlers = {
    paragraphs: () => ({ revision: 'main:2', styles: [], paragraphs: [{ id: 'b1', style: 'body', text: 'hi', runs: [[2, 'ann', null]] }] }),
    suggestions: () => [],
    style_model: () => STYLE_MODEL,
    palette: () => ({ type: 'palette', roles: [], readings: [] }),
    log: () => [],
    chat_log: () => [],
    checkpoints: () => [],
    history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
    branches: () => [{ name: 'main', head: 'main:2', active: true, forked_from: null }],
    restore_policy: () => ({ policy: 'consensus' }),
    hold: () => ({}),
    look: () => ({}),
    unlock: () => ({}),
  }
  const session = new TextSession(() => link, { retryDelays: [0] })
  await session.open()
  if (role === 'viewer') session.state.me.role = 'viewer'
  return { link, session }
}

describe('deleting a style over the wire', () => {
  it('asks what it would do, and says nothing when it cannot be asked', async () => {
    const { link, session } = await opened()
    link.handlers.style_deletion = () => deletion()
    expect((await session.styleDeletion('quote'))?.uses).toBe(14)
    expect(link.sent('style_deletion')).toEqual([{ style: 'quote' }])
    delete link.handlers.style_deletion
    expect(await session.styleDeletion('quote')).toBeNull()
  })

  it('sends the way and the style, and tells which style was made for what had it', async () => {
    const { link, session } = await opened()
    link.handlers.delete_style = () => ({ stand_in: 'quote-kept', revision: 'main:3' })
    expect(await session.deleteStyle('quote', 'rebase', 'note')).toEqual({ standIn: 'quote-kept' })
    expect(link.sent('delete_style')).toEqual([{ style: 'quote', how: 'rebase', target: 'note', base: 'main:2' }])
    link.handlers.delete_style = () => ({ stand_in: null, revision: 'main:4' })
    expect(await session.deleteStyle('plain', 'assign', null)).toEqual({ standIn: null })
    expect(link.sent('delete_style')[1]).toEqual({ style: 'plain', how: 'assign', base: 'main:2' })
  })

  it('hands back the server’s sentence when this deletion is refused, and tells anything else as a notice', async () => {
    const { link, session } = await opened()
    link.handlers.delete_style = () => {
      throw new ProtocolError('command_error', 'Somebody began to use “Quote” while you were deleting it. Nothing was changed.')
    }
    expect(await session.deleteStyle('quote', 'assign', 'body')).toEqual({ refused: 'Somebody began to use “Quote” while you were deleting it. Nothing was changed.' })
    link.handlers.delete_style = () => {
      throw new ProtocolError('forbidden', 'no')
    }
    session.state.notice = null
    expect(await session.deleteStyle('quote', 'assign', 'body')).toBe(false)
    expect(session.state.notice?.text).toBe('You can only look at this document.')
  })

  it('hides and shows a style', async () => {
    const { link, session } = await opened()
    link.handlers.hide_style = () => ({ revision: 'main:3' })
    expect(await session.hideStyle('remark', true)).toBe(true)
    expect(await session.hideStyle('remark', false)).toBe(true)
    expect(link.sent('hide_style')).toEqual([
      { style: 'remark', hidden: true, base: 'main:2' },
      { style: 'remark', hidden: false, base: 'main:2' },
    ])
  })

  it('does neither in a text that can only be looked at', async () => {
    const { link, session } = await opened('viewer')
    link.handlers.delete_style = () => ({ stand_in: null, revision: 'main:3' })
    link.handlers.hide_style = () => ({ revision: 'main:3' })
    expect(await session.deleteStyle('quote', 'assign', 'body')).toBe(false)
    expect(await session.hideStyle('remark', true)).toBe(false)
    expect(link.sent('delete_style')).toEqual([])
    expect(link.sent('hide_style')).toEqual([])
  })
})
