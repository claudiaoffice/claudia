// Format ▸ Template ▸ (E10.4, D1539): Change Theme…, Change Template… and Save as Template…. The keys come from the
// manifest's table (`hintOf`), and `menuShortcuts` binds them, like every other entry's. Only a presentation has it.

import type { translate } from './i18n'
import type { MenuItem } from '~/components/MenuBar.vue'
import { hintOf } from './shortcuts'

export interface TemplateHost {
  /** Nothing may be changed here (a read-only document). */
  readonly: () => boolean
  changeTheme: () => void
  changeTemplate: () => void
  saveAs: () => void
}

/** The Template submenu. The two changes are off in a document one can only look at; saving what it looks like as a
 * template changes nothing in it, so anybody who may export it may do that. */
export function templateItem(t: typeof translate, host: TemplateHost): MenuItem {
  const locked = host.readonly()
  return {
    label: t('Template'),
    items: [
      { id: 'format.change-theme', label: t('Change Theme…'), hint: hintOf('format.change-theme'), action: () => host.changeTheme(), disabled: locked },
      { id: 'format.change-template', label: t('Change Template…'), hint: hintOf('format.change-template'), action: () => host.changeTemplate(), disabled: locked },
      { id: 'format.save-as-template', label: t('Save as Template…'), hint: hintOf('format.save-as-template'), action: () => host.saveAs() },
    ],
  }
}
