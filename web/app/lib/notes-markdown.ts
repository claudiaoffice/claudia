// The speaker notes of a slide are Markdown (D342), read the same small way everywhere (D347): paragraphs, strong and
// emphasis, bullets and numbers (two spaces a level), headings (shown as bold lines), block quotes, links, code. It is
// never HTML: the notes are turned into lines of spans and the component draws those, so what a colleague wrote cannot
// put markup, a picture or a script on someone's screen. A link shows its words and its address and is not
// something to click during a talk; a picture shows its description.
//
// The same rules as `claudia_creates_io/_notes.py` (which writes the notes into pptx and odp), so a note reads the
// same in the presenter view and in the file.

export interface Span {
  text: string
  bold: boolean
  italic: boolean
  code?: boolean
  /** Where a link goes; shown, not followed. */
  href?: string
}

export interface NoteLine {
  blank?: boolean
  spans: Span[]
  /** `•` or `1.`: the mark of a list item. */
  marker?: string
  /** How deep a list item is nested, 0 at the top. */
  level: number
  heading?: boolean
  quote?: boolean
  /** A line of a fenced code block: shown as it is. */
  fenced?: boolean
}

const ESCAPABLE = '\\`*_{}[]()#+-.!>|~'
const LINK = /^\[([^\]]*)\]\(([^)\s]*)\)/
const IMAGE = /^!\[([^\]]*)\]\(([^)\s]*)\)/

const span = (text: string, bold = false, italic = false, extra: Partial<Span> = {}): Span => ({ text, bold, italic, ...extra })

function merged(spans: Span[]): Span[] {
  const out: Span[] = []
  for (const s of spans) {
    if (!s.text) continue
    const last = out.at(-1)
    if (last && last.bold === s.bold && last.italic === s.italic && !last.code && !s.code && last.href === s.href) last.text += s.text
    else out.push({ ...s })
  }
  return out
}

type Look = { bold: boolean; italic: boolean }

/** Do the marks at `i` open or close emphasis? How long they are and which looks they flip, or null if they are just
 * characters (`5 * 3`, `snake_case`, a mark that never closes). */
function emphasis(text: string, i: number, state: Look): { length: number; kinds: (keyof Look)[] } | null {
  const mark = text[i]!
  let run = 0
  while (text[i + run] === mark) run++
  const length = run === 3 ? 3 : run >= 2 ? 2 : 1
  const kinds: (keyof Look)[] = length === 3 ? ['bold', 'italic'] : length === 2 ? ['bold'] : ['italic']
  const before = i > 0 ? text[i - 1]! : ' '
  const after = i + length < text.length ? text[i + length]! : ' '
  const alnum = (c: string) => /[\p{L}\p{N}]/u.test(c)
  if (kinds.every((k) => state[k])) {
    if (/\s/.test(before) || (mark === '_' && alnum(after))) return null
  } else if (!kinds.some((k) => state[k])) {
    if (/\s/.test(after) || (mark === '_' && alnum(before)) || !closes(text, i + length, mark.repeat(length))) return null
  } else return null
  return { length, kinds }
}

function closes(text: string, start: number, marks: string): boolean {
  let at = text.indexOf(marks, start)
  while (at >= 0) {
    const after = at + marks.length < text.length ? text[at + marks.length]! : ' '
    if (at > start && !/\s/.test(text[at - 1]!) && !(marks[0] === '_' && /[\p{L}\p{N}]/u.test(after))) return true
    at = text.indexOf(marks, at + marks.length)
  }
  return false
}

/** The spans of one line's words: emphasis made into looks, escapes undone, links and code kept apart. */
function inline(text: string, look: Look = { bold: false, italic: false }, extra: Partial<Span> = {}): Span[] {
  const spans: Span[] = []
  const state = { ...look }
  let buffer = ''
  const flush = () => {
    spans.push(span(buffer, state.bold, state.italic, extra))
    buffer = ''
  }
  let i = 0
  while (i < text.length) {
    const char = text[i]!
    const rest = text.slice(i)
    let found: RegExpExecArray | null
    if (char === '\\' && i + 1 < text.length && ESCAPABLE.includes(text[i + 1]!)) {
      buffer += text[i + 1]
      i += 2
    } else if (char === '`' && text.indexOf('`', i + 1) > i) {
      const end = text.indexOf('`', i + 1)
      flush()
      spans.push(span(text.slice(i + 1, end), state.bold, state.italic, { ...extra, code: true }))
      i = end + 1
    } else if (char === '!' && (found = IMAGE.exec(rest))) {
      buffer += found[1]
      i += found[0].length
    } else if (char === '[' && (found = LINK.exec(rest))) {
      flush()
      spans.push(...inline(found[1]!, state, found[2] ? { ...extra, href: found[2] } : extra))
      i += found[0].length
    } else if ((char === '*' || char === '_') && emphasis(text, i, state)) {
      const { length, kinds } = emphasis(text, i, state)!
      flush()
      for (const k of kinds) state[k] = !state[k]
      i += length
    } else {
      buffer += char
      i++
    }
  }
  flush()
  return merged(spans)
}

function block(text: string): NoteLine {
  let found: RegExpExecArray | null
  if ((found = /^#{1,6}\s+(.*)$/.exec(text))) {
    return { spans: inline(found[1]!).map((s) => ({ ...s, bold: true })), level: 0, heading: true }
  }
  if ((found = /^(\s*)[-*+]\s+(.*)$/.exec(text))) return { spans: inline(found[2]!), marker: '•', level: Math.floor(found[1]!.length / 2) }
  if ((found = /^(\s*)(\d+[.)])\s+(.*)$/.exec(text))) return { spans: inline(found[3]!), marker: found[2]!, level: Math.floor(found[1]!.length / 2) }
  if (text.startsWith('>')) return { spans: inline(text.slice(1).replace(/^ /, '')), level: 0, quote: true }
  return { spans: inline(text), level: 0 }
}

/** The notes as lines to draw: one for each line of the text, one empty line for any run of blank ones, none at the
 * start or the end. */
export function parseNotes(markdown: string): NoteLine[] {
  const lines: NoteLine[] = []
  let fence = false
  for (const raw of markdown.split('\n')) {
    const text = raw.trimEnd()
    if (text.trimStart().startsWith('```')) fence = !fence
    else if (fence) lines.push({ spans: [span(raw, false, false, { code: true })], level: 0, fenced: true })
    else if (!text.trim()) {
      if (lines.length && !lines.at(-1)!.blank) lines.push({ blank: true, spans: [], level: 0 })
    } else lines.push(block(text))
  }
  while (lines.at(-1)?.blank) lines.pop()
  return lines
}
