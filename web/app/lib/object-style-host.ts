// A floating object as a StyleHost: the shape, text box, picture or chart a person has selected is what the style
// menu styles. The same menu composes uses for a paragraph (E9.7, D203) — it knows nothing of either app.
//
// Two styles meet on one object and must not be confused (D181):
//   * the object's own says what the *box* looks like — fill, stroke, stroke-width (D178);
//   * its paragraph's says what the *words* look like.
// This host is about the first. Pointing an object's words at another paragraph style is `set_paragraph_style`,
// which the menu reaches through the same `apply` once a person is editing the text rather than the shape.
import type { Parts, StyleHost } from './style-host'
import type { ColourRole, ObjectBody, Reading } from './objects'
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
  setObjectStyle(id: string, style: string): Promise<boolean>
  changeStyle(style: string, edit: CssEdit): Promise<boolean>
  deviateObjectStyle(parent: string, ids: string[], edit: CssEdit): Promise<boolean>
  renameStyle(style: string, name: string): Promise<boolean>
  checkCss(text: string): Promise<CssCheck | null>
  setRole(role: string, colour: string): Promise<boolean>
}

/** What a kind of object has: a picture carries its own colours and holds no words (D178, D181). */
export function partsOf(kind: string | undefined): Parts {
  switch (kind) {
    case 'image':
      return { words: false, box: false }
    case 'diagram':
      // A chart draws itself from the data; what a style can still say is the box it sits in.
      return { words: false, box: true }
    case 'text':
      return { words: true, box: true }
    default:
      return { words: true, box: true }
  }
}

/** What to call the selected object in a sentence: “shape”, “text box”, “picture”, “chart”. */
export function nounOf(kind: string | undefined): string {
  return { text: 'text box', shape: 'shape', image: 'picture', diagram: 'chart' }[kind ?? ''] ?? 'object'
}

/** How many objects have each style — the counts beside the names in the style gallery. */
export function objectUses(bodies: ObjectBody[]): Record<string, number> {
  const counted: Record<string, number> = {}
  for (const body of bodies) counted[body.style] = (counted[body.style] ?? 0) + 1
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
      return body ? session.styles.find((s) => s.id === body.style) : undefined
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
      return body ? session.setObjectStyle(body.id, style) : false
    },
    change: (style, edit) => session.changeStyle(style, edit),
    deviate: async (edit) => {
      const body = selected()
      return body ? session.deviateObjectStyle(body.style, [body.id], edit) : false
    },
    rename: (style, name) => session.renameStyle(style, name),
    check: (text) => session.checkCss(text),
    setRole: (role, colour) => session.setRole(role, colour),
  }
}
