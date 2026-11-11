// The style menu is the same in every app (E9.7): it talks to a StyleHost, which says what the thing under the caret is
// styled with and how to change it. A text is one host (paragraph styles); cells and shapes will be others. Nothing in
// the menu knows which.
import {
  fontSizeOf,
  hasDecoration,
  isBold,
  isItalic,
  toggleDecoration as decorationWith,
  withFontSize,
  type Css,
  type CssCheck,
  type CssEdit,
  type StyleView,
} from './style-css'
import { stackFor } from './fonts'
import type { ColourRole, Reading, SlotView, StyleModel } from './objects'

/** One slot of the thing being styled (D304), as the style menu shows it: the server's slot and the words a person
 * reads for it ("Box", "Words", "Outline", "Label"). */
export interface HostSlot extends SlotView {
  label: string
}

/** The four facets in the order every editor shows them (D303). */
export const FACET_ORDER = ['text', 'paragraph', 'box', 'outline'] as const

export interface StyleHost {
  styles: StyleView[]
  /** The style the chosen slot holds; undefined while nothing is selected. */
  current: StyleView | undefined
  readOnly: boolean
  /** What is styled, singular: “paragraph”, “cell”, “shape”, “text box”. */
  noun: string
  /** The slots of what is selected (D304): one for a paragraph, two for a text box, a shape or a cell; none while
   * nothing is selected. */
  slots: HostSlot[]
  /** The slot the menu works on now; `current`, `apply` and `deviate` are about it. */
  slot: HostSlot | undefined
  /** Work on another of `slots` (by name). */
  chooseSlot(name: string): void
  /** The server's table of facets, kinds and slots (`style_model`), null until it has arrived. */
  model: StyleModel | null
  /** The document's colour roles, so a control can offer a meaning instead of a hex (D200). Empty for a document
   * whose palette has not arrived (or that has none), and the controls then fall back to plain colours. */
  roles: ColourRole[]
  /** How the roles read against each other, as the server works it out (D202). */
  readings: Reading[]
  /** How many things have each style. */
  uses(): Record<string, number>
  /** Give the selection this style. */
  apply(style: string): Promise<boolean>
  /** Change a style for everything that has it. */
  change(style: string, edit: CssEdit): Promise<boolean>
  /** Change only the selection: it gets a new style, which is named later. */
  deviate(edit: CssEdit): Promise<boolean>
  rename(style: string, name: string): Promise<boolean>
  check(text: string): Promise<CssCheck | null>
  /** Give a colour role another colour: everything in the document that meant it follows (D200). */
  setRole(role: string, colour: string): Promise<boolean>
}

/** What a gallery offers for a slot (D316, `style-editor-two-slots.svg`): the styles of the slot's own kind, and
 * — for a box — the whole styles that also set a box, whose box part is what the slot would use. A whole style that
 * sets nothing the slot reads is not offered: putting it there would change nothing. */
export function galleryFor(styles: StyleView[], slot: SlotView | undefined, model: StyleModel | null): { own: StyleView[]; bundles: StyleView[] } {
  if (!slot) return { own: [], bundles: [] }
  const own = styles.filter((s) => s.kind === slot.kind)
  const read = new Set(slot.reads.flatMap((facet) => model?.facets[facet] ?? []))
  const bundles = styles.filter((s) => s.kind !== slot.kind && slot.takes.includes(s.kind) && Object.keys(s.computed).some((p) => read.has(p)))
  return { own, bundles }
}

/** The facets a style can hold, by its kind — what the All styles editor shows, where no slot is chosen. */
export function facetsOfKind(model: StyleModel | null, kind: string): string[] {
  const held = new Set(model?.kinds[kind] ?? [])
  return FACET_ORDER.filter((facet) => held.has(facet))
}

/** The facets a slot reads, in the editor's order. */
export function facetsOfSlot(slot: SlotView | undefined): string[] {
  const read = new Set(slot?.reads ?? [])
  return FACET_ORDER.filter((facet) => read.has(facet))
}

/** The four sides of a box, in CSS's order. */
export const SIDES = ['top', 'right', 'bottom', 'left'] as const
export type Side = (typeof SIDES)[number]

/** A border value as its three parts; `null` where the style sets none. */
export function borderOf(value: string | undefined): { width: number; colour: string } | null {
  if (!value) return null
  const match = /^\s*([\d.]+)px\s+solid\s+(.+?)\s*$/.exec(value)
  return match ? { width: Math.round(Number(match[1])), colour: match[2]! } : null
}

export type Scope = 'new' | 'every'

const STEP: Record<string, number> = { pt: 1, px: 1, em: 0.1, rem: 0.1, '%': 10 }
const START = 12
/** As thick a border as the allow-list will take; past this it is a filled shape with a hole in it. */
const MAX_STROKE = 24
/** As much padding as a box sensibly takes; the allow-list itself goes further. */
const MAX_PADDING = 96
const none: Css = {}

/**
 * What the style menu does with a person's input. A change goes either to this text only (a new style that is named
 * later: “styles first, deviate second”) or to every use of the style; a style that still waits for its name is the
 * person’s own, so changes go into it. Changes are made one after the other, each deciding where to go at its turn.
 *
 * Browsing the gallery and changing text are two different things (UX-14): `pick` only chooses which style these
 * controls show and edit next; it never touches the document itself. `current` follows the picked style once one is
 * picked, and `host.current` (the caret's own paragraph) only again once `pick(null)` or the caret's own style is
 * picked back. Deviating ("this text only") makes sense only for the caret's real style — there is no selection
 * sitting in a style someone is merely browsing to — so `canDeviate` is false and `scope` stays "every" throughout.
 */
export class StyleEditor {
  choice: { style: string; scope: Scope } | null = null
  private queue: Promise<unknown> = Promise.resolve()
  /** Styles named or turned down for naming: ids. Public so that a component sees changes. */
  declined: string[] = []
  private picked: string | null = null

  /** `everyUse`: every change goes to every use of the style — the All styles dialog, where nothing is selected
   * (D302); a picked style then stays picked even when it is the caret's own. */
  constructor(
    private readonly host: StyleHost,
    private readonly everyUse = false,
  ) {}

  /** Look at a style's own definition without applying it to anything. `null`, or the caret's own style, goes back
   * to following the caret. */
  pick(id: string | null) {
    // Picking the caret's own style is "follow the caret again", not "pin this style": otherwise a deviation made
    // next ("this paragraph only") would leave the controls on the old style while the caret moved to the new one.
    this.picked = id === this.host.current?.id && !this.everyUse ? null : id
  }

  /** Whether `current` is a style merely being looked at, not the one actually under the caret. */
  get isPicked(): boolean {
    return this.picked !== null && this.picked !== this.host.current?.id
  }

  /** "This text only" only makes sense for the caret's own style; disabled while browsing another one's look. */
  get canDeviate(): boolean {
    return !this.isPicked
  }

  get current(): StyleView | undefined {
    if (this.picked === null) return this.host.current
    return this.host.styles.find((s) => s.id === this.picked) ?? this.host.current
  }

  /** The css the controls show: what the current style really has, with its palette roles already colours (D200).
   *
   * Resolved rather than computed, because a control has to show a colour it can paint: a swatch given `@accent`
   * would come up blank. The consequence is that picking a colour here writes a literal, which is precisely what
   * leaving the palette means — the menu that offers the roles themselves is the next step. */
  get look(): Css {
    return this.current?.resolved ?? none
  }

  /** What the current style *names* for a property: a palette role (`@accent`) where it names one, else the
   * literal value.
   *
   * The colour controls read this rather than `look`, so they can show a person "Accent" and not a hex — the whole
   * point of a role (D200). Everything that has to paint or measure reads `look`, which is already resolved. */
  named(property: string): string | undefined {
    return this.current?.computed[property]
  }

  get scope(): Scope {
    if (this.everyUse || this.isPicked) return 'every'
    const current = this.current
    if (this.choice && current && this.choice.style === current.id) return this.choice.scope
    return current?.to_name ? 'every' : 'new'
  }

  setScope(scope: Scope) {
    if (scope === 'new' && (!this.canDeviate || this.everyUse)) return
    const current = this.current
    if (current) this.choice = { style: current.id, scope }
  }

  get invitesName(): boolean {
    const current = this.current
    return !!current?.to_name && !this.declined.includes(current.id) && !this.host.readOnly
  }

  dismissNaming() {
    const current = this.current
    if (current) this.declined.push(current.id)
  }

  async name(typed: string): Promise<boolean> {
    const current = this.current
    const name = typed.trim()
    if (!current || !name) return false
    const done = await this.host.rename(current.id, name)
    if (done) this.declined.push(current.id)
    return done
  }

  /** Make a change: where it goes is decided when its turn comes. */
  edit(edit: CssEdit): Promise<boolean> {
    if (this.host.readOnly) return Promise.resolve(false)
    const run = this.queue.then(() => {
      const current = this.current
      if (!current) return false
      return this.scope === 'every' ? this.host.change(current.id, edit) : this.host.deviate(edit)
    })
    this.queue = run.catch(() => false)
    return run as Promise<boolean>
  }

  set(property: string, value: string) {
    return this.edit({ set: { [property]: value } })
  }

  setColor(property: 'color' | 'background-color', value: string) {
    return this.set(property, value)
  }

  /** Take a property back from the style: it follows its parent again. */
  reset(property: string) {
    return this.edit({ unset: [property] })
  }

  setText(text: string) {
    return this.edit({ text })
  }

  toggleBold() {
    return this.set('font-weight', isBold(this.look) ? 'normal' : 'bold')
  }

  toggleItalic() {
    return this.set('font-style', isItalic(this.look) ? 'normal' : 'italic')
  }

  toggleDecoration(which: 'underline' | 'line-through') {
    return this.set('text-decoration', decorationWith(this.look, which))
  }

  hasDecoration(which: 'underline' | 'line-through') {
    return hasDecoration(this.look, which)
  }

  setSize(value: number, unit: string) {
    return this.set('font-size', withFontSize(value, unit))
  }

  stepSize(direction: 1 | -1) {
    const size = fontSizeOf(this.look) ?? { value: START, unit: 'pt' }
    const step = STEP[size.unit] ?? 1
    const next = fontSizeOf(this.look) ? size.value + direction * step : START + (direction > 0 ? 1 : -1)
    return this.setSize(Math.round(next * 100) / 100, size.unit)
  }

  setFamily(typed: string) {
    return this.set('font-family', stackFor(typed))
  }

  setAlign(align: string) {
    return this.set('text-align', align)
  }

  // -- the box: a shape's own look, in SVG's words because a shape is an outline and not a rectangle (D178)
  setFill(value: string) {
    return this.set('fill', value)
  }

  setStroke(value: string) {
    return this.set('stroke', value)
  }

  setStrokeWidth(px: number) {
    return this.set('stroke-width', `${Math.max(0, Math.min(MAX_STROKE, Math.round(px)))}px`)
  }

  // -- a box: background, a border per side, padding (D303, D310)
  /** Give the chosen sides a border of `width` px in `colour` (a role or a literal); width 0 takes it away. */
  setBorder(sides: readonly Side[], width: number, colour: string) {
    const clean = Math.max(0, Math.min(MAX_STROKE, Math.round(width)))
    if (clean === 0) return this.edit({ unset: sides.map((side) => `border-${side}`) })
    return this.edit({ set: Object.fromEntries(sides.map((side) => [`border-${side}`, `${clean}px solid ${colour}`])) })
  }

  /** The border one side has, as the style names it (a role stays a role). */
  border(side: Side): { width: number; colour: string } | null {
    return borderOf(this.named(`border-${side}`))
  }

  /** The side the border controls open on: "all" when the four sides agree, otherwise the first side that has a
   *  border — a quote's rule on the left shows as itself, not as "all sides: none". */
  borderSide(): 'all' | Side {
    const four = SIDES.map((side) => this.named(`border-${side}`) ?? '')
    return four.every((value) => value === four[0]) ? 'all' : SIDES.find((_, i) => four[i]) ?? 'all'
  }

  /** The same padding on all four sides, in px. */
  setPadding(px: number) {
    const clean = Math.max(0, Math.min(MAX_PADDING, Math.round(px)))
    return this.edit({ set: Object.fromEntries(SIDES.map((side) => [`padding-${side}`, `${clean}px`])) })
  }

  get padding(): number {
    const match = /([\d.]+)/.exec(this.look['padding-top'] ?? '')
    return match ? Math.round(Number(match[1])) : 0
  }

  get strokeWidth(): number {
    const match = /([\d.]+)/.exec(this.look['stroke-width'] ?? '')
    return match ? Math.round(Number(match[1])) : 0
  }

  stepStrokeWidth(direction: 1 | -1) {
    return this.setStrokeWidth(this.strokeWidth + direction)
  }
}
