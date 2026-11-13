// A floating object as a StyleHost: the shape, text box, picture or chart a person has selected is what the style
// menu styles. The same menu composes uses for a paragraph (E9.7, D203) — it knows nothing of either app.
//
// An object has slots (D304), as the server's `style_model` says: a text box its box and its words, a shape its
// outline and its label, a picture and a chart a box. The menu opens on the slot a person most often means — a text
// box's words, a shape's outline (`slotOf`) — and the switcher of `style-editor-two-slots.svg` chooses the other.
// Everything goes through the one style API every app has (`apply_style`, `deviate`), for the chosen slot only.
import { ref } from 'vue'
import type { HostSlot, StyleHost } from './style-host'
import type { ColourRole, ObjectBody, Reading, StyleModel, StyleTarget } from './objects'
import type { CssCheck, CssEdit, StyleView } from './style-css'

/** What this host needs of a session, so that creates and computes can both supply it. */
export interface ObjectStyling {
  readOnly: boolean
  styles: StyleView[]
  roles: ColourRole[]
  readings: Reading[]
  /** The server's facets, kinds and slots (`style_model`); null until it has arrived. */
  model: StyleModel | null
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

/** The words a person reads for a slot. */
export const SLOT_LABELS: Record<string, string> = { box: 'Box', words: 'Words', outline: 'Outline', label: 'Label', paragraph: 'Paragraph' }

/** The slot the menu opens on for a kind of object: a text box's words, a shape's outline, the box of the rest. */
export function slotOf(kind: string | undefined): string {
  return kind === 'text' ? 'words' : kind === 'shape' ? 'outline' : 'box'
}

/** The style an object holds in a slot: the container's slot is the object's own style, the other its words'. */
export function styleInSlot(body: ObjectBody, slot: string = slotOf(body.kind)): string {
  return slot === 'words' || slot === 'label' ? (body.paragraph?.style ?? body.style) : body.style
}

/** The slots of a kind of object, as the server's table has them, with their labels. */
export function slotsOf(model: StyleModel | null, kind: string | undefined): HostSlot[] {
  return (model?.slots[kind ?? ''] ?? []).map((slot) => ({ ...slot, label: SLOT_LABELS[slot.name] ?? slot.name }))
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

/** `fixedSlot`: a host that always works on that slot of the selection when it has one (creates' bar has one picker
 * for a shape's outline and one for its label); without it the slot is the person's choice, as in the style menu. */
export function objectStyleHost(session: ObjectStyling, fixedSlot?: string): StyleHost {
  const selected = () => session.selected
  // Which slot a person switched to; forgotten when the selection moves to an object that does not have it.
  const chosen = ref<string | null>(fixedSlot ?? null)
  const slots = () => slotsOf(session.model, selected()?.kind)
  const slot = (): HostSlot | undefined => {
    const all = slots()
    return all.find((s) => s.name === chosen.value) ?? all.find((s) => s.name === slotOf(selected()?.kind)) ?? all[0]
  }
  return {
    get styles() {
      return session.styles
    },
    get current() {
      const body = selected()
      const where = slot()
      return body && where ? session.styles.find((s) => s.id === styleInSlot(body, where.name)) : undefined
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
    usesNoun: 'object',
    get slots() {
      return slots()
    },
    get slot() {
      return slot()
    },
    chooseSlot(name: string) {
      chosen.value = name
    },
    get model() {
      return session.model
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
      const where = slot()
      return body && where ? session.applyStyle([{ object: body.id }], style, where.name) : false
    },
    change: (style, edit) => session.changeStyle(style, edit),
    deviate: async (edit) => {
      const body = selected()
      const where = slot()
      return body && where ? session.deviateStyle(styleInSlot(body, where.name), [{ object: body.id }], where.name, edit) : false
    },
    rename: (style, name) => session.renameStyle(style, name),
    check: (text) => session.checkCss(text),
    setRole: (role, colour) => session.setRole(role, colour),
  }
}
