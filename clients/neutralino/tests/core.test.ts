// The native core with a fake server and a fake check: how a window starts (its own server or a given one), what it
// tells the shell page, and that it stops what it started.
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { Outcome } from '../src/connection.js'
import { Core, type CoreMessage, type ServerLike } from '../src/core.js'
import { getIdentity } from '../src/identity.js'
import { SetupProblem } from '../src/local-server.js'
import { parseAddress } from '../src/servers.js'
import type { SetupCodeAccess, SharedService } from '../src/shared-service.js'
import { Settings } from '../src/settings.js'

const tick = () => new Promise((resolve) => setTimeout(resolve, 0))

class FakeServer implements ServerLike {
  started = 0
  stopped = 0
  constructor(readonly url = 'http://127.0.0.1:5000', private readonly failure?: Error) {}
  async start(): Promise<string> {
    this.started++
    if (this.failure) throw this.failure
    return this.url
  }
  async stop(): Promise<void> {
    this.stopped++
  }
}

describe('Core', () => {
  let directory: string
  let settings: Settings
  let sent: CoreMessage[]
  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'claudia-core-'))
    settings = new Settings(join(directory, 'shell.json'))
    sent = []
  })
  afterEach(() => rmSync(directory, { recursive: true, force: true }))

  const make = (options: Partial<ConstructorParameters<typeof Core>[0]> = {}) =>
    new Core({ identity: getIdentity('creates'), settings, send: (m) => sent.push(m), sharedService: null, ...options })

  describe('with its own server', () => {
    it('says it is starting, then shows the server, and lists it as this computer', async () => {
      const server = new FakeServer()
      const core = make({ serverFactory: async () => server })
      core.handle({ kind: 'start' })
      expect(sent[0]).toMatchObject({ kind: 'status', title: 'Starting Claudia Creates…', error: false })
      await tick()
      expect(sent[1]).toEqual({ kind: 'show', origin: 'http://127.0.0.1:5000' })
      core.handle({ kind: 'want_servers' })
      expect(sent[2]).toMatchObject({ kind: 'servers', servers: [{ origin: 'http://127.0.0.1:5000', local: true }] })
    })

    it('starts the server of the window\'s own app', async () => {
      const apps: string[] = []
      const core = make({ identity: getIdentity('computes'), serverFactory: async (app) => (apps.push(app), new FakeServer()) })
      core.handle({ kind: 'start' })
      await tick()
      expect(apps).toEqual(['computes'])
    })

    it('starts once: a page that starts again is brought up to date, not given a second server', async () => {
      let made = 0
      const core = make({ serverFactory: async () => (made++, new FakeServer()) })
      core.handle({ kind: 'start' })
      await tick()
      core.handle({ kind: 'start' })
      expect(made).toBe(1)
      expect(sent.at(-1)).toEqual({ kind: 'show', origin: 'http://127.0.0.1:5000' })
    })

    it('says what is missing, with the fix, when the server cannot be set up', async () => {
      const core = make({
        serverFactory: async () => {
          throw new SetupProblem('Claudia\'s server needs Python 3.14.')
        },
      })
      core.handle({ kind: 'start' })
      await tick()
      expect(sent.at(-1)).toEqual({ kind: 'status', title: 'Claudia Creates cannot start yet', details: "Claudia's server needs Python 3.14.", error: true })
    })

    it('says so when the server does not come up', async () => {
      const logged: string[] = []
      const core = make({ serverFactory: async () => new FakeServer('http://127.0.0.1:1', new Error('exited with code 1')), log: (m) => logged.push(m) })
      core.handle({ kind: 'start' })
      await tick()
      expect(sent.at(-1)).toMatchObject({ kind: 'status', title: 'Claudia Creates could not start its server', details: 'exited with code 1', error: true })
      expect(logged.join('')).toContain('exited with code 1')
    })

    it('stops the server it started, and is safe to stop twice', async () => {
      const server = new FakeServer()
      const core = make({ serverFactory: async () => server })
      core.handle({ kind: 'start' })
      await tick()
      await core.stop()
      await core.stop()
      expect(server.stopped).toBe(1)
    })

    it('starts nothing when the window ends while the server is still being set up', async () => {
      let ready: (server: ServerLike) => void = () => {}
      const server = new FakeServer()
      const core = make({ serverFactory: () => new Promise((resolve) => (ready = resolve)) })
      core.handle({ kind: 'start' })
      await core.stop()
      ready(server)
      await tick()
      expect(server.started).toBe(0)
    })

    it('says nothing more once stopped, and stops a server that came up late', async () => {
      let release: (url: string) => void = () => {}
      const server: ServerLike = { start: () => new Promise((resolve) => (release = resolve)), stop: async () => {} }
      const core = make({ serverFactory: async () => server })
      core.handle({ kind: 'start' })
      await tick()
      const before = sent.length
      await core.stop()
      release('http://127.0.0.1:9')
      await tick()
      expect(sent.length).toBe(before)
    })
  })

  describe('with a given server (--server)', () => {
    const reached = async (address: { origin: string }): Promise<Outcome> => ({ kind: 'reached', origin: address.origin, app: 'creates' })

    it('starts no server: it connects, with the same checks, and remembers the address', async () => {
      let made = 0
      const core = make({ given: parseAddress('demo.claudia-office.de'), serverFactory: async () => (made++, new FakeServer()), check: reached })
      core.handle({ kind: 'start' })
      expect(sent[0]).toMatchObject({ kind: 'status', title: 'Connecting to demo.claudia-office.de…' })
      await tick()
      expect(sent[1]).toEqual({ kind: 'show', origin: 'https://demo.claudia-office.de' })
      expect(made).toBe(0)
      expect(settings.loadServers('creates').map((e) => e.origin)).toEqual(['https://demo.claudia-office.de'])
    })

    it('reports a refusal (wrong app, certificate, unreachable) instead of showing anything', async () => {
      const core = make({
        given: parseAddress('demo.claudia-office.de'),
        check: async () => ({ kind: 'refused', code: 'certificate_invalid', message: 'The certificate of demo.claudia-office.de is not issued by an authority this computer trusts.' }),
      })
      core.handle({ kind: 'start' })
      await tick()
      expect(sent.at(-1)).toMatchObject({ kind: 'connect_failed', code: 'certificate_invalid' })
      expect(sent.some((m) => m.kind === 'show')).toBe(false)
    })
  })

  describe('the setup code of its own server (D1373)', () => {
    it('shows its own server with the setup code it has now, and another server without', async () => {
      const codes = ['K7QM-4TXR-92HB', '2W9C-HQ4M-7KXA']
      const server = Object.assign(new FakeServer(), { setupCode: () => codes.shift() ?? null })
      const core = make({
        serverFactory: async () => server,
        check: async (address) => ({ kind: 'reached', origin: address.origin, app: 'creates' }),
      })
      core.handle({ kind: 'start' })
      await tick()
      expect(sent.at(-1)).toEqual({ kind: 'show', origin: 'http://127.0.0.1:5000', setupCode: 'K7QM-4TXR-92HB' })
      core.handle({ kind: 'connect', address: 'other.example:8420' })
      await tick()
      expect(sent.at(-1)).toEqual({ kind: 'show', origin: 'https://other.example:8420' })
      core.handle({ kind: 'connect', address: 'http://127.0.0.1:5000' }) // back to "This computer": read again
      await tick()
      expect(sent.at(-1)).toEqual({ kind: 'show', origin: 'http://127.0.0.1:5000', setupCode: '2W9C-HQ4M-7KXA' })
      core.handle({ kind: 'connect', address: 'http://127.0.0.1:5000' }) // an administrator exists by now
      await tick()
      expect(sent.at(-1)).toEqual({ kind: 'show', origin: 'http://127.0.0.1:5000' })
    })
  })

  describe("the computer's shared service (E8.5, D1622, D1624)", () => {
    const SHARED = 'http://127.0.0.1:8765'
    const service = (access: SetupCodeAccess = { kind: 'none' }): SharedService => ({ origin: SHARED, setupCode: () => access })
    const reached = async (address: { origin: string }): Promise<Outcome> => ({ kind: 'reached', origin: address.origin, app: 'creates' })
    const started = async (options: Partial<ConstructorParameters<typeof Core>[0]>) => {
      const core = make({ serverFactory: async () => new FakeServer(), check: reached, ...options })
      core.handle({ kind: 'start' })
      await tick()
      return core
    }
    const places = () => {
      const last = sent.at(-1) as { servers: { origin: string; label: string; shared?: boolean }[] }
      return last.servers
    }

    it('is listed after her private place', async () => {
      const core = await started({ sharedService: service() })
      core.handle({ kind: 'want_servers' })
      expect(places().map((s) => [s.origin, s.label])).toEqual([
        ['http://127.0.0.1:5000', 'Private on this computer'],
        [SHARED, 'Shared on this computer'],
      ])
    })

    it('is not where her window opens: that is her private place, so a new document goes there', async () => {
      await started({ sharedService: service() })
      expect(sent.filter((m) => m.kind === 'show')).toEqual([{ kind: 'show', origin: 'http://127.0.0.1:5000' }])
    })

    it('is not listed without the service', async () => {
      const core = await started({ sharedService: null })
      core.handle({ kind: 'want_servers' })
      expect(places().map((s) => s.origin)).toEqual(['http://127.0.0.1:5000'])
    })

    it('is not remembered as another server when she opens it', async () => {
      const core = await started({ sharedService: service() })
      core.handle({ kind: 'connect', address: SHARED })
      await tick()
      expect(settings.loadServers('creates')).toEqual([])
    })

    it('is shown with its setup code to whom may read it, and with "ask an administrator" to anyone else', async () => {
      for (const [access, extra] of [
        [{ kind: 'code', code: 'K7QM-4TXR-92HB' }, { setupCode: 'K7QM-4TXR-92HB' }],
        [{ kind: 'may not' }, { askAdministrator: true }],
        [{ kind: 'none' }, {}],
      ] as const) {
        const core = await started({ sharedService: service(access) })
        core.handle({ kind: 'connect', address: SHARED })
        await tick()
        expect(sent.at(-1)).toEqual({ kind: 'show', origin: SHARED, ...extra })
        await core.stop()
      }
    })
  })

  describe('requests of the page', () => {
    it('connects to another server when asked, and remembers it', async () => {
      const core = make({
        serverFactory: async () => new FakeServer(),
        check: async (address) => ({ kind: 'reached', origin: address.origin, app: 'creates' }),
      })
      core.handle({ kind: 'start' })
      await tick()
      core.handle({ kind: 'connect', address: 'other.example:8420' })
      await tick()
      expect(sent.at(-1)).toEqual({ kind: 'show', origin: 'https://other.example:8420' })
      core.handle({ kind: 'want_servers' })
      expect((sent.at(-1) as { servers: { origin: string }[] }).servers.map((s) => s.origin)).toEqual(['http://127.0.0.1:5000', 'https://other.example:8420'])
    })

    it('refuses a bad address with a code', async () => {
      const core = make()
      core.handle({ kind: 'connect', address: 'ftp://x' })
      await tick()
      expect(sent.at(-1)).toMatchObject({ kind: 'connect_failed', code: 'bad_address' })
    })

    it('keeps the list that the page hands back (what is valid of it)', () => {
      const core = make()
      core.handle({ kind: 'servers', servers: [{ origin: 'https://a.example', label: 'Office', custom: true }, { origin: 'nope' }] })
      expect(settings.loadServers('creates')).toEqual([{ origin: 'https://a.example', label: 'Office', custom: true }])
    })
  })
})
