// A help topic is Markdown (`claudia_server/help.py`, D76) written in lines of about 120 characters, as the files are
// kept; the Help tab used to show it as it was, with its `**` and `##` and the line breaks in the middle of sentences.
// It is read here the way the speaker notes are (`notes-markdown.ts`, D347): paragraphs, strong and emphasis, bullets
// and numbers, headings, quotes, links, code, and never HTML, so a topic someone wrote cannot put markup, a picture or a
// script on the screen. The one difference is that a line break inside a paragraph is a space, as Markdown says, so that
// a paragraph wraps to the width of the panel and not to the width of the file.
import { parseNotes, type NoteLine } from './notes-markdown'

const HEADING = /^#{1,6}\s/
const LIST = /^\s*([-*+]|\d+[.)])\s/
const FENCE = /^\s*```/

/** The text with each paragraph on one line: a line that goes on from the one before it is joined to it with a space.
 * A heading, a list item, a quote, a code fence, and anything in a fence, starts a line of its own. */
export function joinSoftBreaks(markdown: string): string {
  const out: string[] = []
  let fence = false
  let open = false // the last line out is a paragraph (or an item or a quote) that a plain line goes on from
  for (const raw of markdown.replace(/\r\n/g, '\n').split('\n')) {
    const text = raw.trimEnd()
    if (FENCE.test(text)) {
      fence = !fence
      out.push(raw)
      open = false
    } else if (fence) out.push(raw)
    else if (!text.trim()) {
      out.push('')
      open = false
    } else if (open && !HEADING.test(text) && !LIST.test(text) && !text.startsWith('>')) out[out.length - 1] += ' ' + text.trim()
    else {
      out.push(text)
      open = !HEADING.test(text)
    }
  }
  return out.join('\n')
}

/** A help topic's body as lines to draw (the same lines as the speaker notes). */
export function parseHelp(markdown: string): NoteLine[] {
  return parseNotes(joinSoftBreaks(markdown))
}
