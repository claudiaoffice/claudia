import { describe, expect, it } from 'vitest'
import { pathCss, scaleCss, textCss } from '~/lib/slide-style'

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

describe('pathCss and textCss', () => {
  it('give the outline the paint and the text the type', () => {
    expect(Object.keys(pathCss(css)).sort()).toEqual(['fill', 'stroke', 'stroke-width'])
    expect(Object.keys(textCss(css)).sort()).toEqual(['color', 'font-family', 'font-size', 'letter-spacing', 'line-height', 'text-align'])
  })
  it('leave out what a style does not say', () => {
    expect(pathCss({ color: 'red' })).toEqual({})
    expect(textCss({ fill: 'red' })).toEqual({})
  })
})
