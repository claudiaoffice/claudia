// A document for tests: headings, justified body text and a quote, as composes' built-in styles describe them.
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { type FlowBlock } from '../src/flow/paginate'
import { insets } from '../src/display/text'
import { type Css, paragraphStyleFromCss } from '../src/text/css'
import { layoutParagraph } from '../src/text/paragraph'

const SANS = "Inter, system-ui, 'Segoe UI', sans-serif"
const SERIF = 'Fraunces, Georgia, serif'
export const STYLES: Record<string, Css> = {
  title: { 'font-family': SERIF, 'font-size': '30pt', 'font-weight': '500', 'line-height': '1.15', 'margin-bottom': '0.5em' },
  h1: { 'font-family': SERIF, 'font-size': '19pt', 'font-weight': '500', 'line-height': '1.25', 'margin-top': '1.6em', 'margin-bottom': '0.5em' },
  body: { 'font-family': SANS, 'font-size': '12pt', 'line-height': '1.75', 'text-align': 'justify', 'margin-bottom': '0.9em' },
  quote: { 'font-family': SERIF, 'font-size': '14pt', 'font-style': 'italic', 'line-height': '1.7', 'margin-left': '2em', 'border-left': '3px solid #D6477A', 'padding-left': '10pt' },
}
const WORDS =
  'Eine Seite ist in Claudia keine Vermutung des Browsers mehr, sondern das Ergebnis einer Rechnung, die auf jedem Rechner dieselben Zahlen liefert. Jedes Zeichen bekommt seinen Platz aus der Schrift selbst. Office-Dateien, 567,89 € und 0,125 mm: Zahlen müssen genauso stehen wie Wörter.'.split(' ')

export function sampleParagraphs(n: number): { style: string; text: string }[] {
  const out: { style: string; text: string }[] = [{ style: 'title', text: 'Ein Bericht über Seiten' }]
  for (let i = 0; i < n; i++) {
    if (i % 5 === 0) out.push({ style: 'h1', text: `${i / 5 + 1}. Kapitel über Papier` })
    const len = 20 + ((i * 37) % 70)
    const text = Array.from({ length: len }, (_, k) => WORDS[(i * 7 + k) % WORDS.length]).join(' ')
    out.push({ style: i % 9 === 4 ? 'quote' : 'body', text })
  }
  return out
}

/** The paragraphs as flow blocks for a content width. */
export function blocks(fonts: FontSet, resolver: FontResolver, paras: { style: string; text: string }[], width: number): FlowBlock[] {
  return paras.map((p, i) => {
    const r = paragraphStyleFromCss(STYLES[p.style]!, resolver, fonts)!
    if (p.style === 'h1' || p.style === 'title') r.style.keepWithNext = true
    const inset = insets(r.decoration)
    return { id: `b${i}`, layout: layoutParagraph(fonts, r.style, p.text, width - inset.left - inset.right), decoration: r.decoration }
  })
}
