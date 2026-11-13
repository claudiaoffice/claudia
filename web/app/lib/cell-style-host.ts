// The selected cells as a StyleHost (E6.13, D307, D311, D317): the same menu, popover and dialog a paragraph has,
// on the cells of `computes-cell-style-popover.svg`.
//
// A cell has two slots, a box and words (D304), but one style fills both (D311): to the menu a cell is one slot that
// reads every facet — Text, Paragraph and Box — and takes the styles that fit both. "These cells only" deviates both
// slots; "only their box" narrows it to the box (D309), so the words keep their style. Everything goes through the
// one style API every app has (`apply_style`, `deviate`) with the target `{sheet, range}`, plus `clear_cell_style`.
import { ref } from 'vue'
import { rangeLabel } from './cells'
import { alignOf, styleAt, whereFrom, type Area, type CellRange } from './cell-styles'
import type { HostSlot, StyleHost } from './style-host'
import type { ColourRole, Reading, StyleModel, StyleTarget } from './objects'
import type { CssCheck, CssEdit, StyleView } from './style-css'

/** What this host needs of a session (computes'). */
export interface CellStyling {
  readOnly: boolean
  styles: StyleView[]
  roles: ColourRole[]
  readings: Reading[]
  model: StyleModel | null
  /** The sheet shown. */
  sheet: string
  /** The selected cells, `[r0, c0, r1, c1]`; null while an object is selected instead (or there is no sheet). */
  area: Area | null
  /** The active cell: what the menu says the selection has. */
  anchor: { row: number; col: number }
  /** The sheet's style ranges, as loaded. */
  ranges(): CellRange[]
  /** The server's use counts (`style_uses`). */
  uses(): Record<string, number>
  applyStyle(targets: StyleTarget[], style: string, slot?: string): Promise<boolean>
  changeStyle(style: string, edit: CssEdit): Promise<boolean>
  deviateStyle(parent: string, targets: StyleTarget[], slot: string | undefined, edit: CssEdit): Promise<boolean>
  renameStyle(style: string, name: string): Promise<boolean>
  clearCellStyle(sheet: string, range: Area, slot?: string): Promise<boolean>
  checkCss(text: string): Promise<CssCheck | null>
  setRole(role: string, colour: string): Promise<boolean>
}

/** A cell as the one slot the menu works on: what both of its slots read, taking only what fits both. */
export function cellSlot(model: StyleModel | null): HostSlot | undefined {
  const slots = model?.slots.cell
  if (!slots?.length) return undefined
  const reads = [...new Set(slots.flatMap((s) => s.reads))]
  const takes = slots[0]!.takes.filter((kind) => slots.every((s) => s.takes.includes(kind)))
  const words = slots.find((s) => s.name === 'words') ?? slots[0]!
  return { name: 'cell', label: 'Cell', reads, kind: words.kind, takes }
}

export function cellStyleHost(session: CellStyling): StyleHost {
  const boxOnly = ref(false)
  const target = (): StyleTarget[] => (session.area ? [{ sheet: session.sheet, range: session.area }] : [])
  const at = (slot: 'box' | 'words') => styleAt(session.ranges(), session.anchor.row, session.anchor.col, slot).style
  const find = (id: string) => session.styles.find((s) => s.id === id)
  const count = () => {
    const a = session.area
    return a ? (a[2] - a[0] + 1) * (a[3] - a[1] + 1) : 0
  }

  return {
    get styles() {
      return session.styles
    },
    /** The words' style — what the cells read as — or, while "only their box" is ticked, the box's: then the box
     * is what is being changed, and a style made for it alone is what further changes go into. */
    get current() {
      return session.area ? find(at(boxOnly.value ? 'box' : 'words')) : undefined
    },
    get readOnly() {
      return session.readOnly
    },
    noun: 'cell',
    get title() {
      const a = session.area
      if (!a) return 'Cells'
      return `${count() === 1 ? 'Cell' : 'Cells'} ${rangeLabel(a[0], a[1], a[2], a[3])}`
    },
    get these() {
      const n = count()
      return n === 1 ? 'This cell only' : `These ${n.toLocaleString('en-US')} cells only`
    },
    narrow: {
      get label() {
        return count() === 1 ? 'only its box' : 'only their box'
      },
      get on() {
        return boxOnly.value
      },
      set(on: boolean) {
        boxOnly.value = on
      },
    },
    get origin() {
      return session.area ? whereFrom(session.ranges(), session.anchor.row, session.anchor.col, (id) => find(id)?.name ?? id) : []
    },
    extras: ['vertical-align', 'white-space'],
    alignOf: (style) => alignOf(Object.fromEntries(session.styles.map((s) => [s.id, s])), style),
    get slots() {
      const slot = cellSlot(session.model)
      return slot ? [slot] : []
    },
    /** With "only their box" ticked the menu works on the box alone, so it shows only what a box reads (D309). */
    get slot() {
      const slot = cellSlot(session.model)
      return slot && boxOnly.value ? { ...slot, reads: slot.reads.filter((f) => f === 'box') } : slot
    },
    chooseSlot() {
      // One slot to the menu: nothing to switch.
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
    uses: () => session.uses(),
    apply: async (style) => (session.area ? session.applyStyle(target(), style) : false),
    change: (style, edit) => session.changeStyle(style, edit),
    deviate: async (edit) => {
      if (!session.area) return false
      return boxOnly.value ? session.deviateStyle(at('box'), target(), 'box', edit) : session.deviateStyle(at('words'), target(), undefined, edit)
    },
    clear: async () => (session.area ? session.clearCellStyle(session.sheet, session.area) : false),
    rename: (style, name) => session.renameStyle(style, name),
    check: (text) => session.checkCss(text),
    setRole: (role, colour) => session.setRole(role, colour),
  }
}
