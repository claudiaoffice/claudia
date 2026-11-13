import { describe, expect, it } from 'vitest'
import { facetCss, scaleCss } from '~/lib/slide-style'

const css = {
  fill: '#e7e1f4',
  stroke: '#5b4bc4',
  'stroke-width': '4px',
  color: '#1f1a33',
  'font-family': 'Inter, sans-serif',
  'font-size': '36px',
  'line-height': '1.25',
  'letter-spacing': '2px',
  'text-align': 'center',
}

describe('scaleCss', () => {
  it('scales the lengths and leaves everything else as it is', () => {
    const scaled = scaleCss(css, 0.5)
    expect(scaled['font-size']).toBe('18px')
    expect(scaled['stroke-width']).toBe('2px')
    expect(scaled['letter-spacing']).toBe('1px')
    expect(scaled['line-height']).toBe('1.25')
    expect(scaled.fill).toBe('#e7e1f4')
    expect(scaled['font-family']).toBe('Inter, sans-serif')
  })
  it('keeps what it does not understand as it is (a length that is not in pixels)', () => {
    expect(scaleCss({ 'font-size': '2em' }, 0.5)['font-size']).toBe('2em')
  })
  it('does not change the style it is given', () => {
    scaleCss(css, 2)
    expect(css['font-size']).toBe('36px')
  })
  it('rounds to a hundredth of a pixel', () => {
    expect(scaleCss({ 'font-size': '40px' }, 0.3333)['font-size']).toBe('13.33px')
  })
})

// The facets as the server's `style_model` sends them (D303).
const FACETS = {
  text: ['font-family', 'font-size', 'font-weight', 'font-style', 'text-decoration', 'color', 'letter-spacing', 'word-spacing'],
  paragraph: ['text-align', 'line-height', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left'],
  box: ['background-color', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left', 'border-top', 'border-right', 'border-bottom', 'border-left'],
  outline: ['fill', 'stroke', 'stroke-width'],
}

describe('facetCss', () => {
  it('gives the outline the paint and the words the type, by facet', () => {
    expect(Object.keys(facetCss(css, FACETS, ['outline'])).sort()).toEqual(['fill', 'stroke', 'stroke-width'])
    expect(Object.keys(facetCss(css, FACETS, ['text', 'paragraph'])).sort()).toEqual(['color', 'font-family', 'font-size', 'letter-spacing', 'line-height', 'text-align'])
  })
  it('gives a box only what a box reads, so a bundle can stand in a box slot (D316)', () => {
    expect(facetCss({ 'background-color': 'red', color: 'blue', 'padding-top': '4px' }, FACETS, ['box'])).toEqual({ 'background-color': 'red', 'padding-top': '4px' })
  })
  it('leaves out what a style does not say, and everything while the facets have not arrived', () => {
    expect(facetCss({ color: 'red' }, FACETS, ['outline'])).toEqual({})
    expect(facetCss(css, undefined, ['outline'])).toEqual({})
  })
})

describe('scaleCss and a box', () => {
  it('scales the padding of a box with the slide', () => {
    expect(scaleCss({ 'padding-top': '20px' }, 0.5)['padding-top']).toBe('10px')
  })
})
