// A floating object as a StyleHost: the shape, text box, picture or chart a person has selected is what the style
// menu styles. The same menu composes uses for a paragraph (E9.7, D203) — it knows nothing of either app.
//
// An object has slots (D304): a shape its outline and its words, a text box its box and its words, a picture and a
// chart a box. Until the menu edits each slot with a section per facet (the styling-suite plan, step 2.2), this host
// works on the one slot that the old menu's controls fit: a shape's outline (fill, stroke — the "box" controls), a
// text box's words (the "words" controls), and the box of a picture or a chart, for which those controls write
// nothing. It talks to the server through the one style API every app has (`apply_style`, `deviate`).
import type { Parts, StyleHost } from './style-host'
import type { ColourRole, ObjectBody, Reading, StyleTarget } from './objects'
import type { CssCheck, CssEdit, StyleView } from './style-css'

/** What this host needs of a session, so that creates and computes can both supply it. */
export interface ObjectStyling {
  readOnly: boolean
  styles: StyleView[]
  roles: ColourRole[]
  readings: Reading[]
  /** The object a person has selected, or null. */
  selected: ObjectBody | null
  /** Every object of the document, for the use counts. */
  bodies: ObjectBody[]
  /** Put a style into one slot of the targets (`apply_style`). */
  applyStyle(targets: StyleTarget[], style: string, slot: string): Promise<boolean>
  changeStyle(style: string, edit: CssEdit): Promise<boolean>
  /** Make a new style from `parent` for one slot of the targets only (`deviate`, D75, D309). */
  deviateStyle(parent: string, targets: StyleTarget[], slot: string, edit: CssEdit): Promise<boolean>
  renameStyle(style: string, name: string): Promise<boolean>
  checkCss(text: string): Promise<CssCheck | null>
  setRole(role: string, colour: string): Promise<boolean>
}

/** The slot of a kind of object that this host works on (see the header of this file). */
export function slotOf(kind: string | undefined): string {
  return kind === 'text' ? 'words' : kind === 'shape' ? 'outline' : 'box'
}

/** The style an object has in the slot this host works on: a text box's words have their paragraph's style. */
export function styleInSlot(body: ObjectBody): string {
  return slotOf(body.kind) === 'words' ? (body.paragraph?.style ?? body.style) : body.style
}

/** Which controls the menu offers for that slot: a shape's outline takes the fill and border controls (D178), a
 * text box's words the font controls; a picture's or a chart's box takes neither. Left out, not disabled (D209). */
export function partsOf(kind: string | undefined): Parts {
  switch (kind) {
    case 'shape':
      return { words: false, box: true }
    case 'text':
      return { words: true, box: false }
    default:
      return { words: false, box: false }
  }
}

/** What to call the selected object in a sentence: “shape”, “text box”, “picture”, “chart”. */
export function nounOf(kind: string | undefined): string {
  return { text: 'text box', shape: 'shape', image: 'picture', diagram: 'chart' }[kind ?? ''] ?? 'object'
}

/** How many objects have each style — the counts beside the names in the style gallery. */
export function objectUses(bodies: ObjectBody[]): Record<string, number> {
  const counted: Record<string, number> = {}
  for (const body of bodies) {
    // One count per slot that holds a style: the object's own, and its words' (D304).
    for (const style of body.paragraph ? [body.style, body.paragraph.style] : [body.style]) counted[style] = (counted[style] ?? 0) + 1
  }
  return counted
}

export function objectStyleHost(session: ObjectStyling): StyleHost {
  const selected = () => session.selected
  return {
    get styles() {
      return session.styles
    },
    get current() {
      const body = selected()
      return body ? session.styles.find((s) => s.id === styleInSlot(body)) : undefined
    },
    get readOnly() {
      // Only ever "you may not write to this document". Nothing-selected is *not* read-only, however much it
      // looks like it from here: found in a browser, where it disabled the whole palette dialog for an owner who
      // simply had no shape selected. The palette is the document's; what needs a selection is `current`, which is
      // undefined without one, and `apply`/`deviate`, which say so themselves.
      return session.readOnly
    },
    get noun() {
      return nounOf(selected()?.kind)
    },
    get parts() {
      return partsOf(selected()?.kind)
    },
    get roles() {
      return session.roles
    },
    get readings() {
      return session.readings
    },
    uses: () => objectUses(session.bodies),
    apply: async (style) => {
      const body = selected()
      return body ? session.applyStyle([{ object: body.id }], style, slotOf(body.kind)) : false
    },
    change: (style, edit) => session.changeStyle(style, edit),
    deviate: async (edit) => {
      const body = selected()
      return body ? session.deviateStyle(styleInSlot(body), [{ object: body.id }], slotOf(body.kind), edit) : false
    },
    rename: (style, name) => session.renameStyle(style, name),
    check: (text) => session.checkCss(text),
    setRole: (role, colour) => session.setRole(role, colour),
  }
}
