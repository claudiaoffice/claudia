// The Format menu, the same four entries in every app (D300, `format-menu-apply-style.svg`):
//
//   Apply style ▸     the styles that fit what is selected, each drawn in its look, grouped as the app groups them
//   Edit this style…  the popover at the selection (Shift+F10)
//   All styles…       the dialog, with Edit beside Rename (D302)
//   List ▸            bullets, numbers and their levels (E9.21); there in every app, disabled where it has no use yet
//   ─────────────
//   Colours…          the document's palette (D200)
//
// A native shell has one entry for the first, "Apply Style…", which opens the page's popover instead of a flyout
// (D301): that is the flyout parent's `action`. Each workspace says what fits and what to do; this file only builds.
import type { MenuItem } from '../components/MenuBar.vue'
import { menuCss, type StyleView } from './style-css'

/** What the List entry does in this app (E9.21). */
export interface ListMenu {
  /** Why there are no lists here (cells, slides' text boxes): the entry stays, disabled, and says so. */
  unavailable?: string
  /** A viewer may look, not change. */
  readonly?: boolean
  /** The kind of list the caret's item belongs to: ticked. */
  current: 'bullets' | 'numbers' | null
  /** The caret is in a list item: levels and numbering can be asked for. */
  canNest: boolean
  /** The caret is in the first item of a list that has an earlier list of its kind to go on from. */
  canContinue: boolean
  /** The keys, as the app binds them, for the right-hand side of the entries. */
  hints?: { bulleted?: string; numbered?: string; indent?: string; outdent?: string }
  bulleted(): void
  numbered(): void
  continueList(): void
  startAt(): void
  indent(): void
  outdent(): void
}

/** The List entry of an app that has no lists (yet): shown for consistency, disabled, with the reason (E9.21). */
export function noLists(unavailable: string): ListMenu {
  const nothing = () => undefined
  return { unavailable, current: null, canNest: false, canContinue: false, bulleted: nothing, numbered: nothing, continueList: nothing, startAt: nothing, indent: nothing, outdent: nothing }
}

export interface FormatMenu {
  /** The styles the flyout offers, in groups that a separator divides (composes' D127 groups; one group elsewhere). */
  groups: StyleView[][]
  /** A first, inert line saying what the styles are for ("For the 6 selected cells"). */
  heading?: string
  /** The style the selection has now: ticked. */
  current?: string
  /** Whether a style can be applied now: something selected, and the document writable. */
  canApply: boolean
  apply(style: string): void
  /** The shells' "Apply Style…": the page's own popover in its apply mode (D301). */
  openApply(): void
  /** Edit this style…: disabled with nothing selected. */
  look: { disabled: boolean; hint?: string; open(): void }
  allStyles(): void
  colours(): void
  list: ListMenu
  /** More entries at the end of the flyout, after a separator ("Clear cell style"). */
  more?: MenuItem[]
}

/** The List entry: a flyout of what can be done to the paragraphs at the caret. Its entries have action ids, and the
 * native shells' menus have them too (UX-36): in every app, as here, disabled where there are no paragraphs. */
function listItem(t: (text: string) => string, list: ListMenu): MenuItem {
  const off = !!list.unavailable
  const locked = off || !!list.readonly
  const flyout: MenuItem[] = []
  if (list.unavailable) flyout.push({ label: list.unavailable, disabled: true })
  flyout.push(
    { id: 'format.bulleted-list', label: t('Bulleted List'), hint: list.hints?.bulleted, checked: list.current === 'bullets', disabled: locked, action: () => list.bulleted() },
    { id: 'format.numbered-list', label: t('Numbered List'), hint: list.hints?.numbered, checked: list.current === 'numbers', disabled: locked, action: () => list.numbered() },
    { label: '', separator: true },
    { id: 'format.list-continue', label: t('Continue Previous List'), disabled: locked || !list.canContinue, action: () => list.continueList() },
    { id: 'format.list-start', label: t('Start At…'), disabled: locked || !list.canNest, action: () => list.startAt() },
    { label: '', separator: true },
    { id: 'format.list-indent', label: t('Indent'), hint: list.hints?.indent, disabled: locked || !list.canNest, action: () => list.indent() },
    { id: 'format.list-outdent', label: t('Outdent'), hint: list.hints?.outdent, disabled: locked || !list.canNest, action: () => list.outdent() },
  )
  return { label: t('List'), items: flyout, disabled: off }
}

/** The entries of the Format menu: the four of D300 and the list. `t` is the app's translation function. */
export function formatItems(t: (text: string) => string, menu: FormatMenu): MenuItem[] {
  const groups = menu.groups.filter((group) => group.length)
  const flyout: MenuItem[] = []
  if (menu.heading) flyout.push({ label: menu.heading, disabled: true })
  groups.forEach((group, i) => {
    if (i > 0) flyout.push({ label: '', separator: true })
    for (const s of group) {
      flyout.push({
        label: s.name,
        css: menuCss(s.resolved),
        checked: s.id === menu.current,
        disabled: !menu.canApply,
        action: () => menu.apply(s.id),
      })
    }
  })
  if (!groups.length) flyout.push({ label: t('No styles fit what is selected'), disabled: true })
  if (menu.more?.length) flyout.push({ label: '', separator: true }, ...menu.more)
  return [
    { id: 'format.apply-style', label: t('Apply Style'), items: flyout, action: () => menu.openApply() },
    { id: 'format.look', label: t('Edit This Style…'), hint: menu.look.hint, disabled: menu.look.disabled, action: () => menu.look.open() },
    { id: 'format.all-styles', label: t('All Styles…'), action: () => menu.allStyles() },
    listItem(t, menu.list),
    { label: '', separator: true },
    { id: 'format.colours', label: t('Colours…'), action: () => menu.colours() },
  ]
}
