// The text as a StyleHost: its paragraphs are what the style menu styles. A paragraph is one slot that reads text,
// paragraph and box (D304), so there is no switcher.
import type { HostSlot, StyleHost } from './style-host'
import type { TextSession } from './text-session'

import { translate as t } from './i18n'
export function textStyleHost(session: TextSession): StyleHost {
  const slot = (): HostSlot | undefined => {
    const found = session.state.styleModel?.slots.paragraph?.[0]
    return found ? { ...found, label: t('Paragraph') } : undefined
  }
  return {
    get styles() {
      return session.state.styles
    },
    get current() {
      return session.styleView(session.currentStyle()) ?? session.state.styles[0]
    },
    get readOnly() {
      return session.readOnly
    },
    noun: 'paragraph',
    get slots() {
      const one = slot()
      return one ? [one] : []
    },
    get slot() {
      return slot()
    },
    chooseSlot: () => undefined,
    get model() {
      return session.state.styleModel
    },
    get roles() {
      return session.state.palette?.roles ?? []
    },
    get readings() {
      return session.state.palette?.readings ?? []
    },
    uses: () => session.uses(),
    apply: async (style) => (await session.setStyle(style)) ?? false,
    change: (style, edit) => session.changeStyle(style, edit),
    deviate: (edit) => session.deviateStyle(edit),
    rename: (style, name) => session.renameStyle(style, name),
    check: (text) => session.checkCss(text),
    setRole: (role, colour) => session.setRole(role, colour),
  }
}
