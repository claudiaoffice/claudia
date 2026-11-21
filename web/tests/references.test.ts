// References as the clients know them (step H): a field at one U+FFFC, what it reads as, and the picker's sums.
import { describe, expect, it } from 'vitest'
import { applyEvent, type Paragraph } from '~/lib/paragraphs'
import { defaultShow, fieldIndex, grouped, partsOf, plain, preview, readAs, type ReferenceTarget } from '~/lib/references'
import { showLabel } from '~/lib/reference-labels'

const F = '￼'
const target = (over: Partial<ReferenceTarget>): ReferenceTarget => ({ id: 'h', kind: 'heading', level: 1, number: '2.1', text: 'Two sites', name: null, ...over })

describe('a paragraph with references', () => {
  it('finds the index of a field, cuts words at fields and reads them as what they show', () => {
    expect(fieldIndex(`a${F}b${F}c`, 3)).toBe(1)
    expect(partsOf(`see ${F}.`)).toEqual([
      { kind: 'words', text: 'see ', start: 0 },
      { kind: 'field', index: 0, start: 4 },
      { kind: 'words', text: '.', start: 5 },
    ])
    expect(partsOf(`${F}`, 10, 2)).toEqual([{ kind: 'field', index: 2, start: 10 }])
    expect(readAs(`see ${F} and ${F}`, [{ text: '2.1', state: 'ok' }, { text: '', state: 'page' }])).toBe('see 2.1 and #')
    expect(plain(`a${F}b`)).toBe('ab')
  })

  it('follows the server: the fields of a paragraph, what they read as, and splits and joins that share them out', () => {
    const paragraphs: Paragraph[] = [{ id: 'b1', style: 'body', text: `x${F}y${F}`, runs: [[4, 'ann', null]] }, { id: 'b2', style: 'body', text: 'z', runs: [[1, 'ann', null]] }]
    applyEvent(paragraphs, { type: 'paragraph_fields', paragraph: 'b1', fields: [{ kind: 'ref', target: 'h1', show: 'number' }, { kind: 'ref', target: 'h2', show: 'text' }] })
    applyEvent(paragraphs, { type: 'fields', paragraph: 'b1', fields: [{ text: '1', state: 'ok' }, { text: 'Two', state: 'ok' }] })
    expect(applyEvent(paragraphs, { type: 'fields', paragraph: 'gone', fields: [] })).toBe(true)
    applyEvent(paragraphs, { type: 'split', paragraph: 'b1', offset: 2, new_id: 'b9', style: 'body' })
    expect(paragraphs[0]!.fields?.map((f) => f.target)).toEqual(['h1'])
    expect(paragraphs[1]!.fields?.map((f) => f.target)).toEqual(['h2'])
    expect(paragraphs[1]!.shown?.map((s) => s.text)).toEqual(['Two'])
    applyEvent(paragraphs, { type: 'join', paragraph: 'b9', into: 'b1', at: 2 })
    expect(paragraphs[0]!.fields?.map((f) => f.target)).toEqual(['h1', 'h2'])
  })
})

describe('the picker', () => {
  it('shows a number by default where there is one, groups the targets and previews what a reference reads as', () => {
    expect(defaultShow(target({}))).toBe('number')
    expect(defaultShow(target({ number: null }))).toBe('text')
    expect(defaultShow(target({ kind: 'named', number: null, text: '', name: 'figure 1' }))).toBe('name')
    const groups = grouped([target({ kind: 'item', id: 'i' }), target({}), target({ kind: 'named', id: 'n' })])
    expect(groups.map((g) => g.kind)).toEqual(['heading', 'item', 'named'])
    expect(preview(target({}), 'number-text')).toBe('2.1 Two sites')
    expect(preview(target({ number: null }), 'number')).toBe('Two sites')
    expect(preview(target({}), 'page')).toBe('#')
    expect(preview(target({ name: 'Plan' }), 'name')).toBe('Plan')
    expect(preview(target({}), 'text')).toBe('Two sites')
    expect(['number', 'text', 'number-text', 'page', 'name'].map((s) => showLabel(s as never))).toEqual(['Number', 'Text', 'Number and Text', 'Page', 'Name'])
  })
})
