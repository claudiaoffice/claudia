import { describe, expect, it } from 'vitest'
import { auditSentence, placeInHistory, UNPROTECTED, type AuditRow } from '~/lib/audit'

const row = (extra: Partial<AuditRow>): AuditRow => ({ kind: 'export', who: 'anna', when: '2026-11-19T14:02:00.000Z', format: 'docx', parts: ['content'], pages: null, ...extra })

describe('what left the document, in words (D1271)', () => {
  it('says an export in an Office format by its program, and what it held', () => {
    expect(auditSentence(row({ format: 'docx' }))).toBe('exported as Word · content')
    expect(auditSentence(row({ format: 'xlsx' }))).toBe('exported as Excel · content')
    expect(auditSentence(row({ format: 'pptx' }))).toBe('exported as PowerPoint · content')
    expect(auditSentence(row({ format: 'ods' }))).toBe('exported as OpenDocument · content')
  })

  it('says the unencrypted export as unprotected, with its parts', () => {
    expect(auditSentence(row({ format: UNPROTECTED }))).toBe('exported unprotected · content')
    expect(auditSentence(row({ format: UNPROTECTED, parts: ['content', 'history', 'chat'] }))).toBe('exported unprotected · all parts')
  })

  it('says a PDF and a print with their pages, and one page in the singular', () => {
    expect(auditSentence(row({ kind: 'pdf', format: 'pdf', pages: 6 }))).toBe('saved a PDF · 6 pages')
    expect(auditSentence(row({ kind: 'print', format: 'print', pages: 1 }))).toBe('printed · 1 page')
  })

  it('shows a format it does not know as it is', () => {
    expect(auditSentence(row({ format: 'claudia-export 1' }))).toBe('exported as claudia-export 1 · content')
  })
})

describe('where the record goes among the changes', () => {
  const entries = [{ time: '2026-11-19T14:00:00.000Z' }, { time: '2026-11-19T14:05:00.000Z' }, { time: '2026-11-19T14:20:00.000Z' }]
  it('is put before the first change made after it', () => {
    expect(placeInHistory(row({ when: '2026-11-19T14:02:00.000Z' }), entries)).toBe(1)
  })
  it('goes last when nothing came after it, and first when nothing came before', () => {
    expect(placeInHistory(row({ when: '2026-11-19T15:00:00.000Z' }), entries)).toBe(3)
    expect(placeInHistory(row({ when: '2026-11-19T13:00:00.000Z' }), entries)).toBe(0)
  })
})
