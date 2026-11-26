// Paragraphs are things (D554): a heading, a list item or a paragraph can be pointed at with `#` in the chat. The text
// session offers the named paragraphs, the headings and the paragraph with the caret; picking one without a name asks
// the server to name it (`name_thing`) first, so that the tag carries the name the document uses.
import { describe, expect, it } from 'vitest'
import { STYLE_MODEL } from './style-model.fixture'
import type { Welcome } from '~/lib/protocol'
import { TextSession } from '~/lib/text-session'
import { FakeServer } from './support/fake-server'

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

// `heading` is the level the server worked out for each style (E9.22): the client never walks the parents itself.
const view = (id: string, based_on: string | null = null, heading: number | null = null) => ({ id, name: id, purpose: '', based_on, css: {}, computed: {}, to_name: false, heading })
const STYLES = [view('body'), view('heading-1', 'body', 1), view('chapter', 'heading-1', 1), view('aside', 'body', 3)]
const paragraph = (id: string, style: string, text: string, extra: object = {}) => ({ id, style, text, runs: [[[...text].length, 'ann', null]], ...extra })

async function opened() {
  const link = new FakeServer('composes', { welcome: WELCOME })
  link.handlers = {
    paragraphs: () => ({
      revision: 'main:2',
      styles: STYLES,
      lists: [{ id: 'l1', scheme: 'bullets', start: 1, name: '' }],
      schemes: [],
      paragraphs: [
        paragraph('b1', 'heading-1', 'Introduction'),
        paragraph('b2', 'body', 'First words.', { name: 'Opening' }),
        paragraph('b3', 'body', 'a point', { item: { list: 'l1', level: 0 } }),
        paragraph('b4', 'chapter', 'Results'),
        paragraph('b5', 'body', 'Plain text here.'),
        paragraph('b6', 'aside', 'A heading by its level, not its name'),
      ],
    }),
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
    objects: () => ({ objects: [] }),
    name_thing: (p: any) => ({ name: p.id === 'b1' ? 'Introduction' : 'Paragraph 1', revision: 'main:3' }),
  }
  const session = new TextSession(() => link, { retryDelays: [0] })
  await session.open()
  return { link, session }
}

describe('paragraphs as things (D554)', () => {
  it('knows what kind of paragraph each is, a style based on a heading included', async () => {
    const { session } = await opened()
    expect(session.state.paragraphs.map((b) => session.paragraphKind(b))).toEqual(['heading', 'paragraph', 'item', 'heading', 'paragraph', 'heading'])
  })

  it('offers the named paragraphs, the headings, and the paragraph with the caret', async () => {
    const { session } = await opened()
    session.state.selection = { anchor: { paragraph: 'b5', offset: 0 }, focus: { paragraph: 'b5', offset: 0 } }
    const offered = await session.taggableThings()
    expect(offered).toEqual([
      { id: 'b2', name: 'Opening', kind: 'paragraph' },
      { id: 'b1', name: 'Introduction', kind: 'heading', unnamed: true },
      { id: 'b4', name: 'Results', kind: 'heading', unnamed: true },
      { id: 'b5', name: 'Plain text here.', kind: 'paragraph', unnamed: true },
      { id: 'b6', name: 'A heading by its level, not its name', kind: 'heading', unnamed: true },
    ])
  })

  it('names a paragraph that is pointed at for the first time, and then knows that name', async () => {
    const { link, session } = await opened()
    const thing = await session.thingToReference('b1')
    expect(thing).toEqual({ id: 'b1', name: 'Introduction', kind: 'heading' })
    expect(link.calls.filter((c) => c.method === 'name_thing').map((c) => c.params.id)).toEqual(['b1'])
    expect(session.nameOf('b1')).toBe('Introduction')
  })

  it('asks for no name for a paragraph that has one', async () => {
    const { link, session } = await opened()
    expect(await session.thingToReference('b2')).toEqual({ id: 'b2', name: 'Opening', kind: 'paragraph' })
    expect(link.calls.some((c) => c.method === 'name_thing')).toBe(false)
  })

  it('follows a rename that another person makes', async () => {
    const { link, session } = await opened()
    link.push('thing_renamed', { type: 'thing_renamed', id: 'b2', name: 'Start' })
    expect(session.nameOf('b2')).toBe('Start')
  })

  it('goes to a paragraph a tag points at (the editor scrolls there; the caret stays; with no place reported there is no way back to offer)', async () => {
    const { session } = await opened()
    session.state.selection = { anchor: { paragraph: 'b5', offset: 0 }, focus: { paragraph: 'b5', offset: 0 } }
    await session.goToThing('b2')
    expect(session.state.pointed).toMatchObject({ id: 'b2', holder: 'b2' })
    expect(session.state.wayBack).toBeNull()
  })
})
