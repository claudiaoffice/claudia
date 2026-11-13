// WCAG 2.1 contrast arithmetic for tests that read the design tokens (UX-04). Test support only: nothing in the app
// computes a contrast ratio at run time, so this lives next to the tests, not in `app/lib`.

export type Rgb = [number, number, number]

/** `#1f1a33` or `#fff` as three 0–255 numbers. */
export function parseHex(hex: string): Rgb {
  const digits = hex.trim().replace('#', '')
  const full = digits.length === 3 ? [...digits].map((d) => d + d).join('') : digits
  if (!/^[0-9a-fA-F]{6}$/.test(full)) throw new Error(`not a hex colour: ${hex}`)
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16)) as Rgb
}

/** What `color-mix(in srgb, <top> <percent>%, <under>)` gives where `under` is opaque: `top` laid over `under`. */
export function mix(top: Rgb, percent: number, under: Rgb): Rgb {
  return top.map((value, i) => Math.round((value * percent + under[i]! * (100 - percent)) / 100)) as Rgb
}

function channel(value: number): number {
  const v = value / 255
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
}

/** Relative luminance, as WCAG 2.1 defines it. */
export function luminance([r, g, b]: Rgb): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

/** The contrast ratio of two colours, 1 (identical) to 21 (black on white), whichever way round they are given. */
export function contrastRatio(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}
