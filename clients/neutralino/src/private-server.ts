// A person's private server, which her three desktop apps share ("Private on this computer"; E8.5, D1620, D1621; before
// E8.5: the desktop's one server, D445). The twin of clients/linux/.../private_server.py; only the words that name the
// operating system's tools differ between macOS and Windows (src/platform/host.ts).
//
//  - **One server for her three apps.** It serves all three (no `--model`), keeps her folder of documents and her
//    folder of state, and stops by itself (`--exit-when-idle`, D434) ten minutes after nothing was connected. Her first
//    window that needs it starts it; her others find it.
//  - **On a port of her own** (private-port.ts): from her account, the same at every start, so the address -- and what
//    the page keeps for it -- stays hers; never 8765, the port of every shared server (D1621).
//  - **Hers, proven.** Her apps start it with a key from her state folder (owner-key.ts) and use a server they find on
//    her port only when it answers a fresh challenge with that key: another person's server, a shared one (the service,
//    8765 and all), or a program on her port is never taken for hers (CODE-99), and its version is no business of hers
//    (CODE-100).
//  - **Her port held by something else** (a program, or a Claudia server that is not hers): her server goes to the next
//    free port of her range (`walkFrom`, the same order for every window of hers) for as long as that lasts, written
//    down as `instead` in `desktop-server.json` so that her other apps find it. A start uses her server where it is,
//    and starts one on her own port again (and forgets `instead`) once her server is gone and her port is free.
//  - **Two windows starting at once** both start a server on the same port; the one that loses (the port, or the
//    server's own lock on its folder, D435) exits at start-up, and its window then uses the one that won, when it is hers.
//  - **A window never ends the server.** Closing it only lets go of the connection it keeps (`/api/presence`) so the
//    server is never taken for idle while a window is open -- an open front page holds nothing else. A window that finds
//    the server gone (it stopped, or somebody ended it) starts it again, where the page reconnects.
//
// What is an operating system's own: little. The server is started `detached`, so neither the window nor the launcher's
// terminal takes it down; it ends by itself, or `server.ts` stops one that never came up (with signals to its process
// group on a Mac, with taskkill for its process tree on Windows).

import { execFile } from 'node:child_process'
import { mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:net'
import { dirname, join } from 'node:path'
import { buildServerCommand, LocalServer, LOOPBACK, ServerStartError, serverProgramCommand, type ServerProgram } from './server.js'
import { SETUP_CODE } from './core-protocol.js'
import { hostPlatform } from './platform/host.js'
import { isOwnedBy, ownerKey, type OwnerKey } from './owner-key.js'
import { PRIVATE_PORTS, privatePort, walkFrom, type Account } from './private-port.js'

/** `--exit-when-idle`: ten minutes (D445). The clock starts only when the last page has closed. */
export const IDLE_SECONDS = 600
/** In the server's state folder: `{"instead": N}`, the port her server went to while her own port is held by something
 * else; no file while it is not. (A file from before E8.5 says `{"port": N}` and is not read.) */
export const STATE_FILE = 'desktop-server.json'

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

/** Where the server writes its setup code while it has no administrator (D1371), readable by this user only. */
const SETUP_CODE_FILE = join('admin', 'setup-code')

/** The setup code the server with this state folder wrote, or `null` (an administrator exists, or the file is not a
 * code). Read anew at every call: the shared server may have been restarted by another window (D1373). */
export function readSetupCode(state: string): string | null {
  const access = setupCodeAccess(state)
  return access.kind === 'code' ? access.code : null
}

/** What this account may learn of the setup code in a server's state folder: the code, that there is none (the server
 * has an administrator, or the file holds no code), or that it may not read it (D1624). The file itself is read: on
 * Windows, `access()` does not look at a file's ACL, so it would say yes to everyone. */
export type SetupCodeAccess = { kind: 'code'; code: string } | { kind: 'none' } | { kind: 'may not' }

export function setupCodeAccess(state: string): SetupCodeAccess {
  let text: string
  try {
    text = readFileSync(join(state, SETUP_CODE_FILE), 'utf8')
  } catch (problem) {
    const code = (problem as NodeJS.ErrnoException).code
    return code === 'EACCES' || code === 'EPERM' ? { kind: 'may not' } : { kind: 'none' }
  }
  const found = text.trim()
  return SETUP_CODE.test(found) ? { kind: 'code', code: found } : { kind: 'none' }
}

/** The port her server went to instead of her own, or `null` for a missing, broken, nonsensical or older file. */
export function readInstead(file: string): number | null {
  try {
    const port = (JSON.parse(readFileSync(file, 'utf8')) as { instead?: unknown }).instead
    return typeof port === 'number' && Number.isInteger(port) && port >= 1 && port <= 65535 ? port : null
  } catch {
    return null
  }
}

/** Write down where her server went instead (written whole under another name first, so that her other windows never
 * read half a file), or, with `null`, that it is on her own port again. The folder is made. */
export function writeInstead(file: string, port: number | null): void {
  if (port === null) {
    rmSync(file, { force: true })
    return
  }
  mkdirSync(dirname(file), { recursive: true })
  const temporary = `${file}.${process.pid}`
  writeFileSync(temporary, JSON.stringify({ instead: port }) + '\n')
  renameSync(temporary, file)
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
export function serverVersion(program: ServerProgram, timeoutMs = 30_000): Promise<string | null> {
  const [file, ...args] = serverProgramCommand(program) as [string, ...string[]]
  return new Promise((resolve) => {
    try {
      execFile(file, [...args, '--version'], { timeout: timeoutMs, windowsHide: true }, (problem, stdout) => {
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

export interface PrivateServerOptions {
  /** The app of this window: the server must serve it. */
  app: string
  /** What starts the server: an interpreter (it runs `-m claudia_server`) or the installer's `claudia-server.exe`. */
  program: ServerProgram
  web: string
  documents: string
  /** The server's state folder: `desktop-server.json`, `owner.key` and `server.log` are in it. */
  state: string
  /** Who she is on this computer: her port follows from it (private-port.ts). */
  account: Account
  idleSeconds?: number
  log?: (message: string) => void
  /** How long a start that lost to another one looks for the winner. */
  raceWaitMs?: number
  /** Her port, when it is not the one of her account (`CLAUDIA_SERVER_PORT`). */
  port?: number
  /** How a person stops a server that will not go, in this operating system's words (src/platform/host.ts). */
  endTheServer?: string
  // What the tests replace:
  probe?: (url: string) => Promise<Health>
  /** Does the Claudia server at `url` prove to be hers? (owner-key.ts's `isOwnedBy` with her key) */
  isMine?: (url: string) => Promise<boolean>
  makeServer?: (command: string[], url: string, log: string) => ServerProcess
  portFree?: (port: number) => Promise<boolean>
  version?: () => Promise<string | null>
  connect?: (url: string) => PresenceSocket
  sleep?: (ms: number) => Promise<void>
}

const PRESENCE_PAUSE_MS = 1000
const PRESENCE_PAUSE_MAX_MS = 10_000
const RACE_POLL_MS = 300

export class PrivateServer {
  private readonly options: PrivateServerOptions
  private readonly stateFile: string
  private key: OwnerKey | null = null
  private origin: string | null = null
  private letGo = false
  private socket: PresenceSocket | null = null

  constructor(options: PrivateServerOptions) {
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

  /** The server's setup code while it has no administrator (D1373). */
  setupCode(): string | null {
    return readSetupCode(this.options.state)
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

  /** Her port, by her account unless told otherwise. */
  private get usual(): number {
    return this.options.port ?? privatePort(this.options.account)
  }

  /** Find her server or start it. `stay`: the port the page is on, tried first when her server has gone (`keepPresence`),
   * so that it comes back where the page reconnects. */
  private async ensure(stay?: number): Promise<string> {
    if (stay !== undefined) {
      const there = await this.find(stay)
      if (there === 'hers') return urlOf(stay)
      if (there === 'free') return this.startServer(stay)
    }
    const usual = this.usual
    const atUsual = await this.find(usual)
    if (atUsual === 'hers') {
      this.goneBack()
      return urlOf(usual)
    }
    // Her server may still run where it went while her port was held, and it keeps her documents (D435): use it there.
    const instead = readInstead(this.stateFile)
    if (instead !== null && instead !== usual && (await this.find(instead)) === 'hers') return urlOf(instead)
    if (atUsual === 'free') {
      this.goneBack()
      return this.startServer(usual)
    }
    this.log(`port ${usual}, hers, is held by ${atUsual === 'held' ? 'something that is not a Claudia server' : 'a Claudia server that is not hers'}; her server uses another port of her range while that lasts`)
    for (const port of walkFrom(usual)) {
      const there = await this.find(port)
      if (there === 'hers' || there === 'free') {
        this.write(port)
        return there === 'hers' ? urlOf(port) : this.startServer(port)
      }
    }
    throw new ServerStartError(`No port from ${PRIVATE_PORTS.first} to ${PRIVATE_PORTS.last} is free for your Claudia server on this computer.`)
  }

  /** What is on `port`: her server (checked to serve this app at this version), nothing (`free`), a Claudia server that
   * is not hers (`not hers`), or something else that holds it (`held`). */
  private async find(port: number): Promise<'hers' | 'free' | 'not hers' | 'held'> {
    const found = await this.probe(urlOf(port))
    if (found.kind === 'claudia') {
      if (!(await this.isMine(urlOf(port)))) return 'not hers'
      await this.checkIsOurs(found, port)
      return 'hers'
    }
    return found.kind === 'none' && (await this.portFree(port)) ? 'free' : 'held'
  }

  /** Her server is on her own port: `instead` is no longer needed. */
  private goneBack(): void {
    if (readInstead(this.stateFile) !== null) this.write(null)
  }

  private write(instead: number | null): void {
    try {
      writeInstead(this.stateFile, instead)
    } catch (problem) {
      this.log(`${this.stateFile} could not be written: ${(problem as Error).message}`)
    }
  }

  private async checkIsOurs(found: Extract<Health, { kind: 'claudia' }>, port: number): Promise<void> {
    const { app } = this.options
    if (!found.apps.includes(app)) {
      throw new ServerStartError(
        `Your Claudia server on this computer (port ${port}) does not serve ${app}; it serves ${found.apps.join(', ') || 'no app'}.\n` +
          `It stops by itself ten minutes after its last window has closed. ${this.endTheServer} Then start again.`,
      )
    }
    if (found.version === null) return
    const own = await (this.options.version ?? (() => serverVersion(this.options.program)))()
    if (own !== null && own !== found.version) {
      throw new ServerStartError(
        `Your Claudia server of another version (${found.version}, this app belongs to ${own}) is still running on this computer (port ${port}).\n` +
          `It stops by itself ten minutes after its last window has closed. ${this.endTheServer} Then start again.`,
      )
    }
  }

  private async startServer(port: number): Promise<string> {
    const { program, web, documents, state } = this.options
    const url = urlOf(port)
    const idleSeconds = this.options.idleSeconds ?? IDLE_SECONDS
    const command = buildServerCommand(program, { port, documents, web, state, idleSeconds, ownerKeyFile: this.ownerKey().file })
    const server = (this.options.makeServer ?? defaultMakeServer)(command, url, this.logPath)
    try {
      return await server.start()
    } catch (problem) {
      // Another of her windows may have started it a moment before: its server holds the folder's lock (D435), and
      // ours exited. Then that one is the server -- when it proves to be hers.
      if (problem instanceof ServerStartError && problem.exited) {
        if (await this.winnerAnswers(url)) {
          this.log(`another start was first; using its server at ${url}`)
          return url
        }
        // Her documents are held by a server that is not on her port and cannot prove to be hers: her own from before
        // E8.5 (on 8765, with no key), still running after an update (CODE-100's twin for the upgrade).
        if (FOLDER_HELD.test(problem.message)) {
          throw new ServerStartError(
            'Your documents are in use by another Claudia server on this computer: most likely your own, of an older version, which is still running.\n' +
              `It stops by itself ten minutes after its last window has closed. ${this.endTheServer} Then start again.`,
          )
        }
      }
      throw problem
    }
  }

  private async winnerAnswers(url: string): Promise<boolean> {
    const sleep = this.options.sleep ?? defaultSleep
    const until = Date.now() + (this.options.raceWaitMs ?? 30_000)
    for (;;) {
      const found = await this.probe(url)
      if (found.kind === 'claudia' && found.apps.includes(this.options.app)) return this.isMine(url)
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
        // gone? then up again, where the page is; there, nothing happens
        this.origin = await this.ensure(this.origin === null ? undefined : portOf(this.origin))
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

  private ownerKey(): OwnerKey {
    this.key ??= ownerKey(this.options.state)
    return this.key
  }

  private isMine(url: string): Promise<boolean> {
    if (this.options.isMine) return this.options.isMine(url)
    return isOwnedBy(portOf(url), this.ownerKey().key)
  }

  private portFree(port: number): Promise<boolean> {
    return (this.options.portFree ?? ((p) => isPortFree(p)))(port)
  }
}

function urlOf(port: number): string {
  return `http://${LOOPBACK}:${port}`
}

function portOf(url: string): number {
  return Number(new URL(url).port)
}

/** What a server says when another one holds its folder of documents (claudia_server/folder_lock.py, D435). */
const FOLDER_HELD = /another Claudia server uses /

function defaultMakeServer(command: string[], url: string, log: string): ServerProcess {
  return new LocalServer(command, { url, log })
}

function defaultConnect(url: string): PresenceSocket {
  return new WebSocket(url) as unknown as PresenceSocket
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
