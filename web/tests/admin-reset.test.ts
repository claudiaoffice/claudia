// The reset note on Access & documents ▸ Administrators (D1375): the date and the names in the person's language.
import { describe, expect, it } from 'vitest'
import { resetNoteWords } from '../app/lib/admin-reset'

describe('resetNoteWords', () => {
  const note = { at: '2026-11-20T14:03:12Z', previous: ['anna', 'ben'] }

  it('names the day and the previous administrators as a list of the language', () => {
    expect(resetNoteWords(note, 'en')).toEqual({ date: 'Nov 20, 2026', names: 'anna and ben' })
    expect(resetNoteWords(note, 'de')).toEqual({ date: '20.11.2026', names: 'anna und ben' })
    expect(resetNoteWords({ ...note, previous: ['anna', 'ben', 'carla'] }, 'en').names).toBe('anna, ben, and carla')
  })

  it('keeps a date it cannot read as it came', () => {
    expect(resetNoteWords({ at: 'sometime', previous: ['anna'] }, 'en')).toEqual({ date: 'sometime', names: 'anna' })
  })
})
