// A help topic is Markdown written in lines of 120 characters; the Help tab shows it as paragraphs, not as the file.
import { describe, expect, it } from 'vitest'
import { joinSoftBreaks, parseHelp } from '~/lib/help-markdown'

const text = (line: { spans: { text: string }[] }) => line.spans.map((s) => s.text).join('')

describe('a paragraph written over several lines', () => {
  it('is one line, joined with spaces, as Markdown says', () => {
    expect(joinSoftBreaks('Type what you are\nlooking for and\nthe matches show.')).toBe('Type what you are looking for and the matches show.')
  })

  it('stays apart from the next paragraph', () => {
    expect(joinSoftBreaks('One\ntwo.\n\nThree\nfour.')).toBe('One two.\n\nThree four.')
  })

  it('does not join a heading to the paragraph before or after it', () => {
    expect(joinSoftBreaks('Before it.\n## Where it looks\nThe switches\nunder it.')).toBe('Before it.\n## Where it looks\nThe switches under it.')
  })

  it('keeps list items apart and joins what goes on under an item to it', () => {
    expect(joinSoftBreaks('- first\n  goes on\n- second\n1. one\n2. two')).toBe('- first goes on\n- second\n1. one\n2. two')
  })

  it('keeps quote lines apart', () => {
    expect(joinSoftBreaks('> a\n> b')).toBe('> a\n> b')
  })

  it('leaves a code fence exactly as it was', () => {
    expect(joinSoftBreaks('```\nline one\n  line two\n```\nafter')).toBe('```\nline one\n  line two\n```\nafter')
  })

  it('reads Windows line ends', () => {
    expect(joinSoftBreaks('a\r\nb\r\n\r\nc')).toBe('a b\n\nc')
  })
})

describe('a help topic as lines to draw', () => {
  const lines = parseHelp(
    ['**Edit ▸ Search & Replace…** (Ctrl+F) opens a panel', 'over the text.', '', '## Where it looks', '', 'The switches under **Look in** say what.', '', '- one', '- two'].join('\n'),
  )

  it('turns the strong marks into bold and drops the asterisks', () => {
    const first = lines[0]!
    expect(text(first)).toBe('Edit ▸ Search & Replace… (Ctrl+F) opens a panel over the text.')
    expect(first.spans[0]).toMatchObject({ bold: true, text: 'Edit ▸ Search & Replace…' })
  })

  it('makes a heading of a line with hashes, without the hashes', () => {
    const heading = lines.find((l) => l.heading)!
    expect(text(heading)).toBe('Where it looks')
    expect(heading.spans.every((s) => s.bold)).toBe(true)
  })

  it('makes bullets', () => {
    expect(lines.filter((l) => l.marker).map((l) => [l.marker, text(l)])).toEqual([
      ['•', 'one'],
      ['•', 'two'],
    ])
  })

  it('never lets markup through: it is text', () => {
    const [line] = parseHelp('<script>alert(1)</script> and <b>bold</b>')
    expect(text(line!)).toBe('<script>alert(1)</script> and <b>bold</b>')
  })

  it('shows what a picture says and where a link goes', () => {
    const [line] = parseHelp('See [the guide](https://example.org/a) ![a cat](x.png)')
    expect(text(line!)).toBe('See the guide a cat')
    expect(line!.spans.find((s) => s.href)?.href).toBe('https://example.org/a')
  })
})
