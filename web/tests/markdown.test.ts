import { describe, expect, it } from 'vitest'
import type { Block } from '~/lib/blocks'
import { toMarkdown } from '~/lib/markdown'

const block = (style: string, text: string): Block => ({ id: 'b', style, text, runs: [] })

describe('markdown', () => {
  it('writes styles as what they are', () => {
    const md = toMarkdown([
      block('title', 'Essay'),
      block('heading-1', 'Part'),
      block('body', 'Words.'),
      block('quote', 'Said.'),
      block('remark', 'Check this'),
      block('definition', 'Term: what it means'),
    ])
    expect(md).toBe('# Essay\n\n## Part\n\nWords.\n\n> Said.\n\n> *Remark:* Check this\n\n**Term**: what it means\n')
  })

  it('leaves out empty paragraphs at the end, and is empty for an empty text', () => {
    expect(toMarkdown([block('body', 'a'), block('body', '')])).toBe('a\n')
    expect(toMarkdown([block('body', '')])).toBe('')
  })
})
