// "Save as Markdown": the text as it is now, without history, chat or authorship (an open format carries the state only).
import type { Block } from './blocks'
import { headingLevel, type StyleView } from './style-css'

const PREFIX: Record<string, string> = {
  quote: '> ',
  remark: '> *Remark:* ',
}
/** Markdown has six levels of heading; the title takes the first (E9.22). */
const DEEPEST = 6

function words(block: Block, styles: readonly StyleView[]): string {
  const level = headingLevel(styles, block.style)
  if (level !== null) return `${'#'.repeat(Math.min(level + 1, DEEPEST))} ${block.text}`
  if (block.style === 'definition') {
    const m = /^([^:]{1,60}):\s*(.*)$/.exec(block.text)
    return m ? `**${m[1]}**: ${m[2]}` : block.text
  }
  return `${PREFIX[block.style] ?? ''}${block.text}`
}

/** A list item: four spaces for each level (what every Markdown reader takes as nesting, under `-` and `1.` alike),
 * and the number the server counted, so a continued list reads `3.` and not `1.`. */
function line(block: Block, styles: readonly StyleView[]): string {
  if (!block.item) return words(block, styles)
  const counted = block.label?.path
  const marker = counted ? `${counted.at(-1)}.` : '-'
  return `${'    '.repeat(block.item.level)}${marker} ${words(block, styles)}`
}

/** The paragraphs as Markdown, a blank line between them but not between the items of one list; a trailing empty
 * paragraph does not count. `styles` say which paragraphs are headings, and of which level. */
export function toMarkdown(blocks: Block[], styles: readonly StyleView[]): string {
  const shown = [...blocks]
  while (shown.length && !shown.at(-1)!.text) shown.pop()
  const out = shown.map((block, i) => {
    const before = shown[i - 1]
    const tight = !!block.item && before?.item?.list === block.item.list
    return (i === 0 ? '' : tight ? '\n' : '\n\n') + line(block, styles)
  })
  return out.join('') + (shown.length ? '\n' : '')
}
