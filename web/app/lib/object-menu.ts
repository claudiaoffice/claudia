// The right-click menu of an object: one list for all three apps (D1225), as the menus workbook (`claudia-menus`,
// Context menus, rows 1–9) sets it. The list is built here from the object's kind and what the app has (a flag for the
// grid, a block for wrap), so creates, composes and computes cannot drift apart: each app supplies its live callbacks
// and renders the result with the generic `ContextMenu.vue`.
//
//   Name & describe… · Edit text · Style… · Rotate by… · Wrap text… ▸ (composes) · Move to Slide (computes, a chart on a
//   sheet) · — · Cut · Copy (pictures) · — · Release from grid (creates) · Delete
//
// An app leaves out what it cannot do yet (`ObjectMenuApp`): the entry is not shown rather than shown and dead.
//
// There are no 90° entries (Rotate by… does them), Rotate by… is not offered for a chart (D1021), a picture has no text
// to edit and neither has a chart, and for a picture "Style…" also holds what "Properties" was (`properties`). A table
// has a menu of its own (`table-menu.ts`, D1224) and is not offered here. "Name & describe…" opens the one dialog with the
// name field (D1317).
import type { MenuItem } from '../components/MenuBar.vue'
import { translate as t } from './i18n'
import { hintOf } from './shortcuts'
import { canTurn } from './turning'
import { WRAPS, wrapLabel, type Wrap } from './wrap'

/** What the menu needs to know of an object: any app's object has these. */
export interface MenuSubject {
  kind: string
  /** Does it follow the layout grid? Only creates has one. */
  snap?: boolean
}

export interface ObjectMenuActions {
  /** Say what the object shows to someone who cannot see it, or mark it as decoration (BITV 1.1.1). */
  describe: () => void
  edit: () => void
  /** Open the style menu on this object: its fill, its border, and the style its words follow (E9.7, D203). For a
   * picture the style menu also offers its properties. */
  style: () => void
  /** The Rotate By… popover (D1024). */
  rotateBy: () => void
  remove: () => void
  cut: () => void
  copy: () => void
  setSnap: (snap: boolean) => void
  /** composes only: the four modes of D1061, the gap, and what Ctrl+Alt+R cycles. */
  setWrap?: (wrap: Wrap) => void
  setGap?: () => void
  /** computes only, for a chart on a sheet: put it on a slide of its own (E6.31, D1475). */
  moveToSlide?: () => void
}

/** What an app has: `grid` is creates', `wrap` is composes' (the object's current mode). `edit` and `clipboard` are on
 * unless the app says no: composes can write in a container only. Cut, Copy and Paste of a picture are the same in
 * the three apps (`object-clipboard.ts`, D1229). */
export interface ObjectMenuApp {
  grid?: boolean
  wrap?: Wrap
  /** The words of this object can be written from here (default: yes, unless it is a picture or a chart). */
  edit?: boolean
  /** Cut and Copy of a picture work (default: yes). */
  clipboard?: boolean
}

const separator: MenuItem = { label: '', separator: true }

export function contextMenuItems(o: MenuSubject, readonly: boolean, actions: ObjectMenuActions, app: ObjectMenuApp = {}): MenuItem[] {
  const picture = o.kind === 'image'
  const groups: MenuItem[][] = []

  const top: MenuItem[] = [{ label: t('Name & describe…'), hint: hintOf('format.describe'), action: actions.describe, disabled: readonly }]
  // A picture has no text to write and a chart has none either: the entry is left off rather than shown disabled.
  if (!picture && o.kind !== 'diagram' && app.edit !== false) top.push({ label: t('Edit text'), hint: t('Enter'), action: actions.edit, disabled: readonly })
  top.push({ label: t('Style…'), hint: hintOf('format.apply-style'), action: actions.style, disabled: readonly })
  if (canTurn(o.kind)) top.push({ label: t('Rotate by…'), hint: hintOf('format.rotate-by'), action: actions.rotateBy, disabled: readonly })
  if (app.wrap !== undefined && actions.setWrap) {
    const setWrap = actions.setWrap
    top.push({
      label: t('Wrap text…'),
      hint: hintOf('format.wrap-text'),
      disabled: readonly,
      items: [
        ...WRAPS.map((wrap): MenuItem => ({ label: wrapLabel(wrap), checked: wrap === app.wrap, action: () => setWrap(wrap), disabled: readonly })),
        separator,
        { label: t('Gap…'), action: actions.setGap, disabled: readonly || !actions.setGap },
      ],
    })
  }
  // no key yet: it waits for the menu rework (owner, 2026-11-23; `claudia-menus`, Context menus row 25)
  if (o.kind === 'diagram' && actions.moveToSlide) top.push({ label: t('Move to Slide'), action: actions.moveToSlide, disabled: readonly })
  groups.push(top)

  // Cut/Copy: the very same `cutSelection`/`copySelection` the Edit menu's own items call. Copy only reads.
  if (picture && app.clipboard !== false) groups.push([{ label: t('Cut'), hint: t('Ctrl+X'), action: actions.cut, disabled: readonly }, { label: t('Copy'), hint: t('Ctrl+C'), action: actions.copy }])

  // The grid is only a helper the view draws; whether this object follows it is real document state (E10.15).
  // One entry whose label swaps, like "Undo <label>" does, rather than a checkbox.
  if (app.grid) groups.push([{ label: o.snap ? t('Release from grid') : t('Snap to grid'), action: () => actions.setSnap(!o.snap), disabled: readonly }])

  groups.push([{ label: t('Delete'), hint: t('Del'), action: actions.remove, disabled: readonly }])

  return groups.flatMap((group, i) => (i === 0 ? group : [separator, ...group]))
}
