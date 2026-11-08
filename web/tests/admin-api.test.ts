import { describe, expect, it } from 'vitest'
import { AdminApiError, createAdminApi } from '~/lib/admin-api'

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
    await api.setup('tobi', 'hunter2')
    expect((seenInit?.headers as Record<string, string>)['content-type']).toBe('application/json')
    expect(seenInit?.body).toBe(JSON.stringify({ name: 'tobi', password: 'hunter2' }))
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
