import { describe, expect, it } from 'vitest'
import { answeredBy, badge, consentDialog, consentLine, noteOf, type ConsentView, type Via } from '~/lib/ai-provider'

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
    const why = 'Claude is not allowed in this document. The owner can change that in Preferences ▸ AI…'
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

describe('the dialog "AI in this document"', () => {
  const view: ConsentView = {
    provider: 'claude',
    allowed: false,
    by: null,
    at: null,
    owners: ['anna'],
    history: [],
    answering: local,
    offered: true,
  }

  it('lets an owner decide where the server offers Claude', () => {
    expect(consentDialog(view, 'owner')).toMatchObject({ mode: 'owner', allowedLine: '' })
  })

  it('shows an editor or a viewer the state, and who may change it', () => {
    expect(consentDialog(view, 'editor')).toMatchObject({ mode: 'read-only', ownerLine: 'Only the owner can change this: anna.' })
    expect(consentDialog(view, 'viewer').mode).toBe('read-only')
  })

  it('says that nothing leaves the server where it has no Claude, to everybody', () => {
    expect(consentDialog({ ...view, offered: false }, 'owner').mode).toBe('no-remote')
    expect(consentDialog({ ...view, offered: false }, 'viewer').mode).toBe('no-remote')
  })

  it('lets an owner withdraw a consent given earlier while the server has no Claude (UX-74)', () => {
    const given = { ...view, offered: false, allowed: true, by: 'anna', at: '2026-11-22T09:40:00Z' }
    // the owner's check box: it starts as the consent is (ticked) and she can clear it
    expect(consentDialog(given, 'owner').mode).toBe('owner')
    expect(consentDialog(given, 'editor').mode).toBe('no-remote')
    expect(consentDialog({ ...view, offered: false, allowed: false }, 'owner').mode).toBe('no-remote')
  })

  it('tells an owner who may withdraw a consent that the server has no Claude now (UX-74)', () => {
    const given = { ...view, offered: false, allowed: true, by: 'anna', at: '2026-11-22T09:40:00Z' }
    expect(consentDialog(given, 'owner')).toMatchObject({ mode: 'owner', noRemoteNote: true })
    expect(consentDialog(given, 'editor')).toMatchObject({ mode: 'no-remote', noRemoteNote: true })
    expect(consentDialog({ ...given, offered: true }, 'owner').noRemoteNote).toBe(false)
    expect(consentDialog(view, 'viewer').noRemoteNote).toBe(false)
  })

  it('says who decided last, and for whom', () => {
    const on = consentDialog({ ...view, allowed: true, by: 'anna', at: '2026-11-22T09:40:00Z' }, 'owner')
    expect(on.allowedLine).toMatch(/^Allowed by anna, .+ · for Claude \(Anthropic\)$/)
    const off = consentDialog({ ...view, by: 'jonas', at: '2026-11-22T10:00:00Z' }, 'owner')
    expect(off.allowedLine).toMatch(/^Switched off by jonas, .+ · for Claude \(Anthropic\)$/)
  })
})
