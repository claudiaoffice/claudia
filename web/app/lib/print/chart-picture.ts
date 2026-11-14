// A chart as an SVG picture for the page (E6.19, D1008): the layout library draws charts on a printed sheet from an
// image, and the chart library (Plotly, D33) is the one that can make it — in the browser, the same figure the screen
// shows, with no interface around it. Only this module loads Plotly for printing; where it cannot be had (or a figure
// cannot be drawn) the chart is left out and the preview says so.
import type { Session } from '../session'
import type { ChartPictures } from './sheet-document'

/** The SVG text of a data URL as Plotly's `toImage` makes it (`data:image/svg+xml,<percent-encoded markup>`). */
export function svgOfDataUrl(url: string): string | null {
  const head = 'data:image/svg+xml'
  if (!url.startsWith(head)) return null
  const at = url.indexOf(',')
  if (at < 0) return null
  const body = url.slice(at + 1)
  try {
    return url.slice(head.length, at).includes('base64') ? new TextDecoder().decode(Uint8Array.from(atob(body), (c) => c.charCodeAt(0))) : decodeURIComponent(body)
  } catch {
    return null
  }
}

/** The pictures of a session's charts: its figure asked for if it is not here yet, then drawn by Plotly off screen. */
export function plotlyPictures(session: Session): ChartPictures {
  return async (spec, w, h) => {
    try {
      await session.ensureFigure(spec)
      const figure = session.figureOf(spec)
      if (!figure) return null
      const plotly = await import('plotly.js-dist-min')
      // Plotly's `toImage` takes a figure as well as a drawn chart; the layout is the one the screen draws (`ChartView.vue`)
      const layout = { ...figure.layout, width: w, height: h, margin: { t: 32, r: 16, b: 36, l: 48 }, autosize: false }
      const drawn = { data: figure.data, layout } as unknown as Parameters<typeof plotly.default.toImage>[0]
      return svgOfDataUrl(await plotly.default.toImage(drawn, { format: 'svg', width: w, height: h }))
    } catch {
      return null
    }
  }
}
