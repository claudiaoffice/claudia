// The one local server that the three desktop apps share (D445): which port, whether one is running already, what to do
// when two windows start at once, and the presence connection that keeps it from stopping while a window is open.
// Everything outside the server's own process is faked; the real health check and the real state file are covered
// at the bottom.
import { createServer, type Server } from 'node:net'
import { createServer as createHttpServer, type Server as HttpServer } from 'node:http'
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  DesktopServer,
  IDLE_SECONDS,
  SERVER_PORT,
  STATE_FILE,
  isPortFree,
  probeHealth,
  readPort,
  writePort,
  type Health,
  type PresenceSocket,
} from '../src/desktop-server.js'
import { ServerStartError } from '../src/server.js'

const OURS: Health = { kind: 'claudia', apps: ['composes', 'computes', 'creates'], version: '0.32.0' }
const NONE: Health = { kind: 'none' }

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

describe('DesktopServer', () => {
  let state: string
  beforeEach(() => {
    state = mkdtempSync(join(tmpdir(), 'claudia-desktop-state-'))
  })
  afterEach(() => rmSync(state, { recursive: true, force: true }))

  /** What the fakes saw, and the fakes themselves. `answers` is what the health check says, in order, the last one for
   * ever; `starts` are the commands of the servers that were started. */
  function harness(options: { answers?: Health[]; port?: number; portFree?: boolean; version?: string | null; startFails?: Error } = {}) {
    const answers = [...(options.answers ?? [NONE])]
    const probed: string[] = []
    const starts: Array<{ command: string[]; url: string; log: string }> = []
    const sockets: FakeSocket[] = []
    const logged: string[] = []
    const server = new DesktopServer({
      app: 'computes',
      python: '/repo/.venv/bin/python',
      web: '/frontend',
      documents: '/docs',
      state,
      probe: async (url) => {
        probed.push(url)
        return answers.length > 1 ? answers.shift()! : answers[0]!
      },
      makeServer: (command, url, log) => ({
        start: async () => {
          starts.push({ command, url, log })
          if (options.startFails) throw options.startFails
          return url
        },
        stop: async () => {},
      }),
      pickPort: async () => options.port ?? 41233,
      portFree: async () => options.portFree ?? true,
      version: async () => (options.version === undefined ? '0.32.0' : options.version),
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
    return { server, probed, starts, sockets, logged }
  }

  it('starts the server on 8765, the port of every Claudia server, when none runs (D504)', async () => {
    const { server, starts } = harness()
    expect(SERVER_PORT).toBe(8765)
    expect(await server.start()).toBe('http://127.0.0.1:8765')
    expect(starts).toHaveLength(1)
    expect(starts[0]!.command).toContain('8765')
    expect(starts[0]!.command).toEqual(expect.arrayContaining(['--exit-when-idle', String(IDLE_SECONDS)]))
    expect(starts[0]!.command).not.toContain('--model') // all three apps (D445)
    expect(JSON.parse(readFileSync(join(state, STATE_FILE), 'utf8'))).toEqual({ port: 8765 })
    expect(starts[0]!.log).toBe(join(state, 'server.log'))
    await server.stop()
  })

  it('finds a server that runs already on 8765 and starts nothing, whoever started it', async () => {
    const { server, starts, probed } = harness({ answers: [OURS] })
    expect(await server.start()).toBe('http://127.0.0.1:8765')
    expect(starts).toEqual([])
    expect(probed).toEqual(['http://127.0.0.1:8765'])
    await server.stop()
  })

  it('goes back to 8765 from a port an earlier version picked, once nothing runs there any more', async () => {
    writeFileSync(join(state, STATE_FILE), JSON.stringify({ port: 50123 }))
    const { server, starts, probed } = harness()
    expect(await server.start()).toBe('http://127.0.0.1:8765')
    expect(probed).toEqual(['http://127.0.0.1:8765', 'http://127.0.0.1:50123'])
    expect(starts[0]!.url).toBe('http://127.0.0.1:8765')
    expect(JSON.parse(readFileSync(join(state, STATE_FILE), 'utf8'))).toEqual({ port: 8765 })
    await server.stop()
  })

  it('still uses a server that runs on the remembered port, until it stops', async () => {
    writeFileSync(join(state, STATE_FILE), JSON.stringify({ port: 50123 }))
    const { server, starts } = harness({ answers: [NONE, OURS] })
    expect(await server.start()).toBe('http://127.0.0.1:50123')
    expect(starts).toEqual([])
    await server.stop()
  })

  it('refuses a running server of another version, and says how to get rid of it', async () => {
    const { server } = harness({ answers: [{ ...OURS, version: '0.31.0' }], version: '0.32.0' })
    await expect(server.start()).rejects.toThrow(/0\.31\.0.*0\.32\.0|0\.32\.0.*0\.31\.0/s)
    await expect(server.start()).rejects.toThrow(/Activity Monitor/)
  })

  it('does not insist on a version it could not find out', async () => {
    const { server } = harness({ answers: [OURS], version: null })
    await expect(server.start()).resolves.toBe('http://127.0.0.1:8765')
    await server.stop()
  })

  it('refuses a running server that does not serve this app', async () => {
    const { server } = harness({ answers: [{ kind: 'claudia', apps: ['composes'], version: '0.32.0' }] })
    await expect(server.start()).rejects.toThrow(/does not serve computes/)
  })

  it('goes to another port when something that is not a Claudia server answers on 8765, and remembers it', async () => {
    const { server, starts, logged } = harness({ answers: [{ kind: 'other' }], port: 41233 })
    expect(await server.start()).toBe('http://127.0.0.1:41233')
    expect(starts[0]!.url).toBe('http://127.0.0.1:41233')
    expect(JSON.parse(readFileSync(join(state, STATE_FILE), 'utf8'))).toEqual({ port: 41233 })
    expect(logged.join('\n')).toMatch(/8765/)
    await server.stop()
  })

  it('keeps the port it went to then, while 8765 is still taken', async () => {
    writeFileSync(join(state, STATE_FILE), JSON.stringify({ port: 50123 }))
    const { server } = harness({ answers: [{ kind: 'other' }, NONE], port: 41233 })
    expect(await server.start()).toBe('http://127.0.0.1:50123')
    await server.stop()
  })

  it('goes to another port when 8765 is taken by something that says nothing', async () => {
    const server = new DesktopServer({
      app: 'computes',
      python: 'py',
      web: 'w',
      documents: 'd',
      state,
      probe: async () => NONE,
      makeServer: (_command, url) => ({ start: async () => url, stop: async () => {} }),
      pickPort: async () => 41233,
      portFree: async (port) => port !== 8765,
      version: async () => null,
      connect: () => new FakeSocket(),
      sleep: async () => {},
    })
    expect(await server.start()).toBe('http://127.0.0.1:41233')
    await server.stop()
  })

  it('treats an unreadable state file as no state file', async () => {
    writeFileSync(join(state, STATE_FILE), '{ not json')
    const { server } = harness()
    expect(await server.start()).toBe('http://127.0.0.1:8765')
    expect(JSON.parse(readFileSync(join(state, STATE_FILE), 'utf8'))).toEqual({ port: 8765 })
    await server.stop()
  })

  describe('two windows starting at once', () => {
    it('a start that lost to another one (it exited at start-up) uses the one that won', async () => {
      const lost = new ServerStartError('the server stopped at start-up (exit code 2)\nerror: another Claudia server uses /docs', { exited: true })
      const { server } = harness({ answers: [NONE, NONE, OURS], startFails: lost })
      await expect(server.start()).resolves.toBe('http://127.0.0.1:8765')
      await server.stop()
    })

    it('says what the server said when nobody else answers either', async () => {
      const lost = new ServerStartError('the server stopped at start-up (exit code 1)\ntraceback', { exited: true })
      const { server } = harness({ answers: [NONE], startFails: lost })
      await expect(server.start()).rejects.toBe(lost)
    })

    it('does not wait for another server when its own simply never answered', async () => {
      const slow = new ServerStartError('the server did not answer')
      const { server, probed } = harness({ answers: [NONE], startFails: slow })
      await expect(server.start()).rejects.toBe(slow)
      expect(probed).toHaveLength(1) // the one look before starting, none after
    })

    it('the state file is written once: the second window keeps the first one’s port', () => {
      const file = join(state, STATE_FILE)
      expect(writePort(file, 41233, 'exclusive')).toBe(true)
      expect(writePort(file, 50000, 'exclusive')).toBe(false)
      expect(readPort(file)).toBe(41233)
    })

    it('the state file appears whole or not at all, and nothing else is left in the folder', () => {
      const file = join(state, STATE_FILE)
      expect(writePort(file, 41233, 'exclusive')).toBe(true)
      expect(writePort(file, 50000, 'exclusive')).toBe(false)
      expect(readdirSync(state)).toEqual([STATE_FILE])
    })
  })

  describe('presence', () => {
    it('keeps a connection to /api/presence while the window is open, and lets go of it (not of the server) at the end', async () => {
      const { server, sockets, starts } = harness()
      await server.start()
      await new Promise((resolve) => setImmediate(resolve))
      expect(sockets).toHaveLength(1)
      await server.stop()
      expect(sockets[0]!.closed).toBe(true)
      expect(starts).toHaveLength(1) // closing a window does not stop the server
    })

    it('starts the server again, on the same port, when it has gone, and connects again', async () => {
      const { server, sockets, starts } = harness({ answers: [NONE, NONE, NONE] })
      await server.start()
      await new Promise((resolve) => setImmediate(resolve))
      sockets[0]!.drop() // the server stopped
      for (let i = 0; i < 20 && starts.length < 2; i++) await new Promise((resolve) => setImmediate(resolve))
      expect(starts).toHaveLength(2)
      expect(starts[1]!.url).toBe(starts[0]!.url)
      for (let i = 0; i < 20 && sockets.length < 2; i++) await new Promise((resolve) => setImmediate(resolve))
      expect(sockets).toHaveLength(2)
      await server.stop()
    })

    it('connects again without starting anything when the server is still there', async () => {
      const { server, sockets, starts } = harness({ answers: [NONE, OURS] })
      await server.start()
      await new Promise((resolve) => setImmediate(resolve))
      sockets[0]!.drop()
      for (let i = 0; i < 20 && sockets.length < 2; i++) await new Promise((resolve) => setImmediate(resolve))
      expect(sockets).toHaveLength(2)
      expect(starts).toHaveLength(1)
      await server.stop()
    })

    it('opens the presence address of the server, over ws', async () => {
      const urls: string[] = []
      const server = new DesktopServer({
        app: 'creates',
        python: 'py',
        web: 'w',
        documents: 'd',
        state,
        probe: async () => OURS,
        makeServer: (_c, url) => ({ start: async () => url, stop: async () => {} }),
        pickPort: async () => 41233,
        portFree: async () => true,
        version: async () => null,
        connect: (url) => (urls.push(url), new FakeSocket()),
        sleep: async () => {},
      })
      await server.start()
      await new Promise((resolve) => setImmediate(resolve))
      expect(urls).toEqual(['ws://127.0.0.1:8765/api/presence'])
      await server.stop()
    })
  })
})

describe('state file', () => {
  let dir: string
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-state-file-'))
  })
  afterEach(() => rmSync(dir, { recursive: true, force: true }))

  it('reads a port back, and nothing from a missing, broken or silly file', () => {
    const file = join(dir, STATE_FILE)
    expect(readPort(file)).toBeNull()
    writeFileSync(file, '{"port": 41233}')
    expect(readPort(file)).toBe(41233)
    for (const bad of ['', 'x', '[]', '{"port": "41233"}', '{"port": 0}', '{"port": 70000}', '{"port": 1.5}']) {
      writeFileSync(file, bad)
      expect(readPort(file)).toBeNull()
    }
  })

  it('overwrites on request, creating the folder', () => {
    const file = join(dir, 'a', 'b', STATE_FILE)
    expect(writePort(file, 41233, 'overwrite')).toBe(true)
    expect(writePort(file, 50000, 'overwrite')).toBe(true)
    expect(readPort(file)).toBe(50000)
    expect(existsSync(file)).toBe(true)
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
