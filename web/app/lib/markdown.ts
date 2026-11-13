// "Save as Markdown": the text as it is now, without history, chat or authorship (an open format carries the state only).
import type { Block } from './blocks'

const PREFIX: Record<string, string> = {
  title: '# ',
  'heading-1': '## ',
  'heading-2': '### ',
  quote: '> ',
  remark: '> *Remark:* ',
}

function words(block: Block): string {
  if (block.style === 'definition') {
    const m = /^([^:]{1,60}):\s*(.*)$/.exec(block.text)
    return m ? `**${m[1]}**: ${m[2]}` : block.text
  }
  return `${PREFIX[block.style] ?? ''}${block.text}`
}

/** A list item: four spaces for each level (what every Markdown reader takes as nesting, under `-` and `1.` alike),
 * and the number the server counted, so a continued list reads `3.` and not `1.`. */
function line(block: Block): string {
  if (!block.item) return words(block)
  const counted = block.label?.path
  const marker = counted ? `${counted.at(-1)}.` : '-'
  return `${'    '.repeat(block.item.level)}${marker} ${words(block)}`
}

/** The paragraphs as Markdown, a blank line between them but not between the items of one list; a trailing empty
 * paragraph does not count. */
export function toMarkdown(blocks: Block[]): string {
  const shown = [...blocks]
  while (shown.length && !shown.at(-1)!.text) shown.pop()
  const out = shown.map((block, i) => {
    const before = shown[i - 1]
    const tight = !!block.item && before?.item?.list === block.item.list
    return (i === 0 ? '' : tight ? '\n' : '\n\n') + line(block)
  })
  return out.join('') + (shown.length ? '\n' : '')
}
