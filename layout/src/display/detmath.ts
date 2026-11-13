/**
 * Trigonometry that gives the same bits in every JavaScript engine. `Math.sin`, `Math.cos` and `Math.atan2` may
 * differ in the last digit between engines (the language does not fix their results); `+ − × ÷` and `Math.sqrt`
 * are exactly rounded everywhere. These functions use only those, so a curve computed from them is the same
 * everywhere. Accuracy is about 1e-12, far below the 0.001 pt the layout rounds to.
 *
 * @module
 */

const PI = 3.141592653589793
const TWO_PI = 6.283185307179586
const HALF_PI = 1.5707963267948966

/** sin and cos of an angle in radians, at once. */
export function sinCos(angle: number): [number, number] {
  // reduce to [-π, π]
  let a = angle - TWO_PI * Math.round(angle / TWO_PI)
  // to [-π/2, π/2], remembering the sign flip of cos
  let flip = 1
  if (a > HALF_PI) {
    a = PI - a
    flip = -1
  } else if (a < -HALF_PI) {
    a = -PI - a
    flip = -1
  }
  // Taylor series around 0, enough terms for |a| <= π/2 (last term < 1e-13)
  const a2 = a * a
  let s = a
  let term = a
  let c = 1
  let cterm = 1
  for (let k = 1; k <= 11; k++) {
    term *= -a2 / ((2 * k) * (2 * k + 1))
    s += term
    cterm *= -a2 / ((2 * k - 1) * (2 * k))
    c += cterm
  }
  return [s, c * flip]
}

/** atan(x) for any x. */
function atan(x: number): number {
  if (x < 0) return -atan(-x)
  if (x > 1) return HALF_PI - atan(1 / x)
  // halve the angle twice: atan(x) = 2·atan(x / (1 + sqrt(1 + x²))), then a short series
  let y = x / (1 + Math.sqrt(1 + x * x))
  y = y / (1 + Math.sqrt(1 + y * y))
  const y2 = y * y
  let sum = 0
  let power = y
  for (let k = 0; k < 14; k++) {
    sum += power / (2 * k + 1) * (k % 2 === 0 ? 1 : -1)
    power *= y2
  }
  return 4 * sum
}

/** atan2(y, x), the angle of the point (x, y), in (−π, π]. */
export function atan2(y: number, x: number): number {
  if (x > 0) return atan(y / x)
  if (x < 0) return y >= 0 ? atan(y / x) + PI : atan(y / x) - PI
  return y > 0 ? HALF_PI : y < 0 ? -HALF_PI : 0
}
