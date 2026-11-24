// Server settings ▸ Templates (E10.22, D1537): what the page and its Add template… dialog say of `GET /api/admin/templates`
// and `POST /api/admin/templates/check`, as plain functions the components call and the tests check without a DOM.
//
// The server says *what* (names, counts); the words are made here, through the catalog, so the page speaks the App
// Language. The sentences the server gives for a refused file are shown as they come.

import { languageName, layoutsLabel, type TemplateCard } from './templates'

type T = (msgid: string, vars?: Record<string, string | number>) => string

export interface TemplateView extends TemplateCard {
  removable: boolean
}

export interface TemplatesPage {
  format: number
  templates: TemplateView[]
}

/** What the server says of a file before it is added: the note it carries and the names of its layouts. */
export interface TemplateCheck {
  name: string
  purpose: string
  language: string
  layouts: string[]
}

/** What the file says of itself besides its name and purpose: its language and the names of its layouts. */
export function checkDetails(check: TemplateCheck): string {
  return `${languageName(check.language)} · ${check.layouts.join(', ')}`
}

/** What adding will do, said before it happens. */
export function addSentence(check: TemplateCheck, server: string, t: T): string {
  return t('Adds “{name}” with {layouts} to {server}. Everyone who makes a presentation here can start from it.', {
    name: check.name,
    layouts: layoutsLabel(check, t),
    server,
  })
}

/** What removing will do, said before it happens: nothing already made changes. */
export function removeSentence(template: TemplateView, t: T): string {
  return t('Removes “{name}” from this server. Presentations made from it keep their layouts, styles and colours.', {
    name: template.name,
  })
}
