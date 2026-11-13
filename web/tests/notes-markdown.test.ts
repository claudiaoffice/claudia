import { describe, expect, it } from 'vitest'
import { parseNotes, type NoteLine } from '~/lib/notes-markdown'

const plain = (lines: NoteLine[]) => lines.map((l) => (l.blank ? '' : l.spans.map((s) => s.text).join('')))

describe('notes written in Markdown (D347)', () => {
  it('keeps a line for each line and one empty line for any number of blank ones', () => {
    expect(plain(parseNotes('Open with the story\nThen the numbers\n\n\n\nEnd'))).toEqual(['Open with the story', 'Then the numbers', '', 'End'])
  })
  it('has no lines for no notes', () => {
    expect(parseNotes('')).toEqual([])
  })
  it('reads strong and emphasis, both together too', () => {
    const [line] = parseNotes('Say **this** first, *then* ***both***')
    expect(line!.spans).toEqual([
      { text: 'Say ', bold: false, italic: false },
      { text: 'this', bold: true, italic: false },
      { text: ' first, ', bold: false, italic: false },
      { text: 'then', bold: false, italic: true },
      { text: ' ', bold: false, italic: false },
      { text: 'both', bold: true, italic: true },
    ])
  })
  it('takes underscores for emphasis but not inside a word', () => {
    const [line] = parseNotes('_slow_ and snake_case_name')
    expect(line!.spans.map((s) => [s.text, s.italic])).toEqual([['slow', true], [' and snake_case_name', false]])
  })
  it('leaves a mark that never closes as it is', () => {
    expect(plain(parseNotes('5 * 3 and **open'))).toEqual(['5 * 3 and **open'])
  })
  it('lets a backslash make a mark literal', () => {
    const [line] = parseNotes('2 \\* 3 \\*\\*not bold\\*\\*')
    expect(plain([line!])).toEqual(['2 * 3 **not bold**'])
    expect(line!.spans.every((s) => !s.bold)).toBe(true)
  })
  it('shows a heading as a bold line', () => {
    const [heading, text] = parseNotes('## Opening\nthen text')
    expect(heading).toMatchObject({ heading: true })
    expect(heading!.spans).toEqual([{ text: 'Opening', bold: true, italic: false }])
    expect(text!.heading).toBeFalsy()
  })
  it('reads bullets and numbers with their level, two spaces for each', () => {
    const lines = parseNotes('- one\n* two\n  - nested\n1. first\n2) second')
    expect(lines.map((l) => [l.marker, l.level, plain([l])[0]])).toEqual([
      ['•', 0, 'one'],
      ['•', 0, 'two'],
      ['•', 1, 'nested'],
      ['1.', 0, 'first'],
      ['2)', 0, 'second'],
    ])
  })
  it('keeps a quote, and says so', () => {
    expect(parseNotes('> careful here')[0]).toMatchObject({ quote: true })
  })
  it('keeps code as it is: a span in a line, or whole lines in a fence', () => {
    const [inline, , a, b] = parseNotes('run `make *all*` then\n\n```\nx = *1*\ny\n```')
    expect(inline!.spans.map((s) => [s.text, !!s.code])).toEqual([['run ', false], ['make *all*', true], [' then', false]])
    expect([a, b].map((l) => [plain([l!])[0], l!.fenced])).toEqual([['x = *1*', true], ['y', true]])
  })
  it('shows a link as its words and gives the address, never as something to click on', () => {
    const [line] = parseNotes('see [the **plan**](https://example.org/plan) now')
    expect(line!.spans.map((s) => s.text)).toEqual(['see ', 'the ', 'plan', ' now'])
    expect(line!.spans.find((s) => s.text === 'plan')).toMatchObject({ bold: true, href: 'https://example.org/plan' })
    expect(line!.spans.find((s) => s.text === 'the ')).toMatchObject({ href: 'https://example.org/plan' })
  })
  it('shows a picture as its description: notes carry no pictures', () => {
    expect(plain(parseNotes('![a chart](https://example.org/c.png)'))).toEqual(['a chart'])
  })
  it('does not read HTML: it is text', () => {
    const [line] = parseNotes('<b onclick="x()">hi</b> <script>alert(1)</script>')
    expect(line!.spans.map((s) => s.text).join('')).toBe('<b onclick="x()">hi</b> <script>alert(1)</script>')
  })
})
