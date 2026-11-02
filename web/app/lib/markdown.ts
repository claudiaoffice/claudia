// "Save as Markdown": the text as it is now, without history, chat or authorship (an open format carries the state only).
import type { Block } from './blocks'

const PREFIX: Record<string, string> = {
  title: '# ',
  'heading-1': '## ',
  'heading-2': '### ',
  quote: '> ',
  remark: '> *Remark:* ',
}

function line(block: Block): string {
  if (block.style === 'definition') {
    const m = /^([^:]{1,60}):\s*(.*)$/.exec(block.text)
    return m ? `**${m[1]}**: ${m[2]}` : block.text
  }
  return `${PREFIX[block.style] ?? ''}${block.text}`
}

/** The paragraphs as Markdown, a blank line between them; a trailing empty paragraph does not count. */
export function toMarkdown(blocks: Block[]): string {
  const shown = [...blocks]
  while (shown.length && !shown.at(-1)!.text) shown.pop()
  return shown.map(line).join('\n\n') + (shown.length ? '\n' : '')
}
