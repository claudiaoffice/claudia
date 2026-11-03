// Styles reach the page as a few allow-listed CSS properties (claudia_creates.ALLOWED_CSS). The slide is drawn in screen
// pixels, not scaled by CSS, so that lines keep their width relative to the slide: the lengths are scaled here.

const LENGTHS = ['font-size', 'letter-spacing', 'stroke-width']
const PAINT = ['fill', 'stroke', 'stroke-width']
const PIXELS = /^(-?\d+(?:\.\d+)?)px$/

/** The style with its lengths (in pixels of the slide) multiplied by the scale of the screen. */
export function scaleCss(css: Record<string, string>, scale: number): Record<string, string> {
  const out = { ...css }
  for (const name of LENGTHS) {
    const match = PIXELS.exec(out[name] ?? '')
    if (match) out[name] = `${Math.round(Number(match[1]) * scale * 100) / 100}px`
  }
  return out
}

/** The properties that paint an outline. */
export function pathCss(css: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(css).filter(([name]) => PAINT.includes(name)))
}

/** The properties that set type. */
export function textCss(css: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(css).filter(([name]) => !PAINT.includes(name)))
}
