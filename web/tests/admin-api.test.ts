import { describe, expect, it } from 'vitest'
import { AdminApiError, adminScreen, createAdminApi, hasNoAdministrator } from '~/lib/admin-api'

function fakeFetch(handler: (url: string, init?: RequestInit) => { status: number; body?: unknown }): typeof fetch {
  return (async (input: string | URL | Request, init?: RequestInit) => {
    const { status, body } = handler(String(input), init)
    return {
      status,
      ok: status >= 200 && status < 300,
      json: async () => body,
    } as Response
  }) as typeof fetch
}

describe('createAdminApi', () => {
  it('calls the relative /api/admin path and returns the parsed body', async () => {
    let seenUrl = ''
    const fetchImpl = fakeFetch((url) => {
      seenUrl = url
      return { status: 200, body: { needs_administrator: false, exposed: true, administrator: 'tobi' } }
    })
    const api = createAdminApi(fetchImpl)
    const status = await api.status()
    expect(seenUrl).toBe('/api/admin/status')
    expect(status).toEqual({ needs_administrator: false, exposed: true, administrator: 'tobi' })
  })

  it('sends a bearer token when one is given, and none when not', async () => {
    let seenHeaders: Record<string, string> = {}
    const fetchImpl = fakeFetch((_url, init) => {
      seenHeaders = (init?.headers as Record<string, string>) ?? {}
      return { status: 200, body: { name: 'tobi' } }
    })
    const api = createAdminApi(fetchImpl)
    await api.me('secret-token')
    expect(seenHeaders.authorization).toBe('Bearer secret-token')

    await api.status()
    expect(seenHeaders.authorization).toBeUndefined()
  })

  it('sends a JSON content-type and body only for calls that have one', async () => {
    let seenInit: RequestInit | undefined
    const fetchImpl = fakeFetch((_url, init) => {
      seenInit = init
      return { status: 200, body: { token: 't', admin: { name: 'tobi', added: 'now', you: true } } }
    })
    const api = createAdminApi(fetchImpl)
    await api.setup('tobi', 'hunter2', 'K7QM-4TXR-92HB')
    expect((seenInit?.headers as Record<string, string>)['content-type']).toBe('application/json')
    expect(seenInit?.body).toBe(JSON.stringify({ name: 'tobi', password: 'hunter2', code: 'K7QM-4TXR-92HB' }))
  })

  it('checks a setup code without naming anybody (D1372)', async () => {
    const seen: string[] = []
    const fetchImpl = fakeFetch((url, init) => {
      seen.push(`${init?.method} ${url} ${init?.body}`)
      return { status: 204 }
    })
    await createAdminApi(fetchImpl).checkSetupCode('K7QM-4TXR-92HB')
    expect(seen).toEqual(['POST /api/admin/setup-code {"code":"K7QM-4TXR-92HB"}'])
  })

  it('reads and dismisses the reset note as an administrator (D1375)', async () => {
    const seen: string[] = []
    const fetchImpl = fakeFetch((url, init) => {
      seen.push(`${init?.method} ${url} ${(init?.headers as Record<string, string>).authorization}`)
      return init?.method === 'GET' ? { status: 200, body: { at: '2026-11-20T14:03:12Z', previous: ['anna', 'ben'] } } : { status: 204 }
    })
    const api = createAdminApi(fetchImpl)
    expect(await api.resetNote('t')).toEqual({ at: '2026-11-20T14:03:12Z', previous: ['anna', 'ben'] })
    await api.dismissResetNote('t')
    expect(seen).toEqual(['GET /api/admin/reset-note Bearer t', 'DELETE /api/admin/reset-note Bearer t'])
  })

  it('treats a 204 as success with no body', async () => {
    const fetchImpl = fakeFetch(() => ({ status: 204 }))
    const api = createAdminApi(fetchImpl)
    await expect(api.logout('t')).resolves.toBeUndefined()
  })

  it('raises an AdminApiError carrying the status and the detail message', async () => {
    const fetchImpl = fakeFetch(() => ({ status: 401, body: { detail: 'wrong password' } }))
    const api = createAdminApi(fetchImpl)
    await expect(api.login('tobi', 'nope')).rejects.toMatchObject(
      expect.objectContaining({ status: 401, message: 'wrong password' }),
    )
  })

  it('carries the seconds to wait of a refused sign-in (D1266)', async () => {
    const fetchImpl = fakeFetch(() => ({ status: 429, body: { detail: 'too many tries', retry_after: 7 } }))
    const api = createAdminApi(fetchImpl)
    await expect(api.login('tobi', 'nope')).rejects.toMatchObject({ status: 429, retryAfter: 7 })
  })

  it('falls back to a generic message when the error body has no usable detail', async () => {
    const fetchImpl = fakeFetch(() => ({ status: 500, body: null }))
    const api = createAdminApi(fetchImpl)
    await expect(api.login('tobi', 'nope')).rejects.toThrow('request failed (500)')
  })

  it('still raises cleanly when the error response body is not JSON at all', async () => {
    const fetchImpl = (async () => ({
      status: 500,
      ok: false,
      json: async () => {
        throw new Error('not json')
      },
    })) as unknown as typeof fetch
    const api = createAdminApi(fetchImpl)
    await expect(api.login('tobi', 'nope')).rejects.toBeInstanceOf(AdminApiError)
  })

  it('builds admin-management paths with the name encoded', async () => {
    let seenUrl = ''
    const fetchImpl = fakeFetch((url) => {
      seenUrl = url
      return { status: 204 }
    })
    const api = createAdminApi(fetchImpl)
    await api.removeAdmin('t', 'anna marie')
    expect(seenUrl).toBe('/api/admin/admins/anna%20marie')
  })
})

describe('hasNoAdministrator', () => {
  it('is true once nobody has ever become an administrator, exposed or not', () => {
    expect(hasNoAdministrator({ administrator: null })).toBe(true)
  })

  it('is false once somebody has, even on a loopback-only server where needs_administrator stays false', () => {
    expect(hasNoAdministrator({ administrator: 'tobi' })).toBe(false)
  })
})

describe('adminScreen', () => {
  it('offers to become the first administrator while nobody has and nobody is signed in', () => {
    expect(adminScreen(true, null)).toBe('setup')
  })

  it('shows the settings once the first administrator is named, without a reload (bug CODE-48)', () => {
    // the status said "no administrator" when the page loaded; naming one signs them in
    expect(adminScreen(true, 'anna')).toBe('settings')
  })

  it('asks to sign in when there is an administrator and nobody is signed in, else shows the settings', () => {
    expect(adminScreen(false, null)).toBe('sign-in')
    expect(adminScreen(false, 'anna')).toBe('settings')
  })
})
