// Styles reach the page as a few allow-listed CSS properties (claudia_creates.ALLOWED_CSS). The slide is drawn in screen
// pixels, not scaled by CSS, so that lines keep their width relative to the slide: the lengths are scaled here.

const LENGTHS = ['font-size', 'letter-spacing', 'stroke-width', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left']
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

/** The properties of `css` that belong to the given facets — the part of a style a slot reads (D304). The facets
 * come from the server's `style_model` (`facets`), so this file keeps no list of its own; without it, nothing. */
export function facetCss(css: Record<string, string>, facets: Record<string, string[]> | undefined, names: string[]): Record<string, string> {
  const wanted = new Set(names.flatMap((name) => facets?.[name] ?? []))
  return Object.fromEntries(Object.entries(css).filter(([name]) => wanted.has(name)))
}
