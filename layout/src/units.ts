/**
 * Units and exact integer arithmetic.
 *
 * Every length the library produces is an integer number of **mpt**: thousandths of a PostScript point
 * (1 pt = 1/72 inch). Integers are exact in every JavaScript engine, so a layout computed in Firefox, Safari, Chrome
 * or Node gives the same numbers. Floats appear only while reading input (CSS lengths) and are rounded at once.
 *
 * @module
 */

/** Thousandths of a point in one point. */
export const MPT_PER_PT = 1000

/** Largest |a·b| {@link mulDivRound} accepts: 2^51, so that `2ab + c` stays exact below 2^53. */
const MAX_PRODUCT = 2251799813685248

/**
 * `round(a · b / c)`, halves rounded toward +∞, exactly.
 *
 * `a`, `b` are integers with |a·b| ≤ 2^51 and `c` an integer with 0 < c ≤ 2^20; a `RangeError` otherwise. One float
 * division of exact integers is off by less than 1/(4c), which cannot move it across the next integer boundary.
 */
export function mulDivRound(a: number, b: number, c: number): number {
  const p = a * b
  if (!Number.isSafeInteger(a) || !Number.isSafeInteger(b) || !(Math.abs(p) <= MAX_PRODUCT)) {
    throw new RangeError(`mulDivRound: operands must be integers with a product up to 2^51 (${a}, ${b})`)
  }
  if (!Number.isSafeInteger(c) || c <= 0 || c > 1048576) throw new RangeError(`mulDivRound: bad divisor ${c}`)
  return Math.floor((2 * p + c) / (2 * c))
}

/** An integer number of thousandths as a decimal string without trailing zeros: 12500 → "12.5", -5 → "-0.005". */
export function fmt3(thousandths: number): string {
  if (!Number.isSafeInteger(thousandths)) throw new RangeError(`fmt3: not an integer: ${thousandths}`)
  const neg = thousandths < 0
  const abs = Math.abs(thousandths)
  const whole = Math.floor(abs / 1000)
  let frac = String(abs % 1000).padStart(3, '0').replace(/0+$/, '')
  if (frac) frac = '.' + frac
  const s = `${whole}${frac}`
  return neg && s !== '0' ? '-' + s : s
}

/** Millimetres (given in thousandths of a millimetre) to mpt: 210 mm = 210000 → 595276. */
export const umToMpt = (um: number): number => mulDivRound(um, 72000, 25400)

/** Thousandths of an inch to mpt: 8.5 in = 8500 → 612000. */
export const milToMpt = (mil: number): number => mil * 72

/**
 * A CSS length to mpt. Accepts `pt`, `px` (1/96 in), `mm`, `cm`, `in`, `pc`, and `em`/`%` relative to `emMpt`.
 * A bare number is only accepted as zero (as in CSS); anything else gives `null`.
 */
export function cssLengthToMpt(value: string, emMpt: number): number | null {
  const m = /^\s*(-?(?:\d+\.?\d*|\.\d+))\s*(pt|px|mm|cm|in|pc|em|rem|%|q)?\s*$/i.exec(value)
  if (!m) return null
  const n = Number(m[1])
  const unit = (m[2] ?? '').toLowerCase()
  // round the input once to an integer of the unit's thousandths, then convert exactly
  const k = Math.round(n * 1000)
  switch (unit) {
    case 'pt': return k
    case 'px': return mulDivRound(k, 3, 4) // 1 px = 0.75 pt
    case 'mm': return mulDivRound(k, 72000, 25400)
    case 'cm': return mulDivRound(k, 720000, 25400)
    case 'q': return mulDivRound(k, 18000, 25400)
    case 'in': return k * 72
    case 'pc': return k * 12
    case 'em':
    case 'rem': return mulDivRound(k, emMpt, 1000)
    case '%': return mulDivRound(k, emMpt, 100000)
    case '': return n === 0 ? 0 : null
    default: return null
  }
}
