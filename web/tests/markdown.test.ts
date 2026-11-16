import { describe, expect, it } from 'vitest'
import type { Block } from '~/lib/blocks'
import { toMarkdown } from '~/lib/markdown'
import type { StyleView } from '~/lib/style-css'

const block = (style: string, text: string): Block => ({ id: 'b', style, text, runs: [] })
// The heading level is the server's word for each style (E9.22); Markdown writes it, it does not guess it from a name.
const level = (id: string, heading: number | null) => ({ id, heading }) as unknown as StyleView
const STYLES = [level('title', 0), level('heading-1', 1), level('chapter', 3), level('deep', 8), level('body', null)]
const md = (blocks: Block[]) => toMarkdown(blocks, STYLES)

describe('markdown', () => {
  it('writes styles as what they are', () => {
    const out = md([
      block('title', 'Essay'),
      block('heading-1', 'Part'),
      block('body', 'Words.'),
      block('quote', 'Said.'),
      block('remark', 'Check this'),
      block('definition', 'Term: what it means'),
    ])
    expect(out).toBe('# Essay\n\n## Part\n\nWords.\n\n> Said.\n\n> *Remark:* Check this\n\n**Term**: what it means\n')
  })

  it('writes any heading by its level, the title as the one top heading, and a level deeper than Markdown has as its deepest', () => {
    expect(md([block('chapter', 'Methods'), block('deep', 'Detail')])).toBe('#### Methods\n\n###### Detail\n')
  })

  it('leaves out empty paragraphs at the end, and is empty for an empty text', () => {
    expect(md([block('body', 'a'), block('body', '')])).toBe('a\n')
    expect(md([block('body', '')])).toBe('')
  })
})

describe('markdown lists (E9.21)', () => {
  const item = (text: string, list: string, level: number, label: { marker: string; path: number[] | null }, style = 'body'): Block => ({
    ...block(style, text),
    item: { list, level },
    label,
  })
  const dot = { marker: '•', path: null }
  const num = (...path: number[]) => ({ marker: `${path.at(-1)}.`, path })

  it('writes bullets and numbers as a tight list, four spaces for each level, with the numbers the server counted', () => {
    const out = md([
      block('body', 'Intro'),
      item('one', 'l1', 0, num(1)),
      item('inner', 'l1', 1, num(1, 1)),
      item('two', 'l1', 0, num(2)),
      block('body', 'After'),
      item('dot', 'l2', 0, dot),
      item('sub', 'l2', 1, dot),
    ])
    expect(out).toBe('Intro\n\n1. one\n    1. inner\n2. two\n\nAfter\n\n- dot\n    - sub\n')
  })

  it('writes the number of a continued list as it is shown, not as 1', () => {
    expect(md([item('three', 'l1', 0, num(3)), item('four', 'l1', 0, num(4))])).toBe('3. three\n4. four\n')
  })

  it('keeps two neighbouring lists apart with a blank line', () => {
    expect(md([item('a', 'l1', 0, num(1)), item('b', 'l2', 0, num(1))])).toBe('1. a\n\n1. b\n')
  })

  it('an item keeps what its style says it is', () => {
    expect(md([item('said', 'l1', 0, dot, 'quote')])).toBe('- > said\n')
  })

  it('an item the server has not counted yet is a bullet, and an empty last item is left out like any empty paragraph', () => {
    const uncounted: Block = { ...block('body', 'new'), item: { list: 'l1', level: 0 } }
    expect(md([uncounted, item('', 'l1', 0, num(2))])).toBe('- new\n')
  })
})

