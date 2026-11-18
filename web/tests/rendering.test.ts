import { describe, expect, it } from 'vitest'
import { fenceOf, formatFence, outcomesOf, parseFence, pictureOf, renderedView, renderStatus, statusText, toOutcome, type RenderingDef } from '../app/lib/rendering'

const def = (over: Partial<RenderingDef> = {}): RenderingDef => ({
  format: 1, id: 'r1', type: 'latex', source: 'x^2', params: {}, image: null, renderer: '', ...over,
})

describe('fences', () => {
  it('reads a fenced block of a known type', () => {
    expect(parseFence('```latex\n\\frac{a}{b}\n```', ['latex', 'mermaid'])).toEqual({ type: 'latex', source: '\\frac{a}{b}' })
  })
  it('knows the type in any case and ignores spaces after the opening fence', () => {
    expect(parseFence('``` Mermaid \ngraph TD\n```', ['mermaid'])).toEqual({ type: 'mermaid', source: 'graph TD' })
  })
  it('does not take a block of a type the server cannot make', () => {
    expect(parseFence('```python\nprint(1)\n```', ['latex'])).toBeNull()
  })
  it('needs the closing fence and nothing after it', () => {
    expect(parseFence('```latex\nx', ['latex'])).toBeNull()
    expect(parseFence('```latex\nx\n``` more', ['latex'])).toBeNull()
  })
  it('keeps empty text and inner blank lines', () => {
    expect(parseFence('```typst\n\n```', ['typst'])).toEqual({ type: 'typst', source: '' })
    expect(parseFence('```typst\na\n\nb\n```', ['typst'])?.source).toBe('a\n\nb')
  })
  it('writes a container back as the text it came from', () => {
    expect(formatFence('latex', 'x^2')).toBe('```latex\nx^2\n```')
    expect(parseFence(formatFence('mermaid', 'a --> b'), ['mermaid'])).toEqual({ type: 'mermaid', source: 'a --> b' })
  })
  it('takes a longer fence when the text holds three backticks', () => {
    const text = formatFence('typst', 'a ``` b')
    expect(text.startsWith('````typst')).toBe(true)
    expect(parseFence(text, ['typst'])?.source).toBe('a ``` b')
  })
  it('makes the fence of a definition', () => {
    expect(fenceOf(def({ type: 'typst', source: '$x$' }))).toBe('```typst\n$x$\n```')
  })
})

describe('the picture of a container', () => {
  it('is the one the definition last made, else none', () => {
    expect(pictureOf(def({ image: 'i2' }))).toBe('i2')
    expect(pictureOf(def())).toBeNull()
    expect(pictureOf(undefined)).toBeNull()
  })
})

describe('what the person is told', () => {
  it('is drawing while a text waits for its picture', () => {
    expect(renderStatus(def({ source: 'x' }), undefined)).toEqual({ kind: 'drawing' })
  })
  it('is empty without text', () => {
    expect(renderStatus(def({ source: '  ' }), undefined)).toEqual({ kind: 'empty' })
  })
  it('is ready with a picture', () => {
    expect(renderStatus(def({ image: 'i1' }), { ok: true, diagnostics: [], message: '', unavailable: null })).toEqual({ kind: 'ready', diagnostics: [] })
  })
  it('is failed with the tool\'s words, or missing when the tool is not there', () => {
    const bad = { ok: false, diagnostics: [{ severity: 'error', message: 'oops', line: 1, column: 2 }], message: 'bad', unavailable: null }
    expect(renderStatus(def(), bad)).toEqual({ kind: 'failed', message: 'bad', diagnostics: bad.diagnostics })
    expect(renderStatus(def(), { ...bad, unavailable: 'latex' })).toEqual({ kind: 'unavailable', tool: 'latex', message: 'bad' })
  })
  it('keeps a picture it has even after a failed try, with the failure told', () => {
    const bad = { ok: false, diagnostics: [], message: 'bad', unavailable: null }
    expect(renderStatus(def({ image: 'i1' }), bad).kind).toBe('failed')
  })
})

describe('what a window that joins late is told', () => {
  const failed = { ok: false, diagnostics: [], message: 'Fatal Package fontspec Error', unavailable: null }
  it('takes the last outcome of each container from the definitions the server sends', () => {
    const known = outcomesOf([def({ id: 'a', outcome: failed }), def({ id: 'b', outcome: null }), def({ id: 'c' })])
    expect(Object.keys(known)).toEqual(['a'])
    expect(renderStatus(def({ id: 'a' }), known.a)).toEqual({ kind: 'failed', message: 'Fatal Package fontspec Error', diagnostics: [] })
  })
  it('says "drawing" only for a container no try has spoken for', () => {
    expect(renderStatus(def({ id: 'b' }), outcomesOf([def({ id: 'b' })]).b).kind).toBe('drawing')
  })
  it('fills what the server left out the same way for an event and for a definition', () => {
    expect(toOutcome({ ok: false, message: 'x' })).toEqual({ ok: false, diagnostics: [], message: 'x', unavailable: null })
  })
})

describe('words for a status', () => {
  const t = (id: string, vars?: Record<string, string | number>) => (vars ? id.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k])) : id)
  it('says each state in a sentence, and whether it must be announced at once', () => {
    expect(statusText({ kind: 'drawing' }, 'LaTeX', t)).toEqual({ text: 'Drawing…', urgent: false })
    expect(statusText({ kind: 'empty' }, 'LaTeX', t)).toEqual({ text: 'Empty LaTeX container: double-click to write', urgent: false })
    expect(statusText({ kind: 'ready', diagnostics: [] }, 'LaTeX', t)).toEqual({ text: '', urgent: false })
    expect(statusText({ kind: 'failed', message: 'bad', diagnostics: [] }, 'LaTeX', t)).toEqual({ text: 'Could not draw it: bad', urgent: true })
    expect(statusText({ kind: 'unavailable', tool: 'latex', message: '' }, 'LaTeX', t)).toEqual({ text: 'This server has no tool set up to draw LaTeX.', urgent: true })
  })
})

describe('what a face is drawn from', () => {
  const holder = () => ({
    renderings: { r1: def({ image: 'i1' }) },
    renderOutcomes: {},
    renderTypes: [{ type: 'latex', title: 'LaTeX' }],
    images: { i1: { format: 'svg', data: 'AA==' } },
  })
  const url = (a: { data: string }) => `u:${a.data}`
  it('has the picture, the type\'s name and a ready status', () => {
    const v = renderedView(holder(), { kind: 'rendered', ref: 'r1' }, url)!
    expect(v).toMatchObject({ src: 'u:AA==', label: 'LaTeX', status: { kind: 'ready' } })
  })
  it('has no picture while the asset has not come, and says it is being drawn', () => {
    const h = holder()
    h.images = {}
    expect(renderedView(h, { kind: 'rendered', ref: 'r1' }, url)).toMatchObject({ src: '', status: { kind: 'drawing' } })
  })
  it('is nothing for an object whose definition is not known', () => {
    expect(renderedView(holder(), { kind: 'rendered', ref: 'nope' }, url)).toBeNull()
    expect(renderedView(holder(), { kind: 'rendered', ref: null }, url)).toBeNull()
  })
  it('names an unknown type by its id', () => {
    const h = holder()
    h.renderTypes = []
    expect(renderedView(h, { kind: 'rendered', ref: 'r1' }, url)!.label).toBe('latex')
  })
})
