// What left the document, as the History & Chat panel says it (E2.9, D1271): one muted line per export, print or PDF.
// The server keeps the record in the document and sends it to owners and editors; a viewer is never sent it (D1261).
import { translate as t } from './i18n'

/** One thing that left the document, as `audit_log` and the `audit_recorded` event give it. */
export interface AuditRow {
  kind: 'export' | 'print' | 'pdf'
  who: string
  when: string
  format: string
  parts: string[]
  pages: number | null
}

/** The unencrypted export's own name in `format`: the file is not protected by a password (D1270). */
export const UNPROTECTED = 'claudia-unencrypted'

const OFFICE: Record<string, string> = {
  docx: 'Word',
  xlsx: 'Excel',
  pptx: 'PowerPoint',
  odt: 'OpenDocument',
  ods: 'OpenDocument',
  odp: 'OpenDocument',
}

const pagesText = (n: number) => (n === 1 ? t('1 page') : t('{n} pages', { n }))

const partsText = (parts: string[]) => (parts.length >= 3 ? t('all parts') : parts.includes('history') || parts.includes('chat') ? t('content and history') : t('content'))

/** The sentence after the name: "exported as Word · content", "saved a PDF · 6 pages". */
export function auditSentence(row: AuditRow): string {
  if (row.kind === 'pdf') return `${t('saved a PDF')} · ${pagesText(row.pages ?? 0)}`
  if (row.kind === 'print') return `${t('printed')} · ${pagesText(row.pages ?? 0)}`
  if (row.format === UNPROTECTED) return `${t('exported unprotected')} · ${partsText(row.parts)}`
  return `${t('exported as {format}', { format: OFFICE[row.format] ?? row.format })} · ${partsText(row.parts)}`
}

/** Where `row` belongs among `entries` (oldest first, each with a `time`): the index of the first entry made after it,
 * or the end. The record has no revision, so the time is all that places it. */
export function placeInHistory(row: AuditRow, entries: { time: string }[]): number {
  const at = Date.parse(row.when)
  const index = entries.findIndex((e) => Date.parse(e.time) > at)
  return index < 0 ? entries.length : index
}
