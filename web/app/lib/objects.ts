// The shared object layer, client side (E10.16, D177 — mirrors `claudia_core.objects`).
//
// An object arrives from any of the three apps in exactly the same shape: the body's fields flat, plus one
// `anchor` whose contents only its own app understands. So `ObjectBody` below is shared by creates, computes
// and composes, and the only per-app part is the anchor and the small adapter that turns it into a `Frame` in
// pixels (`lib/geometry.ts` already works purely on frames and knows nothing about slides).
//
// This is the client half of the separation: the property dialog, the resize handles and the style plumbing can
// be written once against `ObjectBody` and reused per app by swapping the anchor adapter.

import type { ImageImport } from './images'

/** Where an object sits, in the terms of one app. `container` is its slide, sheet or paragraph. */
export interface SlideAnchor {
  kind: 'slide'
  container: string
  x: number
  y: number
}
export interface CellAnchor {
  kind: 'cell'
  container: string
  row: number
  col: number
}
export interface BlockAnchor {
  kind: 'block'
  container: string
  offset: number
}
export type Anchor = SlideAnchor | CellAnchor | BlockAnchor

/** What an object is and how it looks: the same fields in all three apps. */
export interface ObjectBody {
  id: string
  kind: 'text' | 'shape' | 'image'
  w: number
  h: number
  /** The id of a style in the document's style book: the object's own `fill`, `stroke` and `stroke-width`
   * (D178). What its *words* look like comes from the paragraph's own style instead. */
  style: string
  /** The words in it: a paragraph, the same entity composes uses (E10.17, D181), with its own style and the
   * runs saying who wrote which part. `null` for an image, which carries no text. */
  paragraph: Paragraph | null
  shape: string | null
  image: string | null
  imported: ImageImport | null
  /** Whole degrees clockwise. Persisted and validated by the model; no client surface yet. */
  rotation: number
  /** Whether this object holds to the grid (E10.15, D151): the document's own state, set with `setSnap`. The
   * grid itself is only a helper the view draws (see `lib/grid.ts`'s `useGrid`); unaffected by whether it is
   * shown. */
  snap: boolean
}

/** One object: the shared body plus the anchor of its own app. */
export type VisualObject<A extends Anchor = Anchor> = ObjectBody & { anchor: A }

/** Who wrote a stretch of a paragraph: `length` characters by `author` (null: unknown), through `via`'s
 * suggestion if any. */
export interface Run {
  length: number
  author: string | null
  via: string | null
}

/** One paragraph: its characters, the style that says how they look, and who wrote which of them. */
export interface Paragraph {
  id: string
  style: string
  text: string
  runs: Run[]
}

/** The words of an object, or `''` when it has none — the one place the client decides what an object with no
 * paragraph reads as, so no caller has to repeat the null check. */
export function wordsOf(body: ObjectBody): string {
  return body.paragraph?.text ?? ''
}

/** A style as the server sends it.
 *
 * `css` is what the style sets itself, `computed` what it really has once its parents are resolved (D73), and
 * `resolved` the same again with every palette role (`@accent`, `@accent/55`) replaced by the literal colour the
 * document's palette gives it (D200).
 *
 * **Draw with `resolved`; show and edit `css`/`computed`.** The role grammar deliberately lives on the server, so
 * that the CSS put on a page is always a literal colour — which is what lets the allow-list go on refusing
 * `var()` and `calc()`. A client that drew with `computed` would write `color: @accent` into a style attribute and
 * the browser would simply drop it. */
export interface StyleDef {
  id: string
  name: string
  purpose: string
  based_on: string | null
  css: Record<string, string>
  to_name: boolean
  computed: Record<string, string>
  resolved: Record<string, string>
}

/** One colour of the document's palette: what it means, and the colour it is (D200). */
export interface ColourRole {
  id: string
  name: string
  purpose: string
  colour: string
}

/** How one role reads against another, as the server works it out.
 *
 * `floor` is the contrast the pairing has to clear and `words` says which kind it is: 4.5:1 where it is words,
 * 3:1 where it is a border or a rule. Say what a failing reading *means* to the person — never show them `ratio`
 * (D202). */
export interface Reading {
  foreground: string
  background: string
  ratio: number
  floor: number
  ok: boolean
  words: boolean
}

/** The `palette` event and the `palette` method's answer. */
export interface PaletteEvent {
  type: 'palette'
  roles: ColourRole[]
  readings: Reading[]
}

/** The `objects` event, as the server sends it in every app (`claudia_core.ObjectsChanged`).
 *
 * Typed rather than read off an `any`, because `onAppEvent` takes `any` and so the compiler cannot otherwise
 * catch a renamed field: when `slide`/`sheet` became the one `container` (D177), a handler still reading
 * `data.slide` filed the stacking order under `undefined`, which made a freshly inserted object invisible and
 * unselectable until the document was reopened. Each app's handler narrows `data` to this before touching it. */
export interface ObjectsEvent {
  type: 'objects'
  /** The slide, sheet or paragraph these objects are on. */
  container: string
  changed: VisualObject[]
  removed: string[]
  /** The whole container's stacking order afterwards, bottom first. */
  order: string[]
}

/** A rectangle in the units of whatever space the object lives in. */
export interface Frame {
  x: number
  y: number
  w: number
  h: number
}

/** The frame of an object anchored to a point on a slide: the anchor *is* the top-left corner. */
export function slideFrame(obj: VisualObject<SlideAnchor>): Frame {
  return { x: obj.anchor.x, y: obj.anchor.y, w: obj.w, h: obj.h }
}

/** The slide anchor a frame implies (the inverse of `slideFrame`). */
export function slideAnchor(container: string, frame: Frame): SlideAnchor {
  return { kind: 'slide', container, x: frame.x, y: frame.y }
}

/** The look to draw an object with: the *resolved* CSS of its style, or nothing if the style is unknown.
 *
 * Resolved, not computed, so that a palette role has already become a colour by the time it reaches the page
 * (see `StyleDef`). */
export function cssOf(styles: Record<string, StyleDef>, body: ObjectBody): Record<string, string> {
  return styles[body.style]?.resolved ?? {}
}
