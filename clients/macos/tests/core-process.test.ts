// The built native core (apps/<app>/ext/core.mjs) as a real process, the way Neutralino starts it: tokens on stdin,
// a WebSocket back to Neutralino, events in, broadcasts out, and the end of the process when the window is gone.
// Neutralino is played by a WebSocket server here; the server of the app by a plain http server. This is what can
// be tested without a Mac; that real Neutralino speaks the same protocol was shown on a Mac by spike 5 (2026-11-10).
import { spawn, type ChildProcess } from 'node:child_process'
import { copyFileSync, existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { createServer, type Server } from 'node:http'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { WebSocket, WebSocketServer } from 'ws'
// @ts-expect-error the build tool is plain JavaScript
import { buildApp } from '../tools/build-shell.mjs'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const CORE = join(root, 'apps', 'creates', 'ext', 'core.mjs')

type Broadcast = { event: string; data: any }

/** Neutralino's side: accepts the extension's connection, records what it broadcasts, can send events to it. */
class FakeNeutralino {
  readonly server: WebSocketServer
  socket: WebSocket | null = null
  query = ''
  broadcasts: Broadcast[] = []
  tokens: string[] = []
  private waiting: Array<() => void> = []
  constructor() {
    this.server = new WebSocketServer({ host: '127.0.0.1', port: 0 })
    this.server.on('connection', (socket, request) => {
      this.socket = socket
      this.query = request.url ?? ''
      socket.on('message', (raw) => {
        const message = JSON.parse(String(raw))
        if (message.method === 'app.broadcast') {
          this.tokens.push(message.accessToken)
          this.broadcasts.push(message.data)
          this.waiting.forEach((resolve) => resolve())
        }
      })
    })
  }
  get port(): number {
    return (this.server.address() as { port: number }).port
  }
  /** Resolves when the server listens. */
  ready(): Promise<this> {
    return new Promise((resolve) => (this.server.address() ? resolve(this) : this.server.once('listening', () => resolve(this))))
  }
  dispatch(event: string, data: unknown): void {
    this.socket!.send(JSON.stringify({ event, data }))
  }
  async until(condition: () => boolean, ms = 5000): Promise<void> {
    const end = Date.now() + ms
    while (!condition()) {
      if (Date.now() > end) throw new Error(`timed out; broadcasts so far: ${JSON.stringify(this.broadcasts)}`)
      await new Promise<void>((resolve) => {
        this.waiting.push(resolve)
        setTimeout(resolve, 50)
      })
    }
  }
  async connected(): Promise<void> {
    const end = Date.now() + 5000
    while (this.socket === null) {
      if (Date.now() > end) throw new Error('the core did not connect')
      await new Promise((resolve) => setTimeout(resolve, 20))
    }
  }
  close(): Promise<void> {
    this.socket?.close()
    return new Promise((resolve) => this.server.close(() => resolve()))
  }
}

function claudia(app: string): Promise<{ server: Server; port: number }> {
  const server = createServer((request, response) => {
    response.writeHead(200, { 'content-type': 'application/json' })
    response.end(request.url === '/api/health' ? '{"ok":true}' : JSON.stringify({ app }))
  })
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve({ server, port: (server.address() as { port: number }).port })))
}

describe('the core process', () => {
  let home: string
  let neutralino: FakeNeutralino
  let child: ChildProcess | null
  let servers: Server[]
  let exit: Promise<number | null>

  beforeAll(async () => {
    await buildApp('creates', { quiet: true })
  }, 60000)

  beforeEach(async () => {
    home = mkdtempSync(join(tmpdir(), 'claudia-core-home-'))
    neutralino = await new FakeNeutralino().ready()
    servers = []
    child = null
  })

  afterEach(async () => {
    child?.kill('SIGKILL')
    await neutralino.close()
    for (const server of servers) await new Promise<void>((resolve) => (server.closeAllConnections(), server.close(() => resolve())))
    rmSync(home, { recursive: true, force: true })
  })

  function start(env: Record<string, string>): void {
    child = spawn(process.execPath, [CORE], {
      env: { PATH: process.env.PATH ?? '', HOME: home, CLAUDIA_SHELL_APP: 'creates', ...env },
      stdio: ['pipe', 'ignore', 'pipe'],
    })
    exit = new Promise((resolve) => child!.once('exit', (code) => resolve(code)))
    // Neutralino sends the auth in more than one piece sometimes; the core must wait for all of it.
    const auth = JSON.stringify({ nlPort: neutralino.port, nlToken: 'ext-token', nlConnectToken: 'connect-token', nlExtensionId: 'de.claudiaoffice.core' })
    child.stdin!.write(auth.slice(0, 20))
    setTimeout(() => child?.stdin?.write(auth.slice(20)), 50)
  }

  it('connects back to Neutralino with the extension id and the connect token', async () => {
    start({})
    await neutralino.connected()
    expect(neutralino.query).toBe('/?extensionId=de.claudiaoffice.core&connectToken=connect-token')
  })

  it('shows a given server after the checks, remembers it, and lists it', async () => {
    const server = await claudia('creates')
    servers.push(server.server)
    const origin = `http://127.0.0.1:${server.port}`
    start({ CLAUDIA_SHELL_SERVER: origin })
    await neutralino.connected()
    neutralino.dispatch('claudia.core', { kind: 'start' })
    await neutralino.until(() => neutralino.broadcasts.some((b) => b.data.kind === 'show'))
    expect(neutralino.broadcasts.every((b) => b.event === 'claudiaCore')).toBe(true)
    expect(neutralino.tokens.every((t) => t === 'ext-token')).toBe(true)
    expect(neutralino.broadcasts[0]!.data).toMatchObject({ kind: 'status', title: "Connecting to 127.0.0.1…" })
    expect(neutralino.broadcasts.at(-1)!.data).toEqual({ kind: 'show', origin })

    neutralino.dispatch('claudia.core', { kind: 'want_servers' })
    await neutralino.until(() => neutralino.broadcasts.some((b) => b.data.kind === 'servers'))
    const list = neutralino.broadcasts.find((b) => b.data.kind === 'servers')!.data.servers
    expect(list.map((s: { origin: string }) => s.origin)).toEqual([origin])

    const saved = JSON.parse(readFileSync(join(home, 'Library', 'Application Support', 'Claudia', 'shell.json'), 'utf8'))
    expect(saved.servers.creates.map((s: { origin: string }) => s.origin)).toEqual([origin])
  })

  it("refuses a server of another app, and tells the page why (nothing is shown)", async () => {
    const server = await claudia('composes')
    servers.push(server.server)
    start({ CLAUDIA_SHELL_SERVER: `http://127.0.0.1:${server.port}` })
    await neutralino.connected()
    neutralino.dispatch('claudia.core', { kind: 'start' })
    await neutralino.until(() => neutralino.broadcasts.some((b) => b.data.kind === 'connect_failed'))
    const failure = neutralino.broadcasts.find((b) => b.data.kind === 'connect_failed')!.data
    expect(failure.code).toBe('wrong_app')
    expect(neutralino.broadcasts.some((b) => b.data.kind === 'show')).toBe(false)
  })

  it('connects to another server when the page asks', async () => {
    const own = await claudia('creates')
    const other = await claudia('creates')
    servers.push(own.server, other.server)
    start({ CLAUDIA_SHELL_SERVER: `http://127.0.0.1:${own.port}` })
    await neutralino.connected()
    neutralino.dispatch('claudia.core', { kind: 'start' })
    await neutralino.until(() => neutralino.broadcasts.some((b) => b.data.kind === 'show'))
    neutralino.dispatch('claudia.core', { kind: 'connect', address: `http://127.0.0.1:${other.port}` })
    await neutralino.until(() => neutralino.broadcasts.filter((b) => b.data.kind === 'show').length === 2)
    expect(neutralino.broadcasts.at(-1)!.data).toEqual({ kind: 'show', origin: `http://127.0.0.1:${other.port}` })
  })

  it('ignores what is not a request, and goes on', async () => {
    const server = await claudia('creates')
    servers.push(server.server)
    start({ CLAUDIA_SHELL_SERVER: `http://127.0.0.1:${server.port}` })
    await neutralino.connected()
    neutralino.dispatch('claudia.core', { kind: 'rm-rf' })
    neutralino.dispatch('something.else', { kind: 'start' })
    neutralino.dispatch('claudia.core', { kind: 'start' })
    await neutralino.until(() => neutralino.broadcasts.some((b) => b.data.kind === 'show'))
  })

  it('ends with the window: when Neutralino closes the connection the process exits, cleanly', async () => {
    start({})
    await neutralino.connected()
    neutralino.socket!.close()
    expect(await exit).toBe(0)
  })

  it('ends at once when Neutralino cannot be reached at all', async () => {
    const dead = await new FakeNeutralino().ready()
    const port = dead.port
    await dead.close()
    child = spawn(process.execPath, [CORE], { env: { PATH: process.env.PATH ?? '', HOME: home, CLAUDIA_SHELL_APP: 'creates' }, stdio: ['pipe', 'ignore', 'ignore'] })
    exit = new Promise((resolve) => child!.once('exit', (code) => resolve(code)))
    child.stdin!.write(JSON.stringify({ nlPort: port, nlToken: 't', nlConnectToken: 'c', nlExtensionId: 'de.claudiaoffice.core' }))
    expect(await exit).toBe(0)
  })

  describe('without being told anything (what a window that was not started by the launcher, or a Neutralino that passes on no environment, gives it)', () => {
    const suiteDir = () => join(home, 'Library', 'Application Support', 'Claudia')

    function startBare(core: string): void {
      child = spawn(process.execPath, [core], { env: { PATH: process.env.PATH ?? '', HOME: home }, stdio: ['pipe', 'ignore', 'ignore'] })
      exit = new Promise((resolve) => child!.once('exit', (code) => resolve(code)))
      child.stdin!.write(JSON.stringify({ nlPort: neutralino.port, nlToken: 't', nlConnectToken: 'c', nlExtensionId: 'de.claudiaoffice.core' }))
    }

    it('knows its app from the folder it lies in, answers, and logs what it does', async () => {
      startBare(CORE)
      await neutralino.connected()
      neutralino.dispatch('claudia.core', { kind: 'start' })
      await neutralino.until(() => neutralino.broadcasts.length > 0)
      expect(neutralino.broadcasts[0]!.data.kind).toBe('status') // "Starting Claudia Creates…" -- it is there and answers
      const log = readFileSync(join(suiteDir(), 'creates', 'state', 'shell.log'), 'utf8')
      expect(log).toContain('app creates')
      expect(log).toContain('connected to Neutralino')
      expect(log).toContain('<- page: start')
      expect(log).toContain('-> page: status')
    })

    it('takes app and server from its command line, and logs how stdin looks', async () => {
      const server = await claudia('creates')
      servers.push(server.server)
      const origin = `http://127.0.0.1:${server.port}`
      child = spawn(process.execPath, [CORE, '--app=creates', `--server=${origin}`], { env: { PATH: process.env.PATH ?? '', HOME: home }, stdio: ['pipe', 'ignore', 'ignore'] })
      child.stdin!.write(JSON.stringify({ nlPort: neutralino.port, nlToken: 't', nlConnectToken: 'c', nlExtensionId: 'de.claudiaoffice.core' }))
      await neutralino.connected()
      neutralino.dispatch('claudia.core', { kind: 'start' })
      await neutralino.until(() => neutralino.broadcasts.some((b) => b.data.kind === 'show'))
      expect(neutralino.broadcasts.at(-1)!.data).toEqual({ kind: 'show', origin })
      const log = readFileSync(join(suiteDir(), 'creates', 'state', 'shell.log'), 'utf8')
      expect(log).toContain(`server ${origin}`)
      const first = readFileSync(join(suiteDir(), 'shell.log'), 'utf8') // what the core wrote before it knew its app
      expect(first).toMatch(/stdin is a (pipe|socket)/)
      expect(first).toContain('--app=creates')
    })

    it('connects when Neutralino sends the port as a string and adds fields of its own', async () => {
      child = spawn(process.execPath, [CORE, '--app=creates'], { env: { PATH: process.env.PATH ?? '', HOME: home }, stdio: ['pipe', 'ignore', 'ignore'] })
      child.stdin!.write(JSON.stringify({ nlPort: String(neutralino.port), nlToken: 't', nlConnectToken: 'c', nlExtensionId: 'de.claudiaoffice.core', nlExtra: 1 }))
      await neutralino.connected()
      expect(neutralino.query).toBe('/?extensionId=de.claudiaoffice.core&connectToken=c')
    })

    it('says what it got on stdin, as keys and types, when that is not what it expected', async () => {
      child = spawn(process.execPath, [CORE, '--app=creates'], { env: { PATH: process.env.PATH ?? '', HOME: home }, stdio: ['pipe', 'ignore', 'ignore'] })
      child.stdin!.end(JSON.stringify({ port: 4711, nlToken: 'SECRET-TOKEN' }))
      await new Promise((resolve) => setTimeout(resolve, 600))
      const log = readFileSync(join(suiteDir(), 'creates', 'state', 'shell.log'), 'utf8')
      expect(log).toContain('port: number')
      expect(log).toContain('nlToken: string')
      expect(log).not.toContain('SECRET-TOKEN')
      expect(log).toContain('stdin ended before the tokens arrived')
    })

    it('logs when stdin ends without the tokens (the way the failed wrapper script showed it)', async () => {
      child = spawn(process.execPath, [CORE, '--app=creates'], { env: { PATH: process.env.PATH ?? '', HOME: home }, stdio: ['pipe', 'ignore', 'ignore'] })
      child.stdin!.end()
      await new Promise((resolve) => setTimeout(resolve, 600))
      expect(readFileSync(join(suiteDir(), 'creates', 'state', 'shell.log'), 'utf8')).toContain('stdin ended before the tokens arrived')
    })

    it('says in the log why it cannot run, instead of dying without a word', async () => {
      const elsewhere = join(home, 'core.mjs') // no apps/<app>/ folder, no environment: it cannot know its app
      copyFileSync(CORE, elsewhere)
      startBare(elsewhere)
      expect(await exit).toBe(1)
      const log = readFileSync(join(suiteDir(), 'shell.log'), 'utf8')
      expect(log).toContain('started: node')
      expect(log).toContain("there is no macOS client for ''")
      expect(existsSync(join(suiteDir(), 'creates'))).toBe(false)
    })
  })
})
