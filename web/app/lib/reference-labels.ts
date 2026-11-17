// What the menus and the picker call the ways a reference can show (step H), in the reader's language.
import { translate as t } from './i18n'
import type { Show } from './references'

/** The name of a way to show, for the picker's "Show as" and the reference's menu. */
export function showLabel(show: Show): string {
  switch (show) {
    case 'number':
      return t('Number')
    case 'text':
      return t('Text')
    case 'number-text':
      return t('Number and Text')
    case 'page':
      return t('Page')
    case 'name':
      return t('Name')
  }
}
