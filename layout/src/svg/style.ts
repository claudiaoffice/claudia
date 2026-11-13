/**
 * The style of SVG elements: presentation attributes (`fill="red"`), rules of `<style>` elements, and `style`
 * attributes, in that order of strength, with the inherited properties passed down.
 *
 * Rules are understood with simple selectors only: a type, a class, an id, the universal selector and combinations
 * of them (`rect.big`), in lists (`a, b`). A rule with any other selector (descendants, attributes,
 * pseudo-classes) is left out, and the caller is told so.
 *
 * @module
 */
import type { XmlElement } from './xml'

/** The properties the drawing understands, and whether a child takes its parent's value. */
const PROPERTIES: Record<string, boolean> = {
  fill: true,
  'fill-opacity': true,
  'fill-rule': true,
  stroke: true,
  'stroke-width': true,
  'stroke-opacity': true,
  'stroke-linecap': true,
  'stroke-linejoin': true,
  'stroke-miterlimit': true,
  'stroke-dasharray': true,
  'stroke-dashoffset': true,
  color: true,
  'font-family': true,
  'font-size': true,
  'font-weight': true,
  'font-style': true,
  'text-anchor': true,
  visibility: true,
  'clip-rule': true,
  opacity: false,
  display: false,
  'clip-path': false,
  mask: false,
  filter: false,
  'stop-color': false,
  'stop-opacity': false,
  'marker-start': true,
  'marker-mid': true,
  'marker-end': true,
}

export type Style = Readonly<Record<string, string>>

/** The initial values (SVG 1.1): what the root starts from. */
export const INITIAL: Style = {
  fill: 'black',
  'fill-opacity': '1',
  'fill-rule': 'nonzero',
  stroke: 'none',
  'stroke-width': '1',
  'stroke-opacity': '1',
  'stroke-linecap': 'butt',
  'stroke-linejoin': 'miter',
  'stroke-miterlimit': '4',
  'stroke-dasharray': 'none',
  'stroke-dashoffset': '0',
  color: 'black',
  'font-family': 'sans-serif',
  'font-size': '16',
  'font-weight': 'normal',
  'font-style': 'normal',
  'text-anchor': 'start',
  visibility: 'visible',
  'clip-rule': 'nonzero',
}

interface Rule {
  selector: { type: string | null; ids: string[]; classes: string[] }
  specificity: number
  order: number
  declarations: [string, string][]
}

/** The rules of an SVG's `<style>` elements. */
export class StyleSheet {
  private readonly rules: Rule[] = []
  /** at least one rule had a selector that is not understood */
  skipped = false

  add(css: string): void {
    const text = css.replace(/\/\*[\s\S]*?\*\//g, ' ')
    let i = 0
    while (i < text.length) {
      const open = text.indexOf('{', i)
      if (open < 0) break
      const head = text.slice(i, open).trim()
      // find the matching close (an @-rule like @media holds blocks of its own)
      let depth = 1
      let j = open + 1
      while (j < text.length && depth) {
        if (text[j] === '{') depth++
        else if (text[j] === '}') depth--
        j++
      }
      const body = text.slice(open + 1, j - 1)
      i = j
      if (head.startsWith('@')) {
        this.skipped ||= !/^@(font-face|charset|namespace)/i.test(head)
        continue
      }
      const declarations = parseDeclarations(body)
      for (const part of head.split(',')) {
        const selector = parseSelector(part.trim())
        if (!selector) {
          this.skipped = true
          continue
        }
        const specificity = selector.ids.length * 10000 + selector.classes.length * 100 + (selector.type ? 1 : 0)
        this.rules.push({ selector, specificity, order: this.rules.length, declarations })
      }
    }
  }

  /** The declarations of the rules that match `el`, weakest first. */
  matching(el: XmlElement): [string, string][] {
    if (!this.rules.length) return []
    const id = el.attrs.get('id')
    const classes = (el.attrs.get('class') ?? '').split(/\s+/).filter(Boolean)
    return this.rules
      .filter(({ selector: s }) => (!s.type || s.type === el.name) && s.ids.every((x) => x === id) && s.classes.every((c) => classes.includes(c)))
      .sort((a, b) => a.specificity - b.specificity || a.order - b.order)
      .flatMap((r) => r.declarations)
  }
}

function parseSelector(text: string): Rule['selector'] | null {
  const m = /^(\*|[A-Za-z][\w-]*)?((?:[.#][\w-]+)*)$/.exec(text)
  if (!m || (!m[1] && !m[2])) return null
  const ids: string[] = []
  const classes: string[] = []
  for (const part of m[2]!.match(/[.#][\w-]+/g) ?? []) (part[0] === '#' ? ids : classes).push(part.slice(1))
  return { type: m[1] && m[1] !== '*' ? m[1] : null, ids, classes }
}

/** `a: b; c: d` as pairs, names in lower case, `!important` dropped. */
export function parseDeclarations(text: string): [string, string][] {
  const out: [string, string][] = []
  for (const part of text.split(';')) {
    const colon = part.indexOf(':')
    if (colon < 0) continue
    const name = part.slice(0, colon).trim().toLowerCase()
    const value = part.slice(colon + 1).replace(/!important/i, '').trim()
    if (name && value) out.push([name, value])
  }
  return out
}

/** The style of `el`, from its parent's computed style. */
export function computeStyle(el: XmlElement, parent: Style, sheet: StyleSheet): Style {
  const own: Record<string, string> = {}
  for (const [k, v] of el.attrs) if (k in PROPERTIES) own[k] = v.trim()
  for (const [k, v] of sheet.matching(el)) if (k in PROPERTIES) own[k] = v
  const inline = el.attrs.get('style')
  if (inline) for (const [k, v] of parseDeclarations(inline)) if (k in PROPERTIES) own[k] = v
  const out: Record<string, string> = {}
  for (const [k, inherited] of Object.entries(PROPERTIES)) {
    const v = own[k]
    if (v !== undefined && v !== 'inherit') out[k] = v
    else if ((inherited || v === 'inherit') && parent[k] !== undefined) out[k] = parent[k]!
  }
  // the font size in user units (px), so that children and lengths in em can use it
  if (own['font-size'] && own['font-size'] !== 'inherit') {
    const base = Number.parseFloat(parent['font-size'] ?? '16') || 16
    out['font-size'] = String(fontSizePx(own['font-size'], base) ?? base)
  }
  return out
}

const FONT_KEYWORDS: Record<string, number> = { 'xx-small': 9, 'x-small': 10, small: 13, medium: 16, large: 18, 'x-large': 24, 'xx-large': 32 }

/** A font size in user units (px), relative to `base` for em, % and the relative keywords. */
function fontSizePx(value: string, base: number): number | null {
  const v = value.trim().toLowerCase()
  if (v in FONT_KEYWORDS) return FONT_KEYWORDS[v]!
  if (v === 'larger') return base * 1.2
  if (v === 'smaller') return base / 1.2
  const m = /^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)(px|pt|pc|mm|cm|in|em|ex|rem|%)?$/.exec(v)
  if (!m) return null
  const per: Record<string, number> = { px: 1, pt: 4 / 3, pc: 16, mm: 96 / 25.4, cm: 96 / 2.54, in: 96, em: base, rem: 16, ex: base / 2, '%': base / 100 }
  return Number(m[1]) * per[m[2] ?? 'px']!
}
