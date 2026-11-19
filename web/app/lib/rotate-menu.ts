// Format ▸ Rotate ▸ (D1024, D1232): the submenu is one shape in every app that turns objects. What differs is only what
// the selected object is and how each app turns it, so an app passes those in. The keys come from the manifest's table
// (`hintOf`), and `menuShortcuts` binds them, like every other entry's.

import type { translate } from './i18n'
import type { MenuItem } from '~/components/MenuBar.vue'
import { hintOf } from './shortcuts'
import { canTurn } from './turning'

export interface RotateHost {
  /** The kind of the selected object, `null` with none selected. */
  kind: () => string | null
  /** Nothing may be changed here (a read-only document). */
  readonly: () => boolean
  quarter: (direction: 1 | -1) => void
  by: () => void
}

/** The Rotate submenu: off with nothing selected and for a chart or a table (they do not turn, D1021, D1224); its
 * entries are off too in a document one can only look at. */
export function rotateItem(t: typeof translate, host: RotateHost): MenuItem {
  const kind = host.kind()
  const turns = kind !== null && canTurn(kind)
  const off = !turns || host.readonly()
  return {
    label: t('Rotate'),
    disabled: !turns,
    items: [
      { id: 'format.rotate-right', label: t('Rotate Right 90°'), hint: hintOf('format.rotate-right'), action: () => host.quarter(1), disabled: off },
      { id: 'format.rotate-left', label: t('Rotate Left 90°'), hint: hintOf('format.rotate-left'), action: () => host.quarter(-1), disabled: off },
      { id: 'format.rotate-by', label: t('Rotate By…'), hint: hintOf('format.rotate-by'), action: () => host.by(), disabled: off },
    ],
  }
}
