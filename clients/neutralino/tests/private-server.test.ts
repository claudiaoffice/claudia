// A person's private server (E8.5, D1620, D1621; before: the desktop's one shared server, D445): her three apps share
// it, it is on a port of her own, and her apps use a server they find there only when it proves to be hers -- so
// another person's server, a shared one, or a program on her port is never taken for it (CODE-99, CODE-100).
// Everything outside the server's process is faked by a small computer that knows which port holds what; the real
// health check, the port check and the setup code are covered at the bottom.
import { createServer, type Server } from 'node:net'
import { createServer as createHttpServer, type Server as HttpServer } from 'node:http'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import {
  IDLE_SECONDS,
  PrivateServer,
  STATE_FILE,
  isPortFree,
  probeHealth,
  readInstead,
  readSetupCode,
  type Health,
  type PresenceSocket,
} from '../src/private-server.js'
import { OWNER_KEY_FILE } from '../src/owner-key.js'
import { ServerStartError } from '../src/server.js'
import { MACOS_HOST } from '../src/platform/macos.js'
import { WINDOWS_HOST } from '../src/platform/windows.js'

const VERSION = '0.40.0'
const APPS = ['composes', 'computes', 'creates']

/** A presence socket that the test closes by hand. */
class FakeSocket implements PresenceSocket {
  closed = false
  private listeners: Array<() => void> = []
  addEventListener(type: 'close' | 'error', listener: () => void): void {
    if (type === 'close') this.listeners.push(listener)
  }
  close(): void {
    this.closed = true
    this.drop()
  }
  drop(): void {
    for (const listener of this.listeners.splice(0)) listener()
  }
}

/** What runs on which port of one computer: Claudia servers (a person's, or a shared one: `owner` null), programs that
 * answer but are not Claudia (`other`), and ports held by something that says nothing (`silent`). */
interface FakeServer {
  owner: string | null
  version: string
  apps: string[]
  documents?: string
}
class FakeComputer {
  readonly servers = new Map<number, FakeServer>()
  readonly other = new Set<number>()
  readonly silent = new Set<number>()
  readonly starts: Array<{ person: string; port: number; command: string[]; log: string }> = []

  health(port: number): Health {
    const server = this.servers.get(port)
    if (server) return { kind: 'claudia', apps: server.apps, version: server.version }
    return this.other.has(port) ? { kind: 'other' } : { kind: 'none' }
  }
  free(port: number): boolean {
    return !this.servers.has(port) && !this.other.has(port) && !this.silent.has(port)
  }
}

const people: string[] = []
afterEach(() => {
  for (const folder of people.splice(0)) rmSync(folder, { recursive: true, force: true })
})

/** A person of `computer` and one of her windows: a `PrivateServer` with her own state folder and account. Two
 * windows of the same person share `state`. */
function window(
  computer: FakeComputer,
  person: string,
  uid: number,
  options: { app?: string; state?: string; version?: string | null; port?: number; endTheServer?: string; startFails?: Error } = {},
) {
  const state = options.state ?? mkdtempSync(join(tmpdir(), `claudia-${person}-`))
  if (!options.state) people.push(state)
  const sockets: FakeSocket[] = []
  const logged: string[] = []
  const probed: number[] = []
  const portOf = (url: string) => Number(new URL(url).port)
  const server = new PrivateServer({
    app: options.app ?? 'computes',
    program: '/repo/.venv/bin/python',
    web: '/frontend',
    documents: `/home/${person}/documents`,
    state,
    account: { uid },
    endTheServer: options.endTheServer ?? MACOS_HOST.endTheServer,
    ...(options.port !== undefined ? { port: options.port } : {}),
    probe: async (url) => {
      probed.push(portOf(url))
      return computer.health(portOf(url))
    },
    isMine: async (url) => computer.servers.get(portOf(url))?.owner === person,
    makeServer: (command, url, log) => ({
      start: async () => {
        const port = portOf(url)
        computer.starts.push({ person, port, command, log })
        if (options.startFails) throw options.startFails
        if (!computer.free(port)) throw new ServerStartError(`port ${port} is in use`, { exited: true })
        const documents = command[command.indexOf('--dir') + 1]!
        // The server's own lock on its folder (D435): a second server of the same documents exits at start-up.
        if ([...computer.servers.values()].some((running) => running.documents === documents)) {
          throw new ServerStartError(`the server stopped at start-up (exit code 2)\nerror: another Claudia server uses ${documents}; stop it first, or give this one another folder`, { exited: true })
        }
        computer.servers.set(port, { owner: person, version: VERSION, apps: APPS, documents })
        return url
      },
      stop: async () => {},
    }),
    portFree: async (port) => computer.free(port),
    version: async () => (options.version === undefined ? VERSION : options.version),
    connect: () => {
      const socket = new FakeSocket()
      sockets.push(socket)
      return socket
    },
    sleep: async () => {
      await new Promise((resolve) => setImmediate(resolve))
    },
    raceWaitMs: 50,
    log: (message) => logged.push(message),
  })
  return { server, state, sockets, logged, probed }
}

const ANNA = 501 // her port: 20501
const BEN = 502 // his port: 20502

describe('PrivateServer', () => {
  it('starts her server on her own port, with the key that makes it hers, when none runs', async () => {
    const computer = new FakeComputer()
    const { server, state } = window(computer, 'anna', ANNA)
    expect(await server.start()).toBe('http://127.0.0.1:20501')
    const [started] = computer.starts
    expect(started!.port).toBe(20501)
    expect(started!.command).toEqual(expect.arrayContaining(['--owner-key-file', join(state, OWNER_KEY_FILE)]))
    expect(started!.command).toEqual(expect.arrayContaining(['--exit-when-idle', String(IDLE_SECONDS)]))
    expect(started!.command).not.toContain('--model') // all three apps (D445)
    expect(started!.log).toBe(join(state, 'server.log'))
    expect(readFileSync(join(state, OWNER_KEY_FILE), 'utf8').trim()).toMatch(/^[0-9a-f]{64}$/)
    if (process.platform !== 'win32') expect(statSync(join(state, OWNER_KEY_FILE)).mode & 0o777).toBe(0o600)
    await server.stop()
  })

  it('her three apps share her private place: the second window finds her server and starts nothing', async () => {
    const computer = new FakeComputer()
    const first = window(computer, 'anna', ANNA, { app: 'composes' })
    await first.server.start()
    const second = window(computer, 'anna', ANNA, { app: 'computes', state: first.state })
    expect(await second.server.start()).toBe('http://127.0.0.1:20501')
    expect(computer.starts).toHaveLength(1)
    await first.server.stop()
    await second.server.stop()
  })

  it('keeps her key from one start to the next, and makes a new one when the file holds none', async () => {
    const computer = new FakeComputer()
    const first = window(computer, 'anna', ANNA)
    await first.server.start()
    await first.server.stop()
    const key = readFileSync(join(first.state, OWNER_KEY_FILE), 'utf8')
    computer.servers.clear()
    await window(computer, 'anna', ANNA, { state: first.state }).server.start()
    expect(readFileSync(join(first.state, OWNER_KEY_FILE), 'utf8')).toBe(key)
    writeFileSync(join(first.state, OWNER_KEY_FILE), 'not a key')
    computer.servers.clear()
    await window(computer, 'anna', ANNA, { state: first.state }).server.start()
    expect(readFileSync(join(first.state, OWNER_KEY_FILE), 'utf8').trim()).toMatch(/^[0-9a-f]{64}$/)
    await first.server.stop()
  })

  // CODE-99
  it('two people of one computer each get their own server: Ben never uses Anna’s', async () => {
    const computer = new FakeComputer()
    const anna = window(computer, 'anna', ANNA, { app: 'composes' })
    await anna.server.start()
    const ben = window(computer, 'ben', BEN, { app: 'composes' })
    expect(await ben.server.start()).toBe('http://127.0.0.1:20502')
    expect(computer.servers.get(20502)).toMatchObject({ owner: 'ben', documents: '/home/ben/documents' })
    expect(computer.servers.get(20501)).toMatchObject({ owner: 'anna', documents: '/home/anna/documents' })
    await anna.server.stop()
    await ben.server.stop()
  })

  // CODE-99
  it('his server is still his after the other person has logged out', async () => {
    const computer = new FakeComputer()
    const anna = window(computer, 'anna', ANNA)
    await anna.server.start()
    const ben = window(computer, 'ben', BEN)
    const before = await ben.server.start()
    computer.servers.delete(20501) // Anna logged out: her server is gone
    computer.servers.delete(20502) // and Ben's stopped while idle
    const again = window(computer, 'ben', BEN, { state: ben.state })
    expect(await again.server.start()).toBe(before)
    expect(computer.servers.get(20502)).toMatchObject({ owner: 'ben', documents: '/home/ben/documents' })
    await anna.server.stop()
    await ben.server.stop()
    await again.server.stop()
  })

  // CODE-99
  it('a Claudia server that is not hers on her port is not taken for hers: she starts her own elsewhere', async () => {
    const computer = new FakeComputer()
    computer.servers.set(20501, { owner: 'mallory', version: VERSION, apps: APPS })
    const { server, state, logged } = window(computer, 'anna', ANNA)
    expect(await server.start()).toBe('http://127.0.0.1:20502')
    expect(computer.servers.get(20502)!.owner).toBe('anna')
    expect(readInstead(join(state, STATE_FILE))).toBe(20502)
    expect(logged.join('\n')).toMatch(/20501/)
    await server.stop()
  })

  // CODE-100
  it('a shared server of another version does not keep her apps from opening', async () => {
    const computer = new FakeComputer()
    computer.servers.set(8765, { owner: null, version: '0.31.0', apps: APPS })
    const { server, probed } = window(computer, 'anna', ANNA)
    expect(await server.start()).toBe('http://127.0.0.1:20501')
    expect(probed).not.toContain(8765)
    await server.stop()
  })

  // CODE-100
  it('a shared server of another version on her port is not hers either: no complaint about its version', async () => {
    const computer = new FakeComputer()
    computer.servers.set(20501, { owner: null, version: '0.31.0', apps: APPS })
    const { server } = window(computer, 'anna', ANNA)
    expect(await server.start()).toBe('http://127.0.0.1:20502')
    await server.stop()
  })

  it('her own server of an older version, still running after an update: she is told it stops by itself', async () => {
    const computer = new FakeComputer()
    computer.servers.set(20501, { owner: 'anna', version: '0.39.0', apps: APPS })
    const { server } = window(computer, 'anna', ANNA)
    await expect(server.start()).rejects.toThrow(/0\.39\.0/)
    await expect(server.start()).rejects.toThrow(/stops by itself ten minutes after its last window has closed/)
    await expect(server.start()).rejects.toThrow(/Activity Monitor/)
  })

  it('her own server from before E8.5 (no key, on 8765) still holding her documents: she is told it stops by itself', async () => {
    const computer = new FakeComputer()
    computer.servers.set(8765, { owner: null, version: '0.39.0', apps: APPS, documents: '/home/anna/documents' })
    const { server } = window(computer, 'anna', ANNA)
    const refused = server.start()
    await expect(refused).rejects.toThrow(/older version/)
    await expect(refused).rejects.toThrow(/stops by itself ten minutes after its last window has closed/)
    await expect(refused).rejects.toThrow(/Activity Monitor/)
  })

  it('says it in the words of Windows on Windows (D660)', async () => {
    const computer = new FakeComputer()
    computer.servers.set(20501, { owner: 'anna', version: '0.39.0', apps: APPS })
    const { server } = window(computer, 'anna', ANNA, { endTheServer: WINDOWS_HOST.endTheServer })
    await expect(server.start()).rejects.toThrow(/Task Manager/)
  })

  it('does not insist on a version it could not find out', async () => {
    const computer = new FakeComputer()
    computer.servers.set(20501, { owner: 'anna', version: '0.39.0', apps: APPS })
    const { server } = window(computer, 'anna', ANNA, { version: null })
    await expect(server.start()).resolves.toBe('http://127.0.0.1:20501')
    await server.stop()
  })

  it('refuses her own server when it does not serve this app', async () => {
    const computer = new FakeComputer()
    computer.servers.set(20501, { owner: 'anna', version: VERSION, apps: ['composes'] })
    const { server } = window(computer, 'anna', ANNA)
    await expect(server.start()).rejects.toThrow(/does not serve computes/)
  })

  describe('a program that is not her server on her port', () => {
    it('her server goes to another port for this start, and her other apps find it there', async () => {
      const computer = new FakeComputer()
      computer.other.add(20501)
      const first = window(computer, 'anna', ANNA, { app: 'composes' })
      expect(await first.server.start()).toBe('http://127.0.0.1:20502')
      const second = window(computer, 'anna', ANNA, { app: 'creates', state: first.state })
      expect(await second.server.start()).toBe('http://127.0.0.1:20502')
      expect(computer.starts).toHaveLength(1)
      await first.server.stop()
      await second.server.stop()
    })

    it('the next start tries her usual address again, and forgets the other one once it is free', async () => {
      const computer = new FakeComputer()
      computer.other.add(20501)
      const first = window(computer, 'anna', ANNA)
      await first.server.start()
      await first.server.stop()
      computer.other.delete(20501)
      computer.servers.delete(20502) // her server stopped while idle
      const next = window(computer, 'anna', ANNA, { state: first.state })
      expect(await next.server.start()).toBe('http://127.0.0.1:20501')
      expect(readInstead(join(first.state, STATE_FILE))).toBeNull()
      await next.server.stop()
    })

    it('something that holds her port and says nothing counts as well', async () => {
      const computer = new FakeComputer()
      computer.silent.add(20501)
      const { server } = window(computer, 'anna', ANNA)
      expect(await server.start()).toBe('http://127.0.0.1:20502')
      await server.stop()
    })

    it('her server still running on the other port is used, also once her own port is free again', async () => {
      const computer = new FakeComputer()
      computer.other.add(20501)
      const first = window(computer, 'anna', ANNA, { app: 'composes' })
      expect(await first.server.start()).toBe('http://127.0.0.1:20502')
      computer.other.delete(20501) // the program went; her server still runs where it went, with her documents
      const next = window(computer, 'anna', ANNA, { app: 'computes', state: first.state })
      expect(await next.server.start()).toBe('http://127.0.0.1:20502')
      expect(computer.starts).toHaveLength(1)
      await first.server.stop()
      await next.server.stop()
    })

    it('two of her windows that start at once while her port is held go to the same port, and share one server', async () => {
      const computer = new FakeComputer()
      computer.other.add(20501)
      const first = window(computer, 'anna', ANNA, { app: 'composes' })
      const second = window(computer, 'anna', ANNA, { app: 'creates', state: first.state })
      const urls = await Promise.all([first.server.start(), second.server.start()])
      expect(urls).toEqual(['http://127.0.0.1:20502', 'http://127.0.0.1:20502'])
      expect([...computer.servers.values()].filter((server) => server.owner === 'anna')).toHaveLength(1)
      await first.server.stop()
      await second.server.stop()
    })

    it('the walk stays in her range: after its last port comes its first', async () => {
      const computer = new FakeComputer()
      computer.other.add(29999)
      const { server } = window(computer, 'anna', 9999) // her port: 29999
      expect(await server.start()).toBe('http://127.0.0.1:20000')
      await server.stop()
    })

    it('a server on the other port that is not hers is not used either', async () => {
      const computer = new FakeComputer()
      computer.other.add(20501)
      const { server, state } = window(computer, 'anna', ANNA)
      writeFileSync(join(state, STATE_FILE), JSON.stringify({ instead: 20502 }))
      computer.servers.set(20502, { owner: 'ben', version: VERSION, apps: APPS })
      expect(await server.start()).toBe('http://127.0.0.1:20503')
      expect(readInstead(join(state, STATE_FILE))).toBe(20503)
      await server.stop()
    })
  })

  it('CLAUDIA_SERVER_PORT (the option `port`) takes the place of her usual port', async () => {
    const computer = new FakeComputer()
    const { server } = window(computer, 'anna', ANNA, { port: 18765 })
    expect(await server.start()).toBe('http://127.0.0.1:18765')
    await server.stop()
  })

  describe('two of her windows starting at once', () => {
    it('a start that lost to another one (it exited at start-up) uses the one that won, when it is hers', async () => {
      const computer = new FakeComputer()
      const lost = new ServerStartError('the server stopped at start-up (exit code 2)', { exited: true })
      const { server } = window(computer, 'anna', ANNA, { startFails: lost })
      setImmediate(() => computer.servers.set(20501, { owner: 'anna', version: VERSION, apps: APPS }))
      await expect(server.start()).resolves.toBe('http://127.0.0.1:20501')
      await server.stop()
    })

    it('does not take a winner that is not hers', async () => {
      const computer = new FakeComputer()
      const lost = new ServerStartError('the server stopped at start-up (exit code 2)', { exited: true })
      const { server } = window(computer, 'anna', ANNA, { startFails: lost })
      setImmediate(() => computer.servers.set(20501, { owner: 'mallory', version: VERSION, apps: APPS }))
      await expect(server.start()).rejects.toBe(lost)
    })

    it('does not wait for another server when its own simply never answered', async () => {
      const computer = new FakeComputer()
      const slow = new ServerStartError('the server did not answer')
      const { server, probed } = window(computer, 'anna', ANNA, { startFails: slow })
      await expect(server.start()).rejects.toBe(slow)
      expect(probed).toEqual([20501]) // the one look before starting, none after
    })
  })

  describe('presence', () => {
    it('keeps a connection to /api/presence while the window is open, and lets go of it (not of the server) at the end', async () => {
      const computer = new FakeComputer()
      const { server, sockets } = window(computer, 'anna', ANNA)
      await server.start()
      await new Promise((resolve) => setImmediate(resolve))
      expect(sockets).toHaveLength(1)
      await server.stop()
      expect(sockets[0]!.closed).toBe(true)
      expect(computer.servers.has(20501)).toBe(true) // closing a window does not stop the server
    })

    it('starts her server again, on the same port, when it has gone, and connects again', async () => {
      const computer = new FakeComputer()
      const { server, sockets } = window(computer, 'anna', ANNA)
      await server.start()
      await new Promise((resolve) => setImmediate(resolve))
      computer.servers.delete(20501) // the server stopped
      sockets[0]!.drop()
      for (let i = 0; i < 20 && computer.starts.length < 2; i++) await new Promise((resolve) => setImmediate(resolve))
      expect(computer.starts.map((start) => start.port)).toEqual([20501, 20501])
      for (let i = 0; i < 20 && sockets.length < 2; i++) await new Promise((resolve) => setImmediate(resolve))
      expect(sockets).toHaveLength(2)
      await server.stop()
    })

    it('stays on the port the page is on when it starts her server again, also when her usual port has come free', async () => {
      const computer = new FakeComputer()
      computer.other.add(20501)
      const { server, sockets } = window(computer, 'anna', ANNA)
      expect(await server.start()).toBe('http://127.0.0.1:20502')
      await new Promise((resolve) => setImmediate(resolve))
      computer.other.delete(20501)
      computer.servers.delete(20502) // her server stopped
      sockets[0]!.drop()
      for (let i = 0; i < 20 && computer.starts.length < 2; i++) await new Promise((resolve) => setImmediate(resolve))
      expect(computer.starts.map((start) => start.port)).toEqual([20502, 20502])
      expect(server.url).toBe('http://127.0.0.1:20502')
      await server.stop()
    })

    it('connects again without starting anything when her server is still there', async () => {
      const computer = new FakeComputer()
      const { server, sockets } = window(computer, 'anna', ANNA)
      await server.start()
      await new Promise((resolve) => setImmediate(resolve))
      sockets[0]!.drop()
      for (let i = 0; i < 20 && sockets.length < 2; i++) await new Promise((resolve) => setImmediate(resolve))
      expect(sockets).toHaveLength(2)
      expect(computer.starts).toHaveLength(1)
      await server.stop()
    })
  })
})

describe('state file', () => {
  const dirs: string[] = []
  afterEach(() => {
    for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true })
  })

  it('reads the other port back, and nothing from a missing, broken, silly or older file', () => {
    const dir = mkdtempSync(join(tmpdir(), 'claudia-state-file-'))
    dirs.push(dir)
    const file = join(dir, STATE_FILE)
    expect(readInstead(file)).toBeNull()
    writeFileSync(file, '{"instead": 41233}')
    expect(readInstead(file)).toBe(41233)
    const older = '{"port": 41233}' // before E8.5: the port the one shared server went to
    for (const bad of ['', 'x', '[]', older, '{"instead": "41233"}', '{"instead": 0}', '{"instead": 70000}', '{"instead": 1.5}']) {
      writeFileSync(file, bad)
      expect(readInstead(file)).toBeNull()
    }
  })
})

describe('isPortFree', () => {
  let held: Server | null = null
  afterEach(() => new Promise<void>((resolve) => (held ? held.close(() => resolve()) : resolve())))

  it('is false while something listens on the port, true once it does not', async () => {
    held = createServer()
    const port = await new Promise<number>((resolve) => held!.listen(0, '127.0.0.1', () => resolve((held!.address() as { port: number }).port)))
    expect(await isPortFree(port)).toBe(false)
    await new Promise<void>((resolve) => held!.close(() => resolve()))
    held = null
    expect(await isPortFree(port)).toBe(true)
  })
})

describe('probeHealth', () => {
  let http: HttpServer | null = null
  afterEach(() => new Promise<void>((resolve) => (http ? http.close(() => resolve()) : resolve())))

  async function serving(status: number, body: string): Promise<string> {
    http = createHttpServer((_request, response) => {
      response.statusCode = status
      response.setHeader('content-type', 'application/json')
      response.end(body)
    })
    const port = await new Promise<number>((resolve) => http!.listen(0, '127.0.0.1', () => resolve((http!.address() as { port: number }).port)))
    return `http://127.0.0.1:${port}`
  }

  it('knows a Claudia server by its answer, with its apps and, from this computer, its version', async () => {
    const url = await serving(200, '{"ok": true, "apps": ["composes", "creates"], "version": "0.32.0"}')
    expect(await probeHealth(url)).toEqual({ kind: 'claudia', apps: ['composes', 'creates'], version: '0.32.0' })
  })

  it('knows a Claudia server that does not say its version', async () => {
    const url = await serving(200, '{"ok": true, "apps": ["composes"]}')
    expect(await probeHealth(url)).toEqual({ kind: 'claudia', apps: ['composes'], version: null })
  })

  it('calls anything else that answers “other”', async () => {
    expect(await probeHealth(await serving(200, '{"ok": true}'))).toEqual({ kind: 'other' }) // a server from before D444 has no apps
  })

  it('calls an answer that is not JSON, or not a success, “other”', async () => {
    expect(await probeHealth(await serving(200, '<html>'))).toEqual({ kind: 'other' })
    await new Promise<void>((resolve) => http!.close(() => resolve()))
    expect(await probeHealth(await serving(500, '{"ok": true, "apps": []}'))).toEqual({ kind: 'other' })
  })

  it('says “none” when nobody answers', async () => {
    const url = await serving(200, '{}')
    await new Promise<void>((resolve) => http!.close(() => resolve()))
    http = null
    expect(await probeHealth(url)).toEqual({ kind: 'none' })
  })
})

describe('the setup code of the server (D1373)', () => {
  it('is read from the state folder each time, and only when it is a code', () => {
    const state = mkdtempSync(join(tmpdir(), 'claudia-code-'))
    try {
      expect(readSetupCode(state)).toBeNull()
      mkdirSync(join(state, 'admin'))
      writeFileSync(join(state, 'admin', 'setup-code'), 'K7QM-4TXR-92HB\n')
      expect(readSetupCode(state)).toBe('K7QM-4TXR-92HB')
      writeFileSync(join(state, 'admin', 'setup-code'), '2W9C-HQ4M-7KXA\n') // the server restarted
      expect(readSetupCode(state)).toBe('2W9C-HQ4M-7KXA')
      writeFileSync(join(state, 'admin', 'setup-code'), 'not a code\n')
      expect(readSetupCode(state)).toBeNull()
    } finally {
      rmSync(state, { recursive: true, force: true })
    }
  })
})
