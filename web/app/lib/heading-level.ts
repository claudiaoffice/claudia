// The heading level of a style as the style editor offers it (E9.22). A style's own setting is a level, "no heading"
// (`'body'`) or nothing ("as its parent"); what it *gives* (`heading`) is worked out by the server. The choice "as its
// parent" says in words what that is for this style, so that nobody has to look the parent up.
import { translate as t } from './i18n'
import type { StyleView } from './style-css'

/** The deepest level (as `MAX_HEADING_LEVEL` on the server). */
export const MAX_HEADING_LEVEL = 9

/** A `<select>` value: `'inherit'`, `'body'` or a level as text. */
export type HeadingChoiceValue = string

export interface HeadingChoice {
  value: HeadingChoiceValue
  label: string
}

/** What a level is called: the title, or a level by its number; no level is no heading. */
function levelName(level: number | null | undefined): string {
  if (level === null || level === undefined) return t('No heading')
  return level === 0 ? t('Title') : t('Level {level}', { level })
}

/** The choices for `style`: as its parent (and what that gives), no heading, the title, levels 1 to 9. */
export function headingChoices(style: StyleView, styles: readonly StyleView[]): HeadingChoice[] {
  const parent = style.based_on ? styles.find((s) => s.id === style.based_on) : undefined
  const inherited = parent
    ? t('As “{name}”: {level}', { name: parent.name, level: levelName(parent.heading) })
    : t('No heading (no parent)')
  return [
    { value: 'inherit', label: inherited },
    { value: 'body', label: t('No heading') },
    ...Array.from({ length: MAX_HEADING_LEVEL + 1 }, (_, level) => ({ value: String(level), label: levelName(level) })),
  ]
}

/** The choice that shows a style's own setting. */
export function settingValue(style: StyleView): HeadingChoiceValue {
  const own = style.heading_level
  return own === undefined || own === null ? 'inherit' : String(own)
}

/** The setting a choice stands for, as `set_heading_level` takes it. */
export function headingSetting(value: HeadingChoiceValue): number | 'body' | null {
  if (value === 'inherit') return null
  return value === 'body' ? 'body' : Number(value)
}
