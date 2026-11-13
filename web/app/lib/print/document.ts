// From a text session to pages: the composes adapter of the layout library (`layoutText`), fed with what the session
// holds (paragraphs, styles, page) and what the preview fetched (objects, shapes, images), and the PDF made from it.
import { fontsNeeded, layoutText, utf8Decode, writePdf, type TextDocument, type TextPages } from '@claudia/layout'
import type { Block } from '../blocks'
import type { StyleView } from '../style-css'
import type { PrintAssets } from './assets'
import type { PrintExtras } from '../text-session'

/** The base64 of a server answer as bytes. */
export function fromBase64(data: string): Uint8Array {
  const bin = atob(data)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

/** The text as the layout library reads it. */
export function textDocument(blocks: readonly Block[], styles: readonly StyleView[], page: TextDocument['page'], extras: PrintExtras | null, language?: string | null): TextDocument {
  return {
    blocks: blocks.map((b) => ({ id: b.id, style: b.style, text: b.text })),
    styles: styles.map((s) => ({ id: s.id, based_on: s.based_on, resolved: s.resolved })),
    page,
    objects: extras?.objects ?? [],
    shapes: extras?.shapes ?? [],
    // an SVG picture is drawn from its text (D914); the others from their bytes
    images: extras?.images.map((i) => ({ id: i.id, format: i.format, ...(i.format === 'svg' ? { svg: utf8Decode(fromBase64(i.data)) } : {}) })) ?? [],
    language: language ?? null,
  }
}

/** Fetch the fonts and the hyphenation patterns the text needs, then lay it out. */
export async function layOut(assets: PrintAssets, doc: TextDocument): Promise<TextPages> {
  const [hyphenator] = await Promise.all([assets.hyphenator(doc.language), assets.ensure(fontsNeeded(doc, assets.resolver))])
  return layoutText(doc, assets.fonts, assets.resolver, { hyphenator })
}

/** The PDF of laid-out pages. No date is written into it, so the same text gives the same file everywhere. */
export function pdfOf(assets: PrintAssets, pages: TextPages, images: Map<string, Uint8Array>, title: string, lang?: string | null): Uint8Array {
  return writePdf(pages.list.pages, assets.fonts, (id) => images.get(id) ?? pages.embedded.get(id), { title, ...(lang ? { lang } : {}), producer: 'claudia composes' })
}
