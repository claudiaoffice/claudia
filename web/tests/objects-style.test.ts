import { describe, expect, it } from 'vitest'
import { cssOf, wordsCssOf, type ObjectBody, type StyleDef } from '~/lib/objects'

// A style as the server sends it: `computed` still names the palette's roles, `resolved` has the colours (D200).
const plainShape: StyleDef = {
  id: 'plain-shape',
  name: 'Plain shape',
  purpose: 'a shape that marks a part of the slide',
  based_on: 'body-text',
  css: { fill: '@accent/14', stroke: '@accent' },
  to_name: false,
  kind: 'outline',
  computed: { fill: '@accent/14', stroke: '@accent', 'font-size': '36px' },
  resolved: { fill: 'rgba(91, 75, 196, 0.14)', stroke: '#5B4BC4', 'font-size': '36px' },
}

const body: ObjectBody = { id: 'o1', kind: 'shape', w: 200, h: 120, style: 'plain-shape', rotation: 0, snap: true }

describe('cssOf', () => {
  it('draws with the resolved css, so a palette role never reaches the page', () => {
    // The whole point of resolving on the server: a browser would silently drop `fill: @accent/14`.
    const css = cssOf({ 'plain-shape': plainShape }, body)
    expect(css.fill).toBe('rgba(91, 75, 196, 0.14)')
    expect(css.stroke).toBe('#5B4BC4')
    expect(Object.values(css).some((value) => value.includes('@'))).toBe(false)
  })

  it('keeps everything that is not a colour', () => {
    expect(cssOf({ 'plain-shape': plainShape }, body)['font-size']).toBe('36px')
  })

  it('is empty for a style the document does not have', () => {
    expect(cssOf({}, body)).toEqual({})
  })
})

// D310: a shape's outline and its words are two slots. The words follow the paragraph's own style.
const shapeLabel: StyleDef = {
  id: 'shape-label',
  name: 'Shape label',
  purpose: 'the words inside a shape',
  based_on: 'body-text',
  css: { 'text-align': 'center' },
  to_name: false,
  kind: 'paragraph',
  computed: { 'text-align': 'center', color: '@text' },
  resolved: { 'text-align': 'center', color: '#1F1A33' },
}

describe('wordsCssOf', () => {
  const styles = { 'plain-shape': plainShape, 'shape-label': shapeLabel }
  const withWords: ObjectBody = { ...body, paragraph: { id: 'o1', style: 'shape-label', text: 'hi', runs: [{ length: 2, author: 'ann', via: null }] } }

  it('draws the words of an object with its paragraph’s style, not the object’s own', () => {
    expect(wordsCssOf(styles, withWords)).toEqual({ 'text-align': 'center', color: '#1F1A33' })
  })

  it('is empty for an object without words, or words under a style the document does not have', () => {
    expect(wordsCssOf(styles, body)).toEqual({})
    expect(wordsCssOf({}, withWords)).toEqual({})
  })
})
