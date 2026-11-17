// A text session as the composes adapter of the layout library (`layoutText`) reads it: what the session holds
// (paragraphs, styles, page) and what the preview fetched (objects, shapes, images). `source.ts` lays it out.
import { utf8Decode, type TextDocument } from '@claudia/layout'
import type { Block } from '../blocks'
import { entryWords } from '../contents'
import { FIELD_CHAR, partsOf, readAs } from '../references'
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

/** A paragraph as the layout library reads it; a table of contents (E9.31) with its entries, whose pages the layout
 *  finds (step F). */
function printedBlock(b: Block): TextDocument['blocks'][number] {
  if (!b.generated) return { id: b.id, style: b.style, ...printedWords(b), item: b.item ?? null, label: b.label ? { marker: b.label.marker } : null }
  const entries = (b.entries ?? []).map((e) => ({ target: e.target, words: entryWords(e), style: e.style }))
  return { id: b.id, style: b.style, text: '', contents: { entries, places: b.generated.places, leader: b.generated.leader } }
}

/** A paragraph's words as they print: each reference as what it reads as (step H), and a page reference left for the
 *  layout to fill in (`pageRefs`, step I). */
function printedWords(b: Block): { text: string; pageRefs?: { at: number; target: string }[] } {
  if (!b.fields?.length) return { text: b.text }
  let text = ''
  const pageRefs: { at: number; target: string }[] = []
  for (const part of partsOf(b.text)) {
    if (part.kind === 'words') text += part.text
    else if (b.shown?.[part.index]?.state === 'page' && b.fields[part.index]) pageRefs.push({ at: text.length, target: b.fields[part.index]!.target })
    else text += readAs(FIELD_CHAR, b.shown?.slice(part.index, part.index + 1))
  }
  return pageRefs.length ? { text, pageRefs } : { text }
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
    blocks: blocks.map(printedBlock),
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
