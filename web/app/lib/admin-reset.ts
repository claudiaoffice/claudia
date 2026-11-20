// The note an administrator sees after the administrators were reset from the server's console (D1375,
// AdminAccessDocuments.vue): when, and who they were, in the person's language.
import type { ResetNote } from './admin-api'

export function resetNoteWords(note: ResetNote, locale: string): { date: string; names: string } {
  const when = new Date(note.at)
  const date = Number.isNaN(when.getTime()) ? note.at : new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(when)
  return { date, names: new Intl.ListFormat(locale, { style: 'long', type: 'conjunction' }).format(note.previous) }
}
