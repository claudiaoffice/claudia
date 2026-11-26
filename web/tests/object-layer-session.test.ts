// The object layer, the styles, the palette and the language work the same in all three apps (D1432), and a person who
// may only look is told so before anything is sent (CODE-75). Each case runs against the sheet, the text and the slide
// session alike.
import { describe, expect, it } from 'vitest'
import type { BaseSession, BaseState} from '~/lib/base-session';
import type { LinkLike, Welcome } from '~/lib/protocol'
import { Session } from '~/lib/session'
import { SlideSession } from '~/lib/slide-session'
import { TextSession } from '~/lib/text-session'
import { FakeServer, type AppName } from './support/fake-server'

const STYLE = { id: 'plain', name: 'Plain', purpose: 'Anything', based_on: null, to_name: false, kind: 'box', css: {}, computed: {}, resolved: {} }
const NOTE = { ...STYLE, id: 'note', name: 'Note' }
const PALETTE = { type: 'palette', roles: [], readings: [] }

/** What each app's server answers when a session opens, over what the fake server answers of an empty document: here the
 *  document has a style, and a text has a paragraph. */
const SERVERS: Record<AppName, Record<string, (params: any) => unknown>> = {
  computes: {
    sheets: () => [{ id: 's1', name: 'Sheet1' }],
    styles: () => [STYLE],
    style_uses: () => ({ uses: {} }),
  },
  composes: {
    paragraphs: () => ({ styles: [STYLE], paragraphs: [{ id: 'b1', style: 'plain', text: '', runs: [] }], lists: [], schemes: [] }),
  },
  creates: {
    styles: () => [STYLE],
  },
}

const APPS = [
  { app: 'computes' as const, make: (l: () => LinkLike) => new Session(l, { retryDelays: [] }) },
  { app: 'composes' as const, make: (l: () => LinkLike) => new TextSession(l, { retryDelays: [] }) },
  { app: 'creates' as const, make: (l: () => LinkLike) => new SlideSession(l, { retryDelays: [] }) },
]

async function opened(app: AppName, make: (l: () => LinkLike) => BaseSession<BaseState>, role = 'editor') {
  const link = new FakeServer(app, { welcome: { role: role as Welcome['role'], doc: 'd', revision: 'main:0', branches: [] }, handlers: SERVERS[app] })
    .on('rename_style', () => ({ revision: 'main:1' }))
    .on('set_role', () => ({ revision: 'main:1' }))
  const session = make(() => link)
  await session.open()
  await session.settled()
  return { link, session }
}

describe.each(APPS)('the $app session', ({ app, make }) => {
  it('tells a viewer she can only look, and sends nothing (CODE-75)', async () => {
    const { link, session } = await opened(app, make, 'viewer')
    const sent = link.calls.length

    expect(await session.renameStyle('plain', 'Calm')).toBe(false)
    expect(await session.changeStyle('plain', { set: { color: 'red' } })).toBe(false)
    expect(await session.setRole('accent', '#ff0000')).toBe(false)
    expect(await session.replacePalette([])).toBe(false)
    expect(await session.removeObject('o1')).toBe(false)
    expect(await session.rotateObject('o1', 90)).toBe(false)
    expect(await session.describeObject('o1', 'A chart', false)).toBe(false)
    expect(await session.setLanguage('de')).toBe(false)

    expect(link.calls.length).toBe(sent)
    expect(session.state.notice?.text).toBe('You can only look at this document.')
  })

  it('sends a change of an editor against the revision she sees', async () => {
    const { link, session } = await opened(app, make)

    expect(await session.renameStyle('plain', 'Calm')).toBe(true)

    expect(link.calls.at(-1)).toEqual({ method: 'rename_style', params: { style: 'plain', name: 'Calm', base: 'main:0' } })
  })

  it('keeps objects by id and in their holder’s stacking order, as the events say', async () => {
    const { link, session } = await opened(app, make)
    const box = { id: 'o1', kind: 'text', w: 10, h: 10, style: 'plain', anchor: {} }

    link.push('objects', { type: 'objects', holder: 'h1', changed: [box], removed: [], order: ['o1'] })
    expect(session.state.objects.o1).toEqual(box)
    expect(session.state.order.h1).toEqual(['o1'])

    link.push('objects', { type: 'objects', holder: 'h1', changed: [], removed: ['o1'], order: [] })
    expect(session.state.objects.o1).toBeUndefined()
    expect(session.state.order.h1).toEqual([])
  })

  it('keeps the styles by id, in the order the server lists them, and the palette and the language', async () => {
    const { link, session } = await opened(app, make)

    link.push('styles', { type: 'styles', styles: [NOTE, STYLE] })
    link.push('palette', { ...PALETTE, roles: [{ id: 'text', name: 'Text', purpose: 'words', colour: '#000' }] })
    link.push('language', { type: 'language', language: 'de' })

    expect(Object.keys(session.state.styles)).toEqual(['note', 'plain'])
    expect(session.styleViews().map((s) => s.id)).toEqual(['note', 'plain'])
    expect(session.state.palette?.roles).toHaveLength(1)
    expect(session.state.language).toBe('de')
  })

  it('takes in a picture and an outline the document learned, and lets go of one it forgot', async () => {
    const { link, session } = await opened(app, make)

    link.push('image', { type: 'image', id: 'i1', asset: { id: 'i1', format: 'png', data: '', width: 1, height: 1 } })
    link.push('shape', { type: 'shape', id: 'star', definition: { id: 'star' } })
    expect(session.state.images.i1).toBeDefined()
    expect(session.state.shapes.star).toBeDefined()

    link.push('image', { type: 'image', id: 'i1', asset: null })
    expect(session.state.images.i1).toBeUndefined()
  })
})
