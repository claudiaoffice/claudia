import { describe, expect, it } from 'vitest'
import { lookOf, type LookHolder } from '~/lib/text-object-look'
import type { VisualObject, ParagraphAnchor } from '~/lib/objects'

const FACETS = { text: ['color', 'font-size'], paragraph: ['text-align'], box: ['background-color', 'padding-top'], outline: ['fill', 'stroke'] }
const style = (id: string, resolved: Record<string, string>) => ({ id, name: id, purpose: '', based_on: null, css: {}, computed: resolved, resolved, to_name: false, kind: 'paragraph' })
const holder = (extra: Partial<LookHolder> = {}): LookHolder => ({
  styles: Object.fromEntries([style('plain-box', { 'background-color': '#fff', 'padding-top': '4px', fill: 'red' }), style('plain-shape', { fill: '#eee', stroke: '#333' }), style('body', { color: '#123456', 'font-size': '16px', 'text-align': 'center', fill: 'blue' })].map((s) => [s.id, s])),
  styleModel: { facets: FACETS, kinds: {}, slots: {}, targets: [] },
  shapes: { circle: { id: 'circle', path: 'M0 0Z', text_area: { x: 10, y: 20, w: 80, h: 60 } } },
  images: { i1: { id: 'i1', format: 'svg', width: 3, height: 2, animated: false, data: 'AA==', first_frame: null } },
  ...extra,
})
const object = (extra: object): VisualObject<ParagraphAnchor> =>
  ({ id: 'o1', kind: 'image', w: 100, h: 50, style: 'plain-image', paragraph: null, ref: null, imported: null, rotation: 0, snap: false, description: '', decorative: false, anchor: { kind: 'paragraph', holder: 'b1', offset: 0 }, ...extra }) as VisualObject<ParagraphAnchor>

describe('how an object in a text looks', () => {
  it('shows a picture by its data URL, and nothing before the asset has arrived', () => {
    expect(lookOf(holder(), object({ ref: 'i1' })).picture).toBe('data:image/svg+xml;base64,AA==')
    expect(lookOf(holder(), object({ ref: 'later' })).picture).toBe('')
  })
  it('draws a shape by its outline, painted by the facets of its own style', () => {
    const look = lookOf(holder(), object({ kind: 'shape', ref: 'circle', style: 'plain-shape' }))
    expect(look.outline).toEqual({ path: 'M0 0Z', paint: { fill: '#eee', stroke: '#333' } })
    expect(look.words).toBeNull()
  })
  it('puts the words of a shape in the outline’s text area, centred, in the style of the words and not of the shape', () => {
    const look = lookOf(holder(), object({ kind: 'shape', ref: 'circle', style: 'plain-shape', paragraph: { id: 'p', style: 'body', text: 'Hi', runs: [] } }))
    expect(look.words?.text).toBe('Hi')
    expect(look.words?.area).toMatchObject({ left: '10%', top: '20%', width: '80%', height: '60%', 'justify-content': 'center' })
    expect(look.words?.css).toMatchObject({ color: '#123456', 'font-size': '16px', 'text-align': 'center' })
    expect(look.words?.css.fill).toBeUndefined()
  })
  it('gives a text box its own box and the whole of itself for its words', () => {
    const look = lookOf(holder(), object({ kind: 'text', style: 'plain-box', paragraph: { id: 'p', style: 'body', text: 'Hello', runs: [] } }))
    expect(look.outline).toBeNull()
    expect(look.words?.area).toMatchObject({ left: '0%', top: '0%', width: '100%', height: '100%', 'justify-content': 'flex-start' })
    expect(look.words?.css).toMatchObject({ 'background-color': '#fff', 'padding-top': '4px', color: '#123456' })
    expect(look.words?.css.fill).toBeUndefined()
  })
  it('reads no facet when the server has sent no style model', () => {
    const look = lookOf(holder({ styleModel: null }), object({ kind: 'text', style: 'plain-box', paragraph: { id: 'p', style: 'body', text: 'Hello', runs: [] } }))
    expect(look.words?.css['color']).toBeUndefined()
  })
  it('says that a chart cannot be shown in a text yet, and draws nothing for it', () => {
    const look = lookOf(holder(), object({ kind: 'diagram', diagram: 'c1' }))
    expect(look.unsupported).toBe(true)
    expect(look.picture).toBe('')
  })
  it('leaves a container to its own face', () => {
    expect(lookOf(holder(), object({ kind: 'container', ref: 'r1' }))).toMatchObject({ container: true, unsupported: false })
  })
})
