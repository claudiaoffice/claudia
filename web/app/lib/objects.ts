// The shared object layer, client side (E10.16, D177 — mirrors `claudia_core.objects`).
//
// An object arrives from any of the three apps in exactly the same shape: the body's fields flat, plus one
// `anchor` whose contents only its own app understands. So `ObjectBody` below is shared by creates, computes
// and composes, and the only per-app part is the anchor and the small adapter that turns it into a `Frame` in
// pixels (`lib/geometry.ts` already works purely on frames and knows nothing about slides).
//
// This is the client half of the separation: the property dialog, the resize handles and the style plumbing can
// be written once against `ObjectBody` and reused per app by swapping the anchor adapter.

import type { ObjectKind } from '@claudia/layout'
import type { ImageImport } from './images'
import type { Toc } from './contents'
import type { RefField } from './references'

/** Where an object sits, in the terms of one app. `holder` is its slide, sheet or paragraph. */
export interface SlideAnchor {
  kind: 'slide'
  holder: string
  x: number
  y: number
}
export interface CellAnchor {
  kind: 'cell'
  holder: string
  row: number
  col: number
}
/** A character of a paragraph, plus how far the object is moved off it (D1023): both are in the units of `w` and `h`,
 * and absent for an object that sits exactly at its character. `wrap` says how the text flows round the object (D1061:
 * absent is `over`, the words do not give way) and `gap` how far the words keep from it, in the same units (absent is
 * the usual 8). */
export interface BlockAnchor {
  kind: 'block'
  holder: string
  offset: number
  dx?: number
  dy?: number
  wrap?: 'over' | 'around' | 'above-below' | 'behind'
  gap?: number
}
export type Anchor = SlideAnchor | CellAnchor | BlockAnchor

/** What an object is and how it looks: the same fields in all three apps. */
export interface ObjectBody {
  id: string
  /** The name the object goes by in the whole document (D550), `''` for one that has none yet. */
  name?: string
  kind: ObjectKind
  w: number
  h: number
  /** The id of a style in the document's style book: the object's own `fill`, `stroke` and `stroke-width`
   * (D178). What its *words* look like comes from the paragraph's own style instead. */
  style: string
  /** The words in it: a paragraph, the same entity composes uses (E10.17, D181), with its own style and the
   * runs saying who wrote which part. `null` for an image or a diagram, neither of which carries text. */
  paragraph: Paragraph | null
  /** The id of the definition the kind points at, in the document's own table for that kind: the outline of a
   * `shape`, the asset of an `image`, the `ChartSpec` of a `diagram` (E6.6, `lib/charts.ts`), the rendered text
   * definition of a `rendered` container (D390, `renderings` on the wire) or the table definition of a `table`
   * (D1201). `null` for a text box. A rendered container's picture is its definition's own. Read it with
   * `pointer(object, kind)`, which is `null` unless the object is of that kind. */
  ref: string | null
  imported: ImageImport | null
  /** Whole degrees clockwise about the centre of the frame, 0–359 (D1021). A chart never turns. */
  rotation: number
  /** Whether this object holds to the grid (E10.15, D214): the document's own state, set with `setSnap`. The
   * grid itself is only a helper the view draws (see `lib/grid.ts`'s `useGrid`); unaffected by whether it is
   * shown. */
  snap: boolean
  /** What the object says to someone who cannot see it (BITV 1.1.1; `lib/descriptions.ts`). A picture that has none of
   * its own is described by the words it was imported with; a decorative object has none. */
  description: string
  /** Only decoration: a screen reader skips it, and it has no description. */
  decorative: boolean
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
  /** Its place in a list (E9.21): which list and how deep, when it is an item of one. */
  item?: { list: string; level: number } | null
  /** Set when the words are an agenda (E9.31): its options. Such a paragraph holds no text; its lines are derived. */
  generated?: Toc | null
  /** The references in the words, one for each U+FFFC, in order (step H). */
  fields?: RefField[]
}

/** The id of the definition `body` points at if it is of `kind` (an image's asset, a diagram's chart spec, a table's
 * definition …), else `null`: the one `ref` field serves every kind, and the kind says what it is. */
export function pointer(body: Pick<ObjectBody, 'kind' | 'ref'>, kind: ObjectKind): string | null {
  return body.kind === kind ? body.ref : null
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
  /** `builtin` or `template` where it is not the document's own (D780); only the document's own can be deleted. */
  origin?: 'builtin' | 'template'
  /** Left out of the menus a style is picked from (D780). */
  hidden?: boolean
  /** `paragraph`, `box` or `outline` (D305, D312). */
  kind: string
  computed: Record<string, string>
  resolved: Record<string, string>
  /** The heading level it gives (0 the title, 1 to 9 a level, `null` none) and the list that numbers it (E9.22). */
  heading?: number | null
  numbering?: string | null
  numbered?: string | null
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
  /** The palette a document starts with, as the server states it, so no client keeps a copy that could drift.
   * Absent on the event, which carries only what changed. */
  builtin?: ColourRole[]
}

/** The `objects` event, as the server sends it in every app (`claudia_core.ObjectsChanged`).
 *
 * Typed rather than read off an `any`, because `onAppEvent` takes `any` and so the compiler cannot otherwise
 * catch a renamed field: when `slide`/`sheet` became the one `holder` (D177, D1430), a handler still reading
 * `data.slide` filed the stacking order under `undefined`, which made a freshly inserted object invisible and
 * unselectable until the document was reopened. Each app's handler narrows `data` to this before touching it. */
export interface ObjectsEvent {
  type: 'objects'
  /** The slide, sheet or paragraph these objects are on. */
  holder: string
  changed: VisualObject[]
  removed: string[]
  /** The whole holder's stacking order afterwards, bottom first. */
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
export function slideAnchor(holder: string, frame: Frame): SlideAnchor {
  return { kind: 'slide', holder, x: frame.x, y: frame.y }
}

/** The look to draw an object with: the *resolved* CSS of its style, or nothing if the style is unknown.
 *
 * Resolved, not computed, so that a palette role has already become a colour by the time it reaches the page
 * (see `StyleDef`). */
export function cssOf(styles: Record<string, StyleDef>, body: ObjectBody): Record<string, string> {
  return styles[body.style]?.resolved ?? {}
}

/** One slot of a kind of thing, as the server's `style_model` sends it (D304, D316). */
export interface SlotView {
  name: string
  /** The facets the slot reads. */
  reads: string[]
  /** The kind of a style made for this slot alone. */
  kind: string
  /** The kinds of style that fit it. */
  takes: string[]
}

/** What a style property means and where a style can go: the server's `style_model`. A client keeps no copy. */
export interface StyleModel {
  facets: Record<string, string[]>
  kinds: Record<string, string[]>
  slots: Record<string, SlotView[]>
  targets: string[]
}

/** Something a style is put into, in the app's own terms (`apply_style`, `deviate`). */
export type StyleTarget = { object: string } | { block: string } | { sheet: string; range: [number, number, number, number] }

/** What an object's *words* look like: its paragraph's own style, resolved — not the object's style, which is its
 * box or outline (D181, D304). A shape's outline and its words are two slots with a style each (D310). Empty for an
 * object without words. */
export function wordsCssOf(styles: Record<string, StyleDef>, body: ObjectBody): Record<string, string> {
  return body.paragraph ? (styles[body.paragraph.style]?.resolved ?? {}) : {}
}
