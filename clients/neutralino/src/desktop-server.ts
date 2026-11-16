// The one local server that the three desktop apps share (D445). The twin of clients/linux/.../desktop_server.py; only
// the words that name the operating system's tools differ between macOS and Windows (src/platform/host.ts).
//
//  - **One server for the suite.** It serves all three apps (no `--model`), keeps one folder of documents and one of
//    state, and stops by itself (`--exit-when-idle`, D434) ten minutes after nothing was connected. The first window
//    that needs it starts it; the others find it.
//  - **Found by its port: 8765, the port of every Claudia server** (D504; `./start.sh` and a cloud server use it too), so
//    the address -- and what the page keeps for that address -- stays the same. Only when something that is not a
//    Claudia server holds 8765 does the suite go to another port, remembered in `desktop-server.json` in the state
//    folder. A running server is recognised by `/api/health` (its apps; its version, for a request from this computer):
//    nothing else is asked of it, so a Claudia server of this version on 8765 is this computer's server, whoever
//    started it.
//  - **Two windows starting at once** both start a server on the same port; the one that loses (the port, or the
//    server's own lock on its folder, D435) exits at start-up, and its window then uses the one that won.
//  - **A window never ends the server.** Closing it only lets go of the connection it keeps (`/api/presence`) so the
//    server is never taken for idle while a window is open -- an open front page holds nothing else. A window that finds
//    the server gone (it stopped, or somebody ended it) starts it again on the same port, where the page reconnects.
//
// What is an operating system's own: little. The server is started `detached`, so neither the window nor the launcher's
// terminal takes it down; it ends by itself, or `server.ts` stops one that never came up (with signals to its process
// group on a Mac, with taskkill for its process tree on Windows).

import { execFile } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { linkSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:net'
import { dirname, join } from 'node:path'
import { buildServerCommand, freePort, LocalServer, LOOPBACK, ServerStartError } from './server.js'
import { hostPlatform } from './platform/host.js'

/** `--exit-when-idle`: ten minutes (D445). The clock starts only when the last page has closed. */
export const IDLE_SECONDS = 600
/** In the server's state folder: `{"port": N}`, the port the server went to when 8765 was taken. */
export const STATE_FILE = 'desktop-server.json'
/** The port of every Claudia server unless told otherwise (D504): ./start.sh, a cloud server, the desktop's own. */
export const SERVER_PORT = 8765

/** What is listening where the server should be. */
export type Health =
  | { kind: 'none' }
  /** Something answers, but it is not a server of this suite (or one from before D444, which says no apps). */
  | { kind: 'other' }
  | { kind: 'claudia'; apps: string[]; version: string | null }

/** `/api/health` at `url`. A refused connection is `none`; every other answer that is not ours is `other`. */
export async function probeHealth(url: string, timeoutMs = 1000): Promise<Health> {
  let response: Response
  try {
    response = await fetch(`${url}/api/health`, { signal: AbortSignal.timeout(timeoutMs) })
  } catch {
    return { kind: 'none' }
  }
  try {
    if (!response.ok) return { kind: 'other' }
    const body = (await response.json()) as { ok?: unknown; apps?: unknown; version?: unknown }
    if (body.ok !== true || !Array.isArray(body.apps) || !body.apps.every((app) => typeof app === 'string')) {
      return { kind: 'other' }
    }
    return { kind: 'claudia', apps: body.apps as string[], version: typeof body.version === 'string' ? body.version : null }
  } catch {
    return { kind: 'other' }
  }
}

/** The remembered port, or `null` for a missing, broken or nonsensical file. */
export function readPort(file: string): number | null {
  try {
    const port = (JSON.parse(readFileSync(file, 'utf8')) as { port?: unknown }).port
    return typeof port === 'number' && Number.isInteger(port) && port >= 1 && port <= 65535 ? port : null
  } catch {
    return null
  }
}

/** Remember `port`. `exclusive` writes only when there is no file yet (`false` when somebody was first); `overwrite`
 * always writes. The folder is made. */
export function writePort(file: string, port: number, mode: 'exclusive' | 'overwrite'): boolean {
  mkdirSync(dirname(file), { recursive: true })
  const text = JSON.stringify({ port }) + '\n'
  if (mode === 'overwrite') {
    writeFileSync(file, text)
    return true
  }
  // Written whole under another name and then linked into place: a second window that loses never reads a file that is
  // there but not written yet (two first starts at once are exactly when this is asked). Where the folder cannot hold
  // links, the exclusive create is the fallback.
  const temporary = join(dirname(file), `.desktop-server-${process.pid}-${randomBytes(4).toString('hex')}`)
  try {
    writeFileSync(temporary, text)
    try {
      linkSync(temporary, file)
      return true
    } catch (problem) {
      const code = (problem as NodeJS.ErrnoException).code
      if (code === 'EEXIST') return false
      if (code !== 'EPERM' && code !== 'ENOTSUP' && code !== 'ENOSYS') throw problem
    }
    try {
      writeFileSync(file, text, { flag: 'wx' })
      return true
    } catch (problem) {
      if ((problem as NodeJS.ErrnoException).code === 'EEXIST') return false
      throw problem
    }
  } finally {
    try {
      unlinkSync(temporary)
    } catch {
      // gone already
    }
  }
}

/** Can a server listen on `port` of this computer's loopback address right now? */
export function isPortFree(port: number, host: string = LOOPBACK): Promise<boolean> {
  return new Promise((resolve) => {
    const probe = createServer()
    probe.once('error', () => resolve(false))
    probe.listen(port, host, () => probe.close(() => resolve(true)))
  })
}

/** The version of the server this app would start (`claudia_server --version`), or `null` if that cannot be found out. */
export function serverVersion(python: string, timeoutMs = 30_000): Promise<string | null> {
  return new Promise((resolve) => {
    try {
      execFile(python, ['-m', 'claudia_server', '--version'], { timeout: timeoutMs, windowsHide: true }, (problem, stdout) => {
        const found = problem ? null : /claudia-server\s+(\S+)/.exec(String(stdout))
        resolve(found ? (found[1] as string) : null)
      })
    } catch {
      resolve(null)
    }
  })
}

/** What the presence connection needs of a WebSocket (Node's global one has it). */
export interface PresenceSocket {
  addEventListener(type: 'close' | 'error', listener: () => void): void
  close(): void
}

/** One server process, as `server.ts`'s `LocalServer` offers it. */
export interface ServerProcess {
  start(): Promise<string>
  stop(): Promise<void>
}

export interface DesktopServerOptions {
  /** The app of this window: the server must serve it. */
  app: string
  python: string
  web: string
  documents: string
  /** The server's state folder: `desktop-server.json` and `server.log` are in it. */
  state: string
  idleSeconds?: number
  log?: (message: string) => void
  /** How long a start that lost to another one looks for the winner. */
  raceWaitMs?: number
  /** The port to use when it is free (`SERVER_PORT`). */
  port?: number
  /** How a person stops a server that will not go, in this operating system's words (src/platform/host.ts). */
  endTheServer?: string
  // What the tests replace:
  probe?: (url: string) => Promise<Health>
  makeServer?: (command: string[], url: string, log: string) => ServerProcess
  pickPort?: () => Promise<number>
  portFree?: (port: number) => Promise<boolean>
  version?: () => Promise<string | null>
  connect?: (url: string) => PresenceSocket
  sleep?: (ms: number) => Promise<void>
}

const PRESENCE_PAUSE_MS = 1000
const PRESENCE_PAUSE_MAX_MS = 10_000
const RACE_POLL_MS = 300

export class DesktopServer {
  private readonly options: DesktopServerOptions
  private readonly stateFile: string
  private origin: string | null = null
  private letGo = false
  private socket: PresenceSocket | null = null

  constructor(options: DesktopServerOptions) {
    this.options = options
    this.stateFile = join(options.state, STATE_FILE)
  }

  private get endTheServer(): string {
    return this.options.endTheServer ?? hostPlatform().endTheServer
  }

  /** The file the server writes to (shared by every start). */
  get logPath(): string {
    return join(this.options.state, 'server.log')
  }

  /** Where the server answers, once `start()` has returned. */
  get url(): string | null {
    return this.origin
  }

  /** Find the running server or start it; then keep the presence connection. Returns the server's address. */
  async start(): Promise<string> {
    const url = await this.ensure()
    this.origin = url
    if (!this.letGo) void this.keepPresence()
    return url
  }

  /** Let go of the server: this window is gone. The server itself is not stopped; it stops when nothing is connected. */
  async stop(): Promise<void> {
    this.letGo = true
    this.socket?.close()
    this.socket = null
  }

  // ------------------------------------------------------------------------------------------------ finding it

  private log(message: string): void {
    this.options.log?.(message)
  }

  private async ensure(): Promise<string> {
    const preferred = this.options.port ?? SERVER_PORT
    const remembered = readPort(this.stateFile)
    // A server that runs already: on the port of every Claudia server, or where an earlier start had to go instead.
    let preferredTaken = false
    for (const port of remembered !== null && remembered !== preferred ? [preferred, remembered] : [preferred]) {
      const url = `http://${LOOPBACK}:${port}`
      const found = await this.probe(url)
      if (found.kind === 'claudia') {
        await this.checkIsOurs(found, port)
        this.remember(port)
        return url
      }
      if (port === preferred) preferredTaken = found.kind === 'other' || !(await this.portFree(port))
    }
    // None runs: start one, on the usual port unless something that is not a Claudia server holds it.
    let port = preferred
    if (preferredTaken) {
      port = remembered !== null && remembered !== preferred && (await this.portFree(remembered)) ? remembered : await this.pickPort()
      this.log(`port ${preferred} is used by something that is not a Claudia server; the local server goes to port ${port}`)
    }
    this.remember(port)
    return this.startServer(`http://${LOOPBACK}:${port}`, port)
  }

  /** Write down where the server is, if that is not what the file says already. */
  private remember(port: number): void {
    if (readPort(this.stateFile) === port) return
    try {
      writePort(this.stateFile, port, 'overwrite')
    } catch (problem) {
      this.log(`${this.stateFile} could not be written: ${(problem as Error).message}`)
    }
  }

  private async checkIsOurs(found: Extract<Health, { kind: 'claudia' }>, port: number): Promise<void> {
    const { app } = this.options
    if (!found.apps.includes(app)) {
      throw new ServerStartError(
        `The Claudia server on this computer (port ${port}) does not serve ${app}; it serves ${found.apps.join(', ') || 'no app'}.\n` +
          `It stops by itself ten minutes after its last window has closed. ${this.endTheServer} Then start again.`,
      )
    }
    if (found.version === null) return
    const own = await (this.options.version ?? (() => serverVersion(this.options.python)))()
    if (own !== null && own !== found.version) {
      throw new ServerStartError(
        `A Claudia server of another version (${found.version}, this app belongs to ${own}) is running on this computer (port ${port}).\n` +
          `It stops by itself ten minutes after its last window has closed. ${this.endTheServer} Then start again.`,
      )
    }
  }

  private async startServer(url: string, port: number): Promise<string> {
    const { python, web, documents, state } = this.options
    const command = buildServerCommand(python, { port, documents, web, state, idleSeconds: this.options.idleSeconds ?? IDLE_SECONDS })
    const server = (this.options.makeServer ?? defaultMakeServer)(command, url, this.logPath)
    try {
      return await server.start()
    } catch (problem) {
      // Another window may have started it a moment before: its server holds the folder's lock (D435), and ours
      // exited. Then that one is the server.
      if (problem instanceof ServerStartError && problem.exited && (await this.winnerAnswers(url))) {
        this.log(`another start was first; using its server at ${url}`)
        return url
      }
      throw problem
    }
  }

  private async winnerAnswers(url: string): Promise<boolean> {
    const sleep = this.options.sleep ?? defaultSleep
    const until = Date.now() + (this.options.raceWaitMs ?? 30_000)
    for (;;) {
      const found = await this.probe(url)
      if (found.kind === 'claudia' && found.apps.includes(this.options.app)) return true
      if (Date.now() >= until) return false
      await sleep(RACE_POLL_MS)
    }
  }

  // ----------------------------------------------------------------------------------------------- presence

  /** Keep a connection to the server while this window is open (D445). When it ends, the server has stopped (or been
   * stopped): start it again on the same port and connect again. */
  private async keepPresence(): Promise<void> {
    const sleep = this.options.sleep ?? defaultSleep
    let pause = PRESENCE_PAUSE_MS
    while (!this.letGo) {
      try {
        await this.hold()
        pause = PRESENCE_PAUSE_MS
        if (this.letGo) return
        this.origin = await this.ensure() // gone? then up again; there, nothing happens
      } catch (problem) {
        this.log(`the local server is not there and could not be started again: ${(problem as Error).message}`)
        pause = Math.min(pause * 2, PRESENCE_PAUSE_MAX_MS)
      }
      if (!this.letGo) await sleep(pause)
    }
  }

  /** Resolves when the presence connection ends, however it ends. */
  private hold(): Promise<void> {
    return new Promise((resolve) => {
      const origin = this.origin
      if (origin === null || this.letGo) return resolve()
      const socket = (this.options.connect ?? defaultConnect)(origin.replace(/^http/, 'ws') + '/api/presence')
      this.socket = socket
      socket.addEventListener('close', () => resolve())
      socket.addEventListener('error', () => resolve())
    })
  }

  private probe(url: string): Promise<Health> {
    return (this.options.probe ?? ((target) => probeHealth(target)))(url)
  }

  private pickPort(): Promise<number> {
    return (this.options.pickPort ?? (() => freePort()))()
  }

  private portFree(port: number): Promise<boolean> {
    return (this.options.portFree ?? ((p) => isPortFree(p)))(port)
  }
}

function defaultMakeServer(command: string[], url: string, log: string): ServerProcess {
  return new LocalServer(command, { url, log })
}

function defaultConnect(url: string): PresenceSocket {
  return new WebSocket(url) as unknown as PresenceSocket
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
