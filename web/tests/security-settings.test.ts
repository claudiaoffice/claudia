import { describe, expect, it } from 'vitest'
import { createAdminApi } from '~/lib/admin-api'
import { costSentence, parseTarget, TARGET_MAX, TARGET_MIN } from '~/lib/security-settings'

describe('parseTarget', () => {
  it('reads seconds, with a decimal point or a comma', () => {
    expect(parseTarget('0.75')).toEqual({ ok: true, value: 0.75 })
    expect(parseTarget(' 1,5 ')).toEqual({ ok: true, value: 1.5 })
    expect(parseTarget('2')).toEqual({ ok: true, value: 2 })
  })

  it.each(['', 'fast', '1 s', '-1', '0', 'NaN', 'Infinity', '1e999'])('refuses %j', (text) => {
    expect(parseTarget(text).ok).toBe(false)
  })

  it('keeps to the range the server accepts', () => {
    expect(parseTarget(String(TARGET_MIN)).ok).toBe(true)
    expect(parseTarget(String(TARGET_MAX)).ok).toBe(true)
    expect(parseTarget(String(TARGET_MIN / 2)).ok).toBe(false)
    expect(parseTarget(String(TARGET_MAX + 1)).ok).toBe(false)
  })

  it('says what is accepted, so the person knows what to type', () => {
    const refused = parseTarget('fast')
    expect(refused.ok === false && refused.message).toMatch(/0\.1.*30/)
  })
})

describe('costSentence', () => {
  const cost = { target_seconds: 0.75, iterations: 4, memory_kib: 256 * 1024, lanes: 4, measured: true }

  it('says the memory in MiB and the passes once it is measured', () => {
    expect(costSentence(cost)).toBe('New documents use 256 MiB and 4 passes.')
  })

  it('says it is still being measured, with what is used meanwhile', () => {
    expect(costSentence({ ...cost, iterations: 3, memory_kib: 64 * 1024, measured: false })).toBe(
      'Measuring this machine… New documents use 64 MiB and 3 passes until then.',
    )
  })

  it('has nothing to say for a server without sealed documents', () => {
    expect(costSentence(null)).toBe('')
  })
})

describe('the security setting call', () => {
  it('puts the target to /settings/security', async () => {
    let seen: { url: string; body: string } | null = null
    const api = createAdminApi((async (url: string, init?: RequestInit) => {
      seen = { url: String(url), body: String(init?.body) }
      return { status: 200, ok: true, json: async () => ({}) } as Response
    }) as typeof fetch)
    await api.setSecurity('tok', { kdf_target_seconds: 1.2 })
    expect(seen).toEqual({ url: '/api/admin/settings/security', body: '{"kdf_target_seconds":1.2}' })
  })
})
