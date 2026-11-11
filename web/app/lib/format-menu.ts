// The Format menu, the same four entries in every app (D300, `format-menu-apply-style.svg`):
//
//   Apply style ▸     the styles that fit what is selected, each drawn in its look, grouped as the app groups them
//   Edit this style…  the popover at the selection (Shift+F10)
//   All styles…       the dialog, with Edit beside Rename (D302)
//   ─────────────
//   Colours…          the document's palette (D200)
//
// A native shell has one entry for the first, "Apply Style…", which opens the page's popover instead of a flyout
// (D301): that is the flyout parent's `action`. Each workspace says what fits and what to do; this file only builds.
import type { MenuItem } from '../components/MenuBar.vue'
import { menuCss, type StyleView } from './style-css'

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
  /** More entries at the end of the flyout, after a separator ("Clear cell style"). */
  more?: MenuItem[]
}

/** The four entries of the Format menu. `t` is the app's translation function. */
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
    { id: 'format.apply-style', label: t('Apply style'), items: flyout, action: () => menu.openApply() },
    { id: 'format.look', label: t('Edit this style…'), hint: menu.look.hint, disabled: menu.look.disabled, action: () => menu.look.open() },
    { id: 'format.all-styles', label: t('All styles…'), action: () => menu.allStyles() },
    { label: '', separator: true },
    { id: 'format.colours', label: t('Colours…'), action: () => menu.colours() },
  ]
}
