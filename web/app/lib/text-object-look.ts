// What a floating object of a text looks like on the screen (E10.16): its picture, its outline and its words, as plain
// data the layer draws. The same facets are read as in creates' `SlideCanvas.vue` — a text box its box, a shape its
// outline's paint, the words their text and paragraph (D304) — by the server's own `style_model`, so no list of
// properties is kept here. At 1:1, a text is not scaled.
import { cssOf, pointer, wordsCssOf, type BlockAnchor, type StyleDef, type StyleModel, type VisualObject } from './objects'
import { imageDataUrl } from './images'
import { facetCss } from './slide-style'
import { withDisplayInk } from './style-css'

type Css = Record<string, string>

/** The part of the session state that draws an object. */
export interface LookHolder {
  styles: Readonly<Record<string, StyleDef>>
  styleModel: StyleModel | null
  shapes: Record<string, { id: string; path: string; text_area: { x: number; y: number; w: number; h: number } }>
  images: Record<string, { format: string; data: string }>
}

export interface ObjectLook {
  /** The `src` of the picture, `''` when it is none or has not arrived yet. */
  picture: string
  /** A shape's outline, in a box of 100 × 100, and what paints it. */
  outline: { path: string; paint: Css } | null
  /** The words: their text, their look, and the box they fill (as CSS, in percentages of the object). */
  words: { text: string; css: Css; area: Css } | null
  /** A rendered container, which has a face of its own (`RenderedFace.vue`). */
  rendered: boolean
  /** An object a text cannot show yet (a chart); the layer says so instead of leaving a gap. */
  unsupported: boolean
}

/** The room a shape leaves round its words, in CSS pixels: they are not written right up to its edge. */
const SHAPE_PAD = 8

export function lookOf(holder: LookHolder, o: VisualObject<BlockAnchor>): ObjectLook {
  const styles = holder.styles
  const facets = holder.styleModel?.facets
  const facet = (css: Css, names: string[]) => facetCss(css, facets, names)
  const imageId = pointer(o, 'image')
  const asset = imageId ? holder.images[imageId] : undefined
  const look: ObjectLook = { picture: o.kind === 'image' && asset ? imageDataUrl(asset) : '', outline: null, words: null, rendered: o.kind === 'rendered', unsupported: o.kind === 'diagram' }
  if (o.kind === 'rendered' || o.kind === 'image' || o.kind === 'diagram') return look
  const shapeId = pointer(o, 'shape')
  const outline = shapeId ? (holder.shapes[shapeId] ?? null) : null
  if (o.kind === 'shape' && outline) look.outline = { path: outline.path, paint: facet(withDisplayInk(cssOf(styles, o)), ['outline']) }
  if (o.paragraph) {
    const area = outline?.text_area ?? { x: 0, y: 0, w: 100, h: 100 }
    const isText = o.kind === 'text'
    const box: Css = isText ? { ...facet(withDisplayInk(cssOf(styles, o)), ['box']), 'box-sizing': 'border-box' } : { padding: `${SHAPE_PAD}px`, 'box-sizing': 'border-box' }
    look.words = {
      text: o.paragraph.text,
      css: { ...facet(withDisplayInk(wordsCssOf(styles, o)), ['text', 'paragraph']), ...box },
      area: { left: `${area.x}%`, top: `${area.y}%`, width: `${area.w}%`, height: `${area.h}%`, display: 'flex', 'flex-direction': 'column', 'justify-content': isText ? 'flex-start' : 'center' },
    }
  }
  return look
}
