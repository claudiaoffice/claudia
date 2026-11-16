// A text session as the composes adapter of the layout library (`layoutText`) reads it: what the session holds
// (paragraphs, styles, page) and what the preview fetched (objects, shapes, images). `source.ts` lays it out.
import { utf8Decode, type TextDocument } from '@claudia/layout'
import type { Block } from '../blocks'
import type { StyleView } from '../style-css'
import type { ListInfo, PrintExtras, SchemeInfo } from '../text-session'

/** The lists of a text and how they are drawn, for where its items sit on the page (E9.21). */
export interface ListsOfText {
  lists: readonly ListInfo[]
  schemes: readonly SchemeInfo[]
}

/** The base64 of a server answer as bytes. */
export function fromBase64(data: string): Uint8Array {
  const bin = atob(data)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

/** The text as the layout library reads it: a list item with the marker the server counted for it, so the printed
 *  pages draw the same markers as the editor. */
export function textDocument(
  blocks: readonly Block[],
  styles: readonly StyleView[],
  page: TextDocument['page'],
  extras: PrintExtras | null,
  language?: string | null,
  lists: ListsOfText = { lists: [], schemes: [] },
): TextDocument {
  return {
    blocks: blocks.map((b) => ({ id: b.id, style: b.style, text: b.text, item: b.item ?? null, label: b.label ? { marker: b.label.marker } : null })),
    lists: lists.lists.map((l) => ({ id: l.id, scheme: l.scheme })),
    schemes: lists.schemes.map((s) => ({ id: s.id, indent: s.indent, gap: s.gap })),
    styles: styles.map((s) => ({ id: s.id, based_on: s.based_on, resolved: s.resolved, heading: s.heading ?? null })),
    page,
    objects: extras?.objects ?? [],
    shapes: extras?.shapes ?? [],
    // an SVG picture is drawn from its text (D914); the others from their bytes
    images: extras?.images.map((i) => ({ id: i.id, format: i.format, ...(i.format === 'svg' ? { svg: utf8Decode(fromBase64(i.data)) } : {}) })) ?? [],
    language: language ?? null,
  }
}
