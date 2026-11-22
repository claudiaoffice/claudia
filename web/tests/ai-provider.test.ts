import { describe, expect, it } from 'vitest'
import { answeredBy, badge, consentLine, noteOf, type Via } from '~/lib/ai-provider'

const claude: Via = { provider: 'claude', label: 'Claude', remote: true, note: '' }
const local: Via = { provider: 'local', label: 'Qwen2.5-7B', remote: false, note: '' }

describe('who answers, in words (E7.11): never by colour alone', () => {
  it('names a remote provider as remote and a local one as this server', () => {
    expect(badge(claude)).toBe('Claude · remote')
    expect(badge(local)).toBe('Qwen2.5-7B · this server')
  })

  it('says under an answer who gave it', () => {
    expect(answeredBy(claude)).toBe('answered by Claude (remote)')
    expect(answeredBy(local)).toBe('answered by Qwen2.5-7B · this server')
  })

  it('says under a sentence that is not an answer what happened, after the badge', () => {
    expect(answeredBy({ ...claude, note: 'no answer was made' })).toBe('Claude · remote · no answer was made')
    expect(answeredBy({ ...claude, note: 'stopped at its next step' })).toBe('Claude · remote · stopped at its next step')
  })

  it('keeps a sentence about why this provider answered apart from the line', () => {
    const why = 'Claude is not allowed in this document. The owners can change that in Preferences ▸ AI…'
    expect(answeredBy({ ...local, note: why })).toBe('answered by Qwen2.5-7B · this server')
    expect(noteOf({ ...local, note: why })).toBe(why)
    expect(noteOf(claude)).toBe('')
    expect(noteOf({ ...claude, note: 'no answer was made' })).toBe('')
  })
})

describe('the consent, as the History & Chat panel says it', () => {
  it('says who switched Claude on or off', () => {
    expect(consentLine({ allowed: false, who: 'jonas', when: '2026-11-22T10:00:00Z' })).toBe('jonas switched Claude off for this document.')
    expect(consentLine({ allowed: true, who: 'anna', when: '2026-11-22T09:40:00Z' })).toBe('anna allowed Claude for this document.')
  })
})
