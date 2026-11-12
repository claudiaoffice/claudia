/**
 * From a claudia style's CSS (the allow-list of `claudia_core.css`, already resolved: palette roles replaced by
 * colours) to the resolved {@link ParagraphStyle} and {@link BoxDecoration} the layout works with. CSS lengths are
 * read once and rounded to whole mpt; everything after that is integer arithmetic.
 *
 * @module
 */
import type { FontResolver, Resolution } from '../fonts/resolve'
import { weightOf } from '../fonts/resolve'
import type { FontSet } from '../fonts/fontset'
import { cssLengthToMpt, mulDivRound } from '../units'
import { COLOR_NAMES } from './color-names'
import { BLACK, type ParagraphStyle, type Rgba, type TextAlign } from './style'

export type Css = Readonly<Record<string, string>>

/** CSS `medium`: 16 px = 12 pt. What `em` and `%` in `font-size` are relative to. */
export const BASE_FONT_SIZE = 12000

/** A border side: width (mpt), colour; `null` for none. */
export interface BorderSide {
  width: number
  color: Rgba
  style: 'solid' | 'dashed' | 'dotted' | 'double'
}

/** What a box (a paragraph, a text box, a cell) draws around and behind its content. Lengths in mpt. */
export interface BoxDecoration {
  padding: { top: number; right: number; bottom: number; left: number }
  border: { top: BorderSide | null; right: BorderSide | null; bottom: BorderSide | null; left: BorderSide | null }
  background: Rgba | null
}

export const NO_DECORATION: BoxDecoration = {
  padding: { top: 0, right: 0, bottom: 0, left: 0 },
  border: { top: null, right: null, bottom: null, left: null },
  background: null,
}

/** True when a decoration draws nothing and takes no room. */
export const isPlain = (d: BoxDecoration): boolean =>
  !d.background && !d.border.top && !d.border.right && !d.border.bottom && !d.border.left && !d.padding.top && !d.padding.right && !d.padding.bottom && !d.padding.left

const clamp255 = (n: number) => Math.min(255, Math.max(0, Math.round(n)))

function channel(s: string): number {
  return s.endsWith('%') ? clamp255((Number(s.slice(0, -1)) * 255) / 100) : clamp255(Number(s))
}
function alpha(s: string | undefined): number {
  if (s === undefined) return 255
  return s.endsWith('%') ? clamp255((Number(s.slice(0, -1)) * 255) / 100) : clamp255(Number(s) * 255)
}

/** A CSS colour (`#rgb`, `#rrggbbaa`, `rgb()`, `rgba()`, `hsl()`, `hsla()`, a name) as {@link Rgba}; `null` if not one. */
export function parseColor(value: string | undefined): Rgba | null {
  if (!value) return null
  let v = value.trim().toLowerCase()
  const named = COLOR_NAMES[v]
  if (named) v = named
  const hex = /^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/.exec(v)
  if (hex) {
    let h = hex[1]!
    if (h.length <= 4) h = [...h].map((c) => c + c).join('')
    const n = (i: number) => parseInt(h.slice(i, i + 2), 16)
    return { r: n(0), g: n(2), b: n(4), a: h.length === 8 ? n(6) : 255 }
  }
  const fn = /^(rgba?|hsla?)\(\s*([^)]*)\)$/.exec(v)
  if (!fn) return null
  const parts = fn[2]!.split(/\s*[,/]\s*|\s+/).filter(Boolean)
  if (parts.length < 3) return null
  if (fn[1]!.startsWith('rgb')) return { r: channel(parts[0]!), g: channel(parts[1]!), b: channel(parts[2]!), a: alpha(parts[3]) }
  // hsl → rgb (CSS Color 4, §7.1)
  const hue = ((Number(parts[0]!.replace('deg', '')) % 360) + 360) % 360
  const sat = Math.min(1, Math.max(0, Number(parts[1]!.replace('%', '')) / 100))
  const light = Math.min(1, Math.max(0, Number(parts[2]!.replace('%', '')) / 100))
  const f = (n: number) => {
    const k = (n + hue / 30) % 12
    const a = sat * Math.min(light, 1 - light)
    return light - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))
  }
  return { r: clamp255(f(0) * 255), g: clamp255(f(8) * 255), b: clamp255(f(4) * 255), a: alpha(parts[3]) }
}

function border(value: string | undefined, em: number): BorderSide | null {
  if (!value || value.trim().toLowerCase() === 'none') return null
  const m = /^\s*(\S+)\s+(solid|dashed|dotted|double)\s+(.+)$/i.exec(value)
  if (!m) return null
  const width = cssLengthToMpt(m[1]!, em)
  const color = parseColor(m[3])
  if (width === null || width <= 0 || !color) return null
  return { width, color, style: m[2]!.toLowerCase() as BorderSide['style'] }
}

/** The padding, borders and background a style's CSS gives a box. `em` is the box's font size in mpt. */
export function boxDecorationFromCss(css: Css, em: number): BoxDecoration {
  const len = (p: string) => Math.max(0, cssLengthToMpt(css[p] ?? '0', em) ?? 0)
  const bg = parseColor(css['background-color'])
  return {
    padding: { top: len('padding-top'), right: len('padding-right'), bottom: len('padding-bottom'), left: len('padding-left') },
    border: {
      top: border(css['border-top'], em),
      right: border(css['border-right'], em),
      bottom: border(css['border-bottom'], em),
      left: border(css['border-left'], em),
    },
    background: bg && bg.a > 0 ? bg : null,
  }
}

/** A style resolved from CSS, and what font request it made. */
export interface StyleFromCss {
  style: ParagraphStyle
  decoration: BoxDecoration
  font: Resolution
  /** the requested vertical alignment of the text in a box of fixed height */
  verticalAlign: 'top' | 'middle' | 'bottom'
}

/**
 * Resolve a style's CSS: the font through `resolver` (and registered in `fonts` by the caller beforehand, see
 * {@link FontSet.add}), sizes to mpt. `null` if the catalogue has no usable font at all.
 */
export function paragraphStyleFromCss(css: Css, resolver: FontResolver, fonts: FontSet, options: { language?: string } = {}): StyleFromCss | null {
  const size = Math.max(1000, cssLengthToMpt(css['font-size'] ?? '', BASE_FONT_SIZE) ?? BASE_FONT_SIZE)
  const italic = /^(italic|oblique)$/i.test(css['font-style'] ?? '')
  const font = resolver.resolve(css['font-family'] ?? 'sans-serif', weightOf(css['font-weight']), italic, size)
  if (!font) return null
  const len = (p: string, fallback = 0) => cssLengthToMpt(css[p] ?? '', size) ?? fallback

  let lineHeight: number
  const lh = (css['line-height'] ?? 'normal').trim().toLowerCase()
  if (lh === 'normal') {
    if (!fonts.has(font.face.sha256)) throw new Error(`the font ${font.font.family} must be added to the font set before its style is resolved`)
    const m = fonts.metrics(font.face)
    lineHeight = mulDivRound(m.ascender - m.descender + m.lineGap, size, m.unitsPerEm)
  } else if (/^(\d+\.?\d*|\.\d+)$/.test(lh)) lineHeight = Math.round(Number(lh) * size)
  else lineHeight = cssLengthToMpt(lh, size) ?? Math.round(size * 1.2)

  const alignMap: Record<string, TextAlign> = { left: 'left', start: 'left', right: 'right', end: 'right', center: 'center', justify: 'justify' }
  const deco = (css['text-decoration'] ?? '').toLowerCase()
  const spacing = (p: string) => ((css[p] ?? 'normal').trim().toLowerCase() === 'normal' ? 0 : len(p))
  const ws = (css['white-space'] ?? 'normal').toLowerCase()
  const decoration = boxDecorationFromCss(css, size)
  const va = (css['vertical-align'] ?? 'top').toLowerCase()
  return {
    style: {
      face: font.face,
      size,
      lineHeight: Math.max(1, lineHeight),
      align: alignMap[(css['text-align'] ?? 'left').toLowerCase()] ?? 'left',
      indentLeft: Math.max(0, len('margin-left')),
      indentRight: Math.max(0, len('margin-right')),
      firstLine: 0,
      spaceBefore: Math.max(0, len('margin-top')),
      spaceAfter: Math.max(0, len('margin-bottom')),
      color: parseColor(css.color) ?? BLACK,
      letterSpacing: spacing('letter-spacing'),
      wordSpacing: spacing('word-spacing'),
      underline: deco.includes('underline'),
      strike: deco.includes('line-through'),
      whiteSpace: ws === 'nowrap' ? 'nowrap' : ws === 'pre-wrap' ? 'pre-wrap' : 'normal',
      keepWithNext: false,
      orphans: 2,
      widows: 2,
      ...(options.language ? { language: options.language } : {}),
    },
    decoration,
    font,
    verticalAlign: va === 'middle' ? 'middle' : va === 'bottom' ? 'bottom' : 'top',
  }
}
