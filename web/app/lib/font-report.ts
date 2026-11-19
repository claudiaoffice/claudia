// The font banner (E1.9, D1306): what `font_report` says a document lacks on this server, in words. A document never
// waits for it: it opens and is edited with the fonts it lacks shown in their stand-ins. Getting a font is the
// administrator's (Server settings ▸ Fonts); the banner offers the way there to an administrator and tells everyone
// else to ask one. The server refuses anybody else whatever the page sent (the rule of D251), so showing or hiding the
// button here is courtesy, not the check.

import { translate as t } from './i18n'

export interface MissingFont {
  family: string
  /** What it is shown in, `null` where the generic family of the style is used. */
  stand_in: string | null
  closeness: 'same-widths' | 'other'
}
/** What `font_report` sends. `checked` is false for a server that cannot say what it has. */
export interface FontReport {
  checked: boolean
  missing: MissingFont[]
}

const SHOWN = 3

/** The one sentence of the banner, or `null` when there is nothing to say. */
export function bannerSentence(report: FontReport): string | null {
  if (!report.checked || report.missing.length === 0) return null
  const names = report.missing.slice(0, SHOWN).map((m) => m.family)
  const rest = report.missing.length - names.length
  const list = rest > 0 ? t('{names} and {n} more', { names: names.join(', '), n: rest }) : names.join(', ')
  return report.missing.length === 1
    ? t('This document uses a font this server does not have: {list}. It is shown in a stand-in.', { list })
    : t('This document uses fonts this server does not have: {list}. They are shown in stand-ins.', { list })
}

/** Does the banner draw "Get"? Only for somebody signed in as an administrator on this server. */
export function mayOfferGet(signedInAsAdministrator: boolean): boolean {
  return signedInAsAdministrator
}
