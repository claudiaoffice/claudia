// The numbering a client works out (E9.22): the manager's preview, whether the headings are numbered, what a scheme is
// used by, and the choices of the style editor's Numbering row. The document's markers are the server's.
import { describe, expect, it } from 'vitest'
import { headingsNumbered, hasHeadingStyles, markerOf, numberingChoices, numberingValue, usersOf, type SchemeInfo } from '~/lib/numbering'

const level = (format: SchemeInfo['levels'][number]['format'], from_level: number, after = '', before = '') => ({ format, bullet: '•', before, after, from_level })
const CHAPTERS: SchemeInfo = { id: 'chapters', name: 'Chapters', kind: 'number', indent: 1.6, gap: 0.25, levels: Array.from({ length: 9 }, () => level('decimal', 0)) }
const NUMBERS: SchemeInfo = { id: 'numbers', name: 'Numbers', kind: 'number', indent: 1.6, gap: 0.25, levels: Array.from({ length: 9 }, (_, k) => level((['decimal', 'lower-alpha', 'lower-roman'] as const)[k % 3]!, k, '.')) }

describe('the preview of a scheme', () => {
  it('draws the trail or the level’s own counter, as the server does', () => {
    expect([markerOf(CHAPTERS, [2]), markerOf(CHAPTERS, [2, 3]), markerOf(CHAPTERS, [2, 3, 1])]).toEqual(['2', '2.3', '2.3.1'])
    expect([markerOf(NUMBERS, [4]), markerOf(NUMBERS, [4, 2]), markerOf(NUMBERS, [4, 2, 9])]).toEqual(['4.', 'b.', 'ix.'])
    const parts: SchemeInfo = { ...CHAPTERS, levels: [level('upper-roman', 0, ':', 'Part '), ...CHAPTERS.levels.slice(1)] }
    expect(markerOf(parts, [4])).toBe('Part IV:')
    expect(markerOf({ ...CHAPTERS, levels: [level('bullet', 0), ...CHAPTERS.levels.slice(1)] }, [3])).toBe('•')
  })
})

describe('numbered headings', () => {
  const styles = [
    { id: 'title', name: 'Title', heading: 0, numbered: 'outline' },
    { id: 'h1', name: 'Heading 1', heading: 1, numbering: 'outline', numbered: 'outline' },
    { id: 'h2', name: 'Heading 2', heading: 2, numbered: 'outline', based_on: 'h1' },
    { id: 'body', name: 'Body', heading: null, numbered: null },
  ]
  const lists = [{ id: 'outline', scheme: 'chapters', start: 1, name: 'Outline' }]

  it('are numbered when a style of level 1 or more numbers its paragraphs; the title does not count', () => {
    expect(headingsNumbered(styles)).toBe(true)
    expect(headingsNumbered([styles[0]!, styles[3]!])).toBe(false)
    expect(hasHeadingStyles([styles[0]!, styles[3]!])).toBe(false)
  })

  it('say what uses a scheme, so a change is never a surprise', () => {
    expect(usersOf('chapters', lists, styles)).toEqual({ lists, styles: [styles[1]] })
    expect(usersOf('numbers', lists, styles)).toEqual({ lists: [], styles: [] })
  })

  it('offer as-the-parent, not numbered and every list in the style editor', () => {
    const choices = numberingChoices(styles[2]!, styles, lists, [CHAPTERS], (text, values) => text.replace(/\{(\w+)\}/g, (_, k) => String(values?.[k])))
    expect(choices.map((c) => c.value)).toEqual(['inherit', 'none', 'outline'])
    expect(choices[0]!.label).toBe('As “Heading 1”: Outline · Chapters')
    expect(numberingValue(styles[2]!)).toBe('inherit')
    expect(numberingValue(styles[1]!)).toBe('outline')
  })
})
