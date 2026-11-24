import { afterEach, describe, expect, it } from 'vitest'
import { clearToken, readToken, storeToken, useAdminSession } from '~/lib/admin-session'
import { AdminApiError, type AdminApi } from '~/lib/admin-api'

function memoryStorage() {
  const map = new Map<string, string>()
  return {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
  }
}

function fakeApi(overrides: Partial<AdminApi> = {}): AdminApi {
  return {
    status: async () => ({ needs_administrator: false, exposed: true, administrator: null }),
    setup: async () => ({ token: 't', admin: { name: 'tobi', added: 'now', you: true } }),
    login: async () => ({ token: 't', admin: { name: 'tobi', added: 'now', you: true } }),
    logout: async () => undefined,
    me: async () => ({ name: 'tobi' }),
    checkSetupCode: async () => undefined,
    resetNote: async () => null,
    dismissResetNote: async () => undefined,
    listAdmins: async () => [],
    addAdmin: async () => ({ name: 'tobi', added: 'now', you: true }),
    removeAdmin: async () => undefined,
    changeAdminPassword: async () => undefined,
    getSettings: async () => {
      throw new Error('not needed for these tests')
    },
    setMaxDocuments: async () => {
      throw new Error('not needed for these tests')
    },
    revealAccessSecret: async () => ({ access_secret: null }),
    putAccessSecret: async () => {
      throw new Error('not needed for these tests')
    },
    rotateAccessSecret: async () => {
      throw new Error('not needed for these tests')
    },
    setAi: async () => {
      throw new Error('not needed for these tests')
    },
    setTypeset: async () => {
      throw new Error('not needed for these tests')
    },
    ...overrides,
  }
}

describe('token storage', () => {
  it('starts with nothing stored', () => {
    expect(readToken(memoryStorage())).toBeNull()
  })
  it('stores and reads back a token', () => {
    const storage = memoryStorage()
    storeToken('abc', storage)
    expect(readToken(storage)).toBe('abc')
  })
  it('clears a stored token', () => {
    const storage = memoryStorage()
    storeToken('abc', storage)
    clearToken(storage)
    expect(readToken(storage)).toBeNull()
  })
})

describe('useAdminSession', () => {
  // The tab's storage outlives one session, as in a browser: each test starts signed out.
  afterEach(() => clearToken())

  it('starts signed out, with no name until refresh or sign-in', () => {
    const session = useAdminSession(fakeApi())
    expect(session.token.value).toBeNull()
    expect(session.name.value).toBeNull()
  })

  it('setup stores the token and name on success', async () => {
    const session = useAdminSession(fakeApi())
    const refused = await session.setup('tobi', 'hunter22', 'c')
    expect(refused).toBeNull()
    expect(session.token.value).toBe('t')
    expect(session.name.value).toBe('tobi')
  })

  it('setup sends the setup code', async () => {
    const sent: string[][] = []
    const session = useAdminSession(fakeApi({ setup: async (...args: string[]) => (sent.push(args), { token: 't', admin: { name: 'tobi', added: 'now', you: true } }) }))
    await session.setup('tobi', 'hunter22', 'K7QM-4TXR-92HB')
    expect(sent).toEqual([['tobi', 'hunter22', 'K7QM-4TXR-92HB']])
  })

  it('setup says why it was refused, and leaves the session signed out (D1371)', async () => {
    const refusing = (error: Error) =>
      useAdminSession(
        fakeApi({
          setup: async () => {
            throw error
          },
        }),
      )
    const taken = refusing(new AdminApiError(409, 'this server already has an administrator'))
    expect(await taken.setup('tobi', 'hunter22', 'c')).toEqual({ kind: 'taken', message: 'this server already has an administrator' })
    expect(taken.token.value).toBeNull()
    expect(await refusing(new AdminApiError(403, 'not the code')).setup('tobi', 'hunter22', 'c')).toEqual({ kind: 'wrong-code', message: 'not the code' })
    expect(await refusing(new AdminApiError(429, 'too many', 12)).setup('tobi', 'hunter22', 'c')).toEqual({ kind: 'too-soon', message: 'too many', retryAfter: 12 })
    expect(await refusing(new AdminApiError(400, 'the password needs at least 8 characters')).setup('tobi', 'x', 'c')).toEqual({
      kind: 'other',
      message: 'the password needs at least 8 characters',
    })
    expect((await refusing(new Error('offline')).setup('tobi', 'hunter22', 'c'))?.kind).toBe('other')
  })

  it('login falls back to a generic message for a non-API error', async () => {
    const api = fakeApi({
      login: async () => {
        throw new TypeError('network down')
      },
    })
    const session = useAdminSession(api)
    const error = await session.login('tobi', 'hunter22')
    expect(error).toBe('Could not reach the server.')
  })

  it('login says how long to wait when the server asks for a wait, and forgets it at the next try (D1266)', async () => {
    let answers = 0
    const api = fakeApi({
      login: async () => {
        answers += 1
        if (answers === 1) throw new AdminApiError(429, 'too many tries', 5)
        return { token: 't', admin: { name: 'tobi', added: 'now', you: true } }
      },
    })
    const session = useAdminSession(api)
    expect(session.waitAdvice.value).toBe(0)
    expect(await session.login('tobi', 'x')).toBe('too many tries')
    expect(session.waitAdvice.value).toBe(5)
    expect(await session.login('tobi', 'right one')).toBeNull()
    expect(session.waitAdvice.value).toBe(0)
  })

  it('refresh resolves the stored token to a name', async () => {
    const session = useAdminSession(fakeApi({ me: async () => ({ name: 'anna' }) }))
    await session.setup('tobi', 'hunter22', 'c') // puts a token in place to refresh
    const ok = await session.refresh()
    expect(ok).toBe(true)
    expect(session.name.value).toBe('anna')
  })

  it('refresh clears the session when the token no longer resolves', async () => {
    const api = fakeApi({
      me: async () => {
        throw new AdminApiError(401, 'signed out')
      },
    })
    const session = useAdminSession(api)
    await session.setup('tobi', 'hunter22', 'c')
    const ok = await session.refresh()
    expect(ok).toBe(false)
    expect(session.token.value).toBeNull()
    expect(session.name.value).toBeNull()
  })

  it('refresh is false with nothing to check when never signed in', async () => {
    const session = useAdminSession(fakeApi())
    expect(await session.refresh()).toBe(false)
  })

  it('logout clears the session locally even if the server call fails', async () => {
    const api = fakeApi({
      logout: async () => {
        throw new Error('offline')
      },
    })
    const session = useAdminSession(api)
    await session.setup('tobi', 'hunter22', 'c')
    await session.logout()
    expect(session.token.value).toBeNull()
    expect(session.name.value).toBeNull()
  })
})
