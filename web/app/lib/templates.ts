// Starting a presentation from a template (E10.4, E10.22, D1538): what the cards of New presentation say, and the two
// requests behind them, as plain functions the dialog calls and the tests check without a DOM.
//
// `GET /api/templates` lists what the server has; `POST /api/templates/{id}/upload` makes the new presentation and holds
// it as an upload, which the usual create then picks up (`hello` with `create` and `upload`). Nothing here knows about
// documents: the template is copied in, and nothing follows it (D1531).

import { translate } from './i18n'

type T = (msgid: string, vars?: Record<string, string | number>) => string

/** The words of the page; the functions that say something take their own `t` so that the tests can give another. */
const t: T = translate

/** One template as the server lists it. */
export interface TemplateCard {
  id: string
  name: string
  purpose: string
  /** a language tag such as `de` or `en-GB` */
  language: string
  builtin: boolean
  layouts: string[]
}

/** "1 layout", "5 layouts": the line of a card and the column of the admin page. */
export function layoutsLabel(template: { layouts: string[] }, t: T = translate): string {
  const n = template.layouts.length
  return n === 1 ? t('1 layout') : t('{n} layouts', { n })
}

/** A language tag as its own people write it ("Deutsch", "British English"), as the App Language menu does, whatever
 * the language of the page is; the tag itself when it cannot be named. */
export function languageName(tag: string): string {
  try {
    return new Intl.DisplayNames([tag], { type: 'language', fallback: 'none' }).of(tag) ?? tag
  } catch {
    return tag
  }
}

/** The small print of a card: "8 layouts · English"; the built-in template says only that it is. */
export function cardMeta(card: TemplateCard, t: T = translate): string {
  if (card.builtin) return t('built in')
  return `${layoutsLabel(card, t)} · ${languageName(card.language)}`
}

/** The button that starts a presentation from the chosen card. */
export function createLabel(card: TemplateCard, t: T = translate): string {
  return t('Create from “{name}”', { name: card.name })
}

/** Whether there is anything to choose: the built-in template is a blank presentation, which is what a plain create makes. */
export function needsChoice(templates: TemplateCard[]): boolean {
  return templates.some((template) => !template.builtin)
}

async function sentenceOf(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
  } catch {
    /* no JSON: the status says enough */
  }
  return t('The server answered with an error ({status}).', { status: response.status })
}

/** The templates of a server, in the language of the person. A server that does not know templates (404) has none to
 * choose from; any other refusal is told in the server's own sentence. */
export async function fetchTemplates(
  origin: string,
  locale: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ templates: TemplateCard[] } | { error: string }> {
  let response: Response
  try {
    response = await fetchImpl(`${origin}/api/templates?locale=${encodeURIComponent(locale)}`)
  } catch {
    return { error: t('The server cannot be reached.') }
  }
  if (response.status === 404) return { templates: [] }
  if (!response.ok) return { error: await sentenceOf(response) }
  const body = (await response.json()) as { templates?: TemplateCard[] }
  return { templates: Array.isArray(body.templates) ? body.templates : [] }
}

/** Makes the presentation a template starts and holds it as an upload; its token (the `upload` of the answer) to create the document from. */
export async function startFromTemplate(
  origin: string,
  id: string,
  locale: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ upload: string } | { error: string }> {
  let response: Response
  try {
    response = await fetchImpl(`${origin}/api/templates/${encodeURIComponent(id)}/upload?locale=${encodeURIComponent(locale)}`, { method: 'POST' })
  } catch {
    return { error: t('The server cannot be reached.') }
  }
  if (!response.ok) return { error: await sentenceOf(response) }
  return { upload: ((await response.json()) as { upload: string }).upload }
}
