// Styles are CSS (D73, E1.10). The server decides what is allowed (`check_css`); this file only reads and writes what the
// server sends: the order of properties, which style a property comes from, sizes, bold and the like. Nothing here knows
// about paragraphs, cells or shapes, so the style menu can be used by all three apps.

export type Css = Record<string, string>

export interface StyleView {
  id: string
  name: string
  purpose: string
  based_on: string | null
  /** What the style sets itself. */
  css: Css
  /** What it really has, once its parents are taken in. */
  computed: Css
  /** Made by deviating and still carrying the name it was given: it invites a name (E9.7). */
  to_name: boolean
}

export interface CssProblem {
  line: number | null
  property: string | null
  message: string
}
export interface CssCheck {
  css: Css
  text: string
  problems: CssProblem[]
}
/** A change to the CSS of a style: properties to set and to remove, or the complete text of the style. */
export interface CssEdit {
  set?: Css
  unset?: string[]
  text?: string
}

/** The order in which a style is written (the same as the server's `format_css`). */
export const CSS_ORDER = [
  'font-family',
  'font-size',
  'font-weight',
  'font-style',
  'text-decoration',
  'color',
  'background-color',
  'text-align',
  'line-height',
  'letter-spacing',
  'word-spacing',
  'margin-top',
  'margin-right',
  'margin-bottom',
  'margin-left',
  'padding-top',
  'padding-right',
  'padding-bottom',
  'padding-left',
  'border-top',
  'border-right',
  'border-bottom',
  'border-left',
  'fill',
  'stroke',
  'stroke-width',
]
const place = (name: string) => {
  const i = CSS_ORDER.indexOf(name)
  return i < 0 ? CSS_ORDER.length : i
}
const inOrder = (names: string[]) => [...names].sort((a, b) => place(a) - place(b) || a.localeCompare(b))

export function formatCss(css: Css): string {
  return inOrder(Object.keys(css))
    .map((name) => `${name}: ${css[name]};`)
    .join('\n')
}

/** What to set and what to remove to turn `base` into `next`. */
export function diffCss(base: Css, next: Css): { set: Css; unset: string[] } {
  const set: Css = {}
  for (const [name, value] of Object.entries(next)) if (base[name] !== value) set[name] = value
  return { set, unset: Object.keys(base).filter((name) => !(name in next)) }
}

export interface Provenance {
  property: string
  value: string
  /** The id of the style that sets it. */
  from: string
  /** True when the style itself does not set it but one of its parents does. */
  inherited: boolean
}

/** Every property a style really has, with the style it comes from. */
export function provenance(styles: StyleView[], id: string): Provenance[] {
  const chain: StyleView[] = []
  for (let at: string | null = id; at; ) {
    const style = styles.find((s) => s.id === at)
    if (!style || chain.includes(style)) break
    chain.unshift(style)
    at = style.based_on
  }
  const found = new Map<string, Provenance>()
  for (const style of chain) for (const [property, value] of Object.entries(style.css)) found.set(property, { property, value, from: style.id, inherited: style.id !== id })
  return inOrder([...found.keys()]).map((name) => found.get(name)!)
}

// ------------------------------------------------------------------------------ the properties the menu has controls for
const SIZE = /^(\d+(?:\.\d+)?)(pt|px|em|rem|%)$/

export function fontSizeOf(css: Css): { value: number; unit: string } | null {
  const match = SIZE.exec(css['font-size'] ?? '')
  return match ? { value: Number(match[1]), unit: match[2]! } : null
}

export function withFontSize(value: number, unit: string): string {
  const clamped = Math.min(400, Math.max(1, value))
  return `${Math.round(clamped * 100) / 100}${unit}`
}

export function isBold(css: Css): boolean {
  const weight = css['font-weight']
  return weight === 'bold' || weight === 'bolder' || Number(weight) >= 600
}

export function isItalic(css: Css): boolean {
  return css['font-style'] === 'italic' || css['font-style'] === 'oblique'
}

export function hasDecoration(css: Css, which: 'underline' | 'line-through' | 'overline'): boolean {
  return (css['text-decoration'] ?? '').split(/\s+/).includes(which)
}

/** The value of `text-decoration` with `which` switched on or off. */
export function toggleDecoration(css: Css, which: 'underline' | 'line-through' | 'overline'): string {
  const now = (css['text-decoration'] ?? '').split(/\s+/).filter((w) => w && w !== 'none')
  const next = now.includes(which) ? now.filter((w) => w !== which) : [...now, which]
  return next.length ? next.join(' ') : 'none'
}

/** The first font of the family list, without quotes. */
export function familyName(css: Css): string {
  const first = (css['font-family'] ?? '').split(',')[0]?.trim() ?? ''
  return first.replace(/^['"]|['"]$/g, '')
}

const HEX = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i
const RGB = /^rgba?\(\s*(\d+)\s*[, ]\s*(\d+)\s*[, ]\s*(\d+)/i
const two = (n: number) => Math.min(255, n).toString(16).padStart(2, '0')

/** `#rrggbb` for the colours a colour field can show; `null` for the rest (names, hsl, transparent). */
export function toHex(color: string | undefined): string | null {
  if (!color) return null
  const hex = HEX.exec(color.trim())
  if (hex) {
    const digits = hex[1]!.length === 3 ? [...hex[1]!].map((c) => c + c).join('') : hex[1]!
    return `#${digits.toLowerCase()}`
  }
  const rgb = RGB.exec(color)
  return rgb ? `#${two(Number(rgb[1]))}${two(Number(rgb[2]))}${two(Number(rgb[3]))}` : null
}

// ------------------------------------------------------------------------------ what the page draws

/** The document's own default ink, in whatever form a style might state it — not a colour anyone chose, the colour
 * a run gets when nobody touched its `color` at all. A document genuinely is black-on-white (the owner's own framing,
 * 2026-11-06): this is a display-only stand-in, never a change to what is stored. */
const DEFAULT_INK_HEXES = new Set(['#1f1a33', '#000000'])

/** Is `color` one of the stand-ins for the document's own default ink? */
export function isDefaultInk(color: string | undefined): boolean {
  if (!color) return false
  const hex = toHex(color)
  return (hex !== null && DEFAULT_INK_HEXES.has(hex)) || color.trim().toLowerCase() === 'black'
}

/** `css` with its default-ink `color` (if any) swapped for the page's own text colour, so an unstyled run still
 * reads in dark mode; a colour anyone actually picked is left exactly as authored, in both themes. Used wherever a
 * style's computed CSS reaches the page — composes' paragraphs (`paragraphCss` below) and creates' text and shape
 * objects (`SlideCanvas.vue`'s `cssOf`) alike. */
export function withDisplayInk(css: Css): Css {
  return isDefaultInk(css.color) ? { ...css, color: 'var(--text)' } : css
}

/** The CSS of a paragraph on the page: the computed style as it is, with its ink made to read in dark mode. */
export function paragraphCss(computed: Css): Css {
  return withDisplayInk({ ...computed })
}

const PREVIEW = ['font-family', 'font-weight', 'font-style', 'text-decoration', 'color', 'background-color', 'letter-spacing']

/** How a style looks in a list of styles: its type and colours, not its size, margins or borders. Goes through the
 * same `withDisplayInk` swap as `paragraphCss` — a style whose own colour is the document's default ink still has
 * to be readable in the style picker itself (`StylesDialog.vue`'s "All styles…" list, `StyleMenu.vue`'s "Edit this
 * style…" picker), the owner's 2026-11-06 report that a style's own name was invisible there in dark mode. */
export function previewCss(computed: Css): Css {
  return withDisplayInk(Object.fromEntries(Object.entries(computed).filter(([name]) => PREVIEW.includes(name))))
}

const TAGS: Record<string, string> = { title: 'h1', 'heading-1': 'h2', 'heading-2': 'h3', quote: 'blockquote' }

/** The element a paragraph is: a heading or a quote if its style comes from one, a plain paragraph otherwise. */
export function semanticTag(styles: StyleView[], id: string): string {
  const seen = new Set<string>()
  for (let at: string | null | undefined = id; at && !seen.has(at); ) {
    if (TAGS[at]) return TAGS[at]!
    seen.add(at)
    at = styles.find((s) => s.id === at)?.based_on
  }
  return 'p'
}

export function styleUses(blocks: { style: string }[]): Record<string, number> {
  const uses: Record<string, number> = {}
  for (const block of blocks) uses[block.style] = (uses[block.style] ?? 0) + 1
  return uses
}
