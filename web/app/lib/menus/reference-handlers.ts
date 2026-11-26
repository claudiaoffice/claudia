// What a reference's own menu does (D1607, UX-96): Show As ▸ its ways and Remove Reference. Go to Target has a key,
// which works at the caret, so each workspace keeps its own. Where the entries stand and when they fit is the
// definition's (`menus.generated.ts`). The calls are `t('...')` on purpose, for `scripts/extract_i18n.py`.
import type { Translate } from '../fits/conditions'
import { SHOWS, type Show } from '../references'
import type { Handlers } from './assemble'

/** The reference the menu was opened on. */
export interface ReferenceHere {
  show: Show
  setShow: (show: Show) => void
  remove: () => void
}

/** The entries for the reference `here`; with none (the workspace's own map, which the Shortcuts list reads), each says
 *  there is no reference here. */
export function referenceHandlers(t: Translate, here: ReferenceHere | null): Handlers {
  const notNow = here ? undefined : () => t('There is no reference here.')
  return {
    ...Object.fromEntries(SHOWS.map((show) => [`format.show-as-${show}`, { run: () => here?.setShow(show), checked: () => here?.show === show, notNow }])),
    'edit.remove-reference': { run: () => here?.remove(), notNow },
  }
}
