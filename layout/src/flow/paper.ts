/**
 * Paper sizes and page geometry. Every size is exact in mpt: millimetre sizes through {@link umToMpt}, inch sizes
 * as whole multiples of 72 pt. Any size can be used; the presets are only names for common ones.
 *
 * @module
 */
import { milToMpt, umToMpt } from '../units'

export type Orientation = 'portrait' | 'landscape'

export interface PaperSize {
  id: string
  /** a name people know: "A4", "Letter" */
  name: string
  /** the short side and the long side, mpt */
  width: number
  height: number
  /** how the size is usually written: "210 × 297 mm" */
  label: string
}

const mm = (id: string, name: string, w: number, h: number): PaperSize => ({ id, name, width: umToMpt(w * 1000), height: umToMpt(h * 1000), label: `${w} × ${h} mm` })
const inch = (id: string, name: string, w: number, h: number, label: string): PaperSize => ({ id, name, width: milToMpt(w), height: milToMpt(h), label })

/** Common paper sizes (ISO 216 A and B series, North American sizes), short side first. */
export const PAPER_SIZES: readonly PaperSize[] = [
  mm('a3', 'A3', 297, 420),
  mm('a4', 'A4', 210, 297),
  mm('a5', 'A5', 148, 210),
  mm('a6', 'A6', 105, 148),
  mm('b5', 'B5', 176, 250),
  inch('letter', 'Letter', 8500, 11000, '8.5 × 11 in'),
  inch('legal', 'Legal', 8500, 14000, '8.5 × 14 in'),
  inch('tabloid', 'Tabloid', 11000, 17000, '11 × 17 in'),
  inch('executive', 'Executive', 7250, 10500, '7.25 × 10.5 in'),
]

/** A preset by id (`a4`, `letter`), or `undefined`. */
export const paperById = (id: string): PaperSize | undefined => PAPER_SIZES.find((p) => p.id === id)

export interface Margins {
  top: number
  right: number
  bottom: number
  left: number
}

/** A page: its size as it lies (orientation applied) and its margins, mpt. */
export interface PageGeometry {
  width: number
  height: number
  margin: Margins
}

/** The smallest page and content width the layout accepts (a stamp, 10 mm, would not hold a word). */
export const MIN_PAGE = umToMpt(25_000)
export const MIN_CONTENT = umToMpt(10_000)

/**
 * The geometry of a page of `width` × `height` (short side first or not) in `orientation`, with `margin`.
 * `RangeError` if the page is too small or the margins leave less than {@link MIN_CONTENT} for the text.
 */
export function pageGeometry(width: number, height: number, orientation: Orientation, margin: Margins): PageGeometry {
  const short = Math.min(width, height)
  const long = Math.max(width, height)
  const [w, h] = orientation === 'landscape' ? [long, short] : [short, long]
  for (const v of [w, h, margin.top, margin.right, margin.bottom, margin.left]) {
    if (!Number.isSafeInteger(v) || v < 0) throw new RangeError(`page sizes and margins are whole, positive mpt: ${v}`)
  }
  if (w < MIN_PAGE || h < MIN_PAGE) throw new RangeError('the page is smaller than 25 mm')
  if (w - margin.left - margin.right < MIN_CONTENT || h - margin.top - margin.bottom < MIN_CONTENT) {
    throw new RangeError('the margins leave less than 10 mm for the text')
  }
  return { width: w, height: h, margin: { ...margin } }
}

/** The content box of a page. */
export const contentBox = (g: PageGeometry) => ({
  x: g.margin.left,
  y: g.margin.top,
  w: g.width - g.margin.left - g.margin.right,
  h: g.height - g.margin.top - g.margin.bottom,
})
