// "Save as Markdown": the text as it is now, without history, chat or authorship (an open format carries the state only).
import type { Paragraph } from './paragraphs'
import { headingLevel, type StyleView } from './style-css'

const PREFIX: Record<string, string> = {
  quote: '> ',
  remark: '> *Remark:* ',
}
/** Markdown has six levels of heading; the title takes the first (E9.22). */
const DEEPEST = 6

function words(paragraph: Paragraph, styles: readonly StyleView[]): string {
  const level = headingLevel(styles, paragraph.style)
  if (level !== null) return `${'#'.repeat(Math.min(level + 1, DEEPEST))} ${paragraph.text}`
  if (paragraph.style === 'definition') {
    const m = /^([^:]{1,60}):\s*(.*)$/.exec(paragraph.text)
    return m ? `**${m[1]}**: ${m[2]}` : paragraph.text
  }
  return `${PREFIX[paragraph.style] ?? ''}${paragraph.text}`
}

/** A list item: four spaces for each level (what every Markdown reader takes as nesting, under `-` and `1.` alike),
 * and the number the server counted, so a continued list reads `3.` and not `1.`. */
function line(paragraph: Paragraph, styles: readonly StyleView[]): string {
  if (!paragraph.item) return words(paragraph, styles)
  const counted = paragraph.label?.path
  const marker = counted ? `${counted.at(-1)}.` : '-'
  return `${'    '.repeat(paragraph.item.level)}${marker} ${words(paragraph, styles)}`
}

/** The paragraphs as Markdown, a blank line between them but not between the items of one list; a trailing empty
 * paragraph does not count. `styles` say which paragraphs are headings, and of which level. */
export function toMarkdown(paragraphs: Paragraph[], styles: readonly StyleView[]): string {
  const shown = [...paragraphs]
  while (shown.length && !shown.at(-1)!.text) shown.pop()
  const out = shown.map((paragraph, i) => {
    const before = shown[i - 1]
    const tight = !!paragraph.item && before?.item?.list === paragraph.item.list
    return (i === 0 ? '' : tight ? '\n' : '\n\n') + line(paragraph, styles)
  })
  return out.join('') + (shown.length ? '\n' : '')
}
