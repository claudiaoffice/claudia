import { describe, expect, it, vi } from 'vitest'
import { nounOf, objectStyleHost, objectUses, partsOf, slotOf, styleInSlot, type ObjectStyling } from '~/lib/object-style-host'
import type { ColourRole, ObjectBody, Reading } from '~/lib/objects'
import type { StyleView } from '~/lib/style-css'

const BODY = (over: Partial<ObjectBody> = {}): ObjectBody =>
  ({ id: 'o1', kind: 'shape', w: 200, h: 120, style: 'plain-shape', rotation: 0, snap: true, ...over }) as ObjectBody

const style = (id: string, name: string): StyleView => ({
  id,
  name,
  purpose: '',
  based_on: id === 'body-text' ? null : 'body-text',
  css: {},
  computed: { fill: '@accent/14' },
  resolved: { fill: 'rgba(91, 75, 196, 0.14)' },
  to_name: false,
  kind: id === 'body-text' ? 'paragraph' : 'outline',
})

const ROLES: ColourRole[] = [{ id: 'accent', name: 'Accent', purpose: '', colour: '#5B4BC4' }]
const READINGS: Reading[] = [
  { foreground: 'accent-text', background: 'accent', ratio: 6.46, floor: 4.5, ok: true, words: true },
]

function styling(over: Partial<ObjectStyling> = {}) {
  const calls: Record<string, unknown[]> = {}
  const spy = (name: string) =>
    vi.fn(async (...args: unknown[]) => {
      calls[name] = args
      return true
    })
  const session: ObjectStyling = {
    readOnly: false,
    styles: [style('body-text', 'Body text'), style('plain-shape', 'Plain shape')],
    roles: ROLES,
    readings: READINGS,
    selected: BODY(),
    bodies: [BODY(), BODY({ id: 'o2' }), BODY({ id: 'o3', style: 'body-text', kind: 'text' })],
    applyStyle: spy('applyStyle'),
    changeStyle: spy('changeStyle'),
    deviateStyle: spy('deviateStyle'),
    renameStyle: spy('renameStyle'),
    checkCss: vi.fn(async () => null),
    setRole: spy('setRole'),
    ...over,
  }
  return { host: objectStyleHost(session), session, calls }
}

describe('what a kind of object has', () => {
  it('gives a picture no fill and no words: it carries its own colours and holds no text', () => {
    expect(partsOf('image')).toEqual({ words: false, box: false })
  })

  it('gives a chart nothing: its box style reads none of the outline controls (D304, D305)', () => {
    expect(partsOf('diagram')).toEqual({ words: false, box: false })
  })

  it('gives a shape its outline only: its words have a style of their own (D310)', () => {
    expect(partsOf('shape')).toEqual({ words: false, box: true })
  })

  it('gives a text box its words: the slot the font controls fit (D304)', () => {
    expect(partsOf('text')).toEqual({ words: true, box: false })
  })

  it('calls each kind what a person would call it', () => {
    expect([nounOf('shape'), nounOf('text'), nounOf('image'), nounOf('diagram')]).toEqual([
      'shape',
      'text box',
      'picture',
      'chart',
    ])
    expect(nounOf(undefined)).toBe('object')
  })
})

describe('the object as a style host', () => {
  it('reports the selected object’s own style, and what the object is', () => {
    const { host } = styling()
    expect(host.current?.id).toBe('plain-shape')
    expect(host.noun).toBe('shape')
    expect(host.parts).toEqual({ words: false, box: true }) // an outline: its words have a style of their own (D310)
  })

  it('counts how many objects have each style', () => {
    const { host } = styling()
    expect(host.uses()).toEqual({ 'plain-shape': 2, 'body-text': 1 })
    expect(objectUses([])).toEqual({})
  })

  it('carries the palette and its readings through to the controls', () => {
    const { host } = styling()
    expect(host.roles).toEqual(ROLES)
    expect(host.readings).toEqual(READINGS)
  })

  it('points the selected object at another style', async () => {
    const { host, calls } = styling()
    expect(await host.apply('body-text')).toBe(true)
    expect(calls.applyStyle).toEqual([[{ object: 'o1' }], 'body-text', 'outline'])
  })

  it('deviates from the selected object’s own style, for that object alone', async () => {
    // "This shape only": the change must not reach every other shape that shares the style (D75).
    const { host, calls } = styling()
    expect(await host.deviate({ set: { fill: '@attention' } })).toBe(true)
    expect(calls.deviateStyle).toEqual(['plain-shape', [{ object: 'o1' }], 'outline', { set: { fill: '@attention' } }])
  })

  it('changes a role for the whole document', async () => {
    const { host, calls } = styling()
    expect(await host.setRole('accent', '#008080')).toBe(true)
    expect(calls.setRole).toEqual(['accent', '#008080'])
  })

  it('has nothing current with nothing selected, and refuses the edits that need one', async () => {
    const { host } = styling({ selected: null })
    expect(host.current).toBeUndefined()
    expect(await host.apply('body-text')).toBe(false)
    expect(await host.deviate({ set: { fill: '#fff' } })).toBe(false)
  })

  it('is not read-only merely because nothing is selected: the palette is the document’s', async () => {
    // Found in a browser: reporting read-only here disabled the whole Colours dialog for an owner who happened
    // to have no shape selected.
    const { host, calls } = styling({ selected: null })
    expect(host.readOnly).toBe(false)
    expect(await host.setRole('accent', '#008080')).toBe(true)
    expect(calls.setRole).toEqual(['accent', '#008080'])
  })

  it('is read-only for a viewer', () => {
    expect(styling({ readOnly: true }).host.readOnly).toBe(true)
  })

  it('follows the selection when it moves to another kind of object', () => {
    const { host, session } = styling()
    session.selected = BODY({ id: 'o9', kind: 'image', style: 'plain-image' })
    expect(host.noun).toBe('picture')
    expect(host.parts).toEqual({ words: false, box: false })
  })
})

describe('the slots an object is styled in (D304)', () => {
  it('works on a shape’s outline, a text box’s words and everything else’s box', () => {
    expect([slotOf('shape'), slotOf('text'), slotOf('image'), slotOf('diagram')]).toEqual(['outline', 'words', 'box', 'box'])
  })

  it('reads a text box’s style from its words', () => {
    const box = BODY({ kind: 'text', style: 'plain-box', paragraph: { id: 'o1', style: 'body-text', text: '', runs: [] } })
    expect(styleInSlot(box)).toBe('body-text')
    expect(styleInSlot(BODY())).toBe('plain-shape')
  })

  it('applies and deviates in a text box’s words, not its box', async () => {
    const box = BODY({ kind: 'text', style: 'plain-box', paragraph: { id: 'o1', style: 'body-text', text: '', runs: [] } })
    const { host, calls } = styling({ selected: box })
    expect(host.current?.id).toBe('body-text')
    await host.apply('body-text')
    expect(calls.applyStyle).toEqual([[{ object: 'o1' }], 'body-text', 'words'])
    await host.deviate({ set: { 'font-weight': 'bold' } })
    expect(calls.deviateStyle).toEqual(['body-text', [{ object: 'o1' }], 'words', { set: { 'font-weight': 'bold' } }])
  })

  it('counts an object’s words as a use of their style', () => {
    const box = BODY({ kind: 'text', style: 'plain-box', paragraph: { id: 'o1', style: 'body-text', text: '', runs: [] } })
    expect(objectUses([box])).toEqual({ 'plain-box': 1, 'body-text': 1 })
  })
})
