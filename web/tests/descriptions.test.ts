import { describe, expect, it, vi } from 'vitest'
import { MAX_DESCRIPTION, describeParams, descriptionProblem, isDescribed, objectName, pictureAlt, type Describable } from '~/lib/descriptions'

const body = (extra: Partial<Describable> = {}): Describable => ({ kind: 'text', description: '', decorative: false, imported: null, ...extra })
const picture = (extra: Partial<Describable> = {}) => body({ kind: 'image', description: 'two cyclists', ...extra })

describe('objectName: what a screen reader says for an object', () => {
  it('names a picture by its description', () => {
    expect(objectName(picture())).toBe('Picture: two cyclists')
  })
  it('says a picture is decorative, so that nobody hunts for a description it does not have', () => {
    expect(objectName(picture({ decorative: true, description: '' }))).toBe('Picture (decorative)')
  })
  it('says a picture has no description when it has none, rather than reading an empty name', () => {
    expect(objectName(picture({ description: '' }))).toBe('Picture (no description)')
  })
  it('names a chart the same way', () => {
    expect(objectName(body({ kind: 'diagram', description: 'sales by quarter' }))).toBe('Chart: sales by quarter')
    expect(objectName(body({ kind: 'diagram' }))).toBe('Chart (no description)')
  })
  it('names a rendered text container (a formula, a diagram drawn from text) as the picture it is shown as', () => {
    expect(objectName(body({ kind: 'rendered', description: 'the quadratic formula' }), { words: 'x = ...' })).toBe('Picture: the quadratic formula')
    expect(objectName(body({ kind: 'rendered' }), { words: 'x = ...' })).toBe('Picture (no description)')
  })
  it('names a text box by its words, or by its description when it has one', () => {
    expect(objectName(body(), { words: 'hello' })).toBe('Text box: hello')
    expect(objectName(body(), {})).toBe('Text box')
    expect(objectName(body({ description: 'the greeting' }), { words: 'hello' })).toBe('Text box: the greeting')
  })
  it('names a shape by its outline, its words, and its description when it has one', () => {
    expect(objectName(body({ kind: 'shape' }), { shape: 'Circle', words: 'hi' })).toBe('Circle: hi')
    expect(objectName(body({ kind: 'shape' }), {})).toBe('Shape')
    expect(objectName(body({ kind: 'shape', description: 'a server' }), { shape: 'Circle', words: 'hi' })).toBe('Circle: a server')
  })
  it('says a decorative text box or shape is decoration', () => {
    expect(objectName(body({ kind: 'shape', decorative: true }), { shape: 'Circle' })).toBe('Circle (decorative)')
  })
})

describe('pictureAlt: the alt text of the <img>', () => {
  it('is the description, and empty for a decoration so that a screen reader skips it', () => {
    expect(pictureAlt(picture())).toBe('two cyclists')
    expect(pictureAlt(picture({ decorative: true, description: '' }))).toBe('')
  })
  it('falls back to what the picture was imported with while a server that predates descriptions is in use', () => {
    const imported = { alt: 'a bicycle' } as Describable['imported']
    expect(pictureAlt(picture({ description: undefined as unknown as string, imported }))).toBe('a bicycle')
  })
})

describe('isDescribed: what an accessibility check will look for', () => {
  it('is true for a description or a decoration, false for neither', () => {
    expect(isDescribed(picture())).toBe(true)
    expect(isDescribed(picture({ decorative: true, description: '' }))).toBe(true)
    expect(isDescribed(picture({ description: '   ' }))).toBe(false)
  })
})

describe('descriptionProblem: what the dialog tells the person', () => {
  it('asks a picture for words, or for the decorative mark', () => {
    expect(descriptionProblem('image', '', false)).toBe('empty')
    expect(descriptionProblem('image', '   ', false)).toBe('empty')
    expect(descriptionProblem('image', 'a bicycle', false)).toBeNull()
    expect(descriptionProblem('image', '', true)).toBeNull()
  })
  it('lets any other object go without', () => {
    expect(descriptionProblem('shape', '', false)).toBeNull()
    expect(descriptionProblem('diagram', '', false)).toBeNull()
  })
  it('keeps to the length the model keeps to', () => {
    expect(MAX_DESCRIPTION).toBe(300)
    expect(descriptionProblem('shape', 'x'.repeat(300), false)).toBeNull()
    expect(descriptionProblem('shape', 'x'.repeat(301), false)).toBe('too-long')
  })
  it('refuses words on a decoration, which has none', () => {
    expect(descriptionProblem('shape', 'a box', true)).toBe('decorative-with-words')
  })
})

describe('describeParams: what is sent', () => {
  it('trims a description, and sends none for a decoration', () => {
    expect(describeParams('  a bicycle ', false)).toEqual({ description: 'a bicycle', decorative: false })
    expect(describeParams('left over', true)).toEqual({ description: '', decorative: true })
  })
})

describe('describeShortcut', () => {
  it('is Ctrl+Alt+D, known to the shells as format.describe, and runs what it is given', async () => {
    const { describeShortcut } = await import('~/lib/descriptions')
    const run = vi.fn()
    const def = describeShortcut(run, () => true)
    expect(def.id).toBe('format.describe')
    expect(def.chord).toEqual({ key: 'd', code: 'KeyD', ctrl: true, alt: true })
    def.run()
    expect(run).toHaveBeenCalledOnce()
    expect(def.enabled!()).toBe(true)
  })
})
