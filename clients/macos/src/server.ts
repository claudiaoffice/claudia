// The local server a window starts for itself (E0.2/D115), adapted from
// clients/linux/src/claudia_shell_gtk/server.py for Node and macOS.
//
// Three differences from the Linux version, all macOS having no equivalent of Linux's PR_SET_PDEATHSIG:
//  - no "the kernel kills the server for us if the shell is kill -9'd" guarantee. `spawn()` still asks for its own
//    process group (`detached: true`, POSIX) so `stop()` can reach everything the server itself started, but if
//    *this* process is killed outright rather than exited normally, the spawned server can be left running. Not
//    solved here -- flagged in the implementation notes the same way the spike flagged "what happens when the
//    Neutralino window is killed rather than closed is untested" (notes/e0-3-neutralino-windows-macos.md).
//  - the real `claudia_server` package has no `--lifeline`/stdin-close option (only the *spike's* own
//    `testserver.py` did) -- so stop() here only has SIGTERM/SIGKILL, the same two Linux falls back to, just
//    without Linux's belt-and-braces PDEATHSIG as well.
//  - `os.killpg` is POSIX and exists on macOS too (unlike the signal-group call's Windows caveat in server.py's
//    own comments) -- `child.kill(signal)` here is sent to the negative pid Node gives a detached child's group
//    leader automatically on POSIX, so no extra API is needed for that part.

import { spawn as nodeSpawn, type ChildProcess } from 'node:child_process'
import { closeSync, existsSync, mkdirSync, openSync, readFileSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { randomBytes } from 'node:crypto'

export const LOOPBACK = '127.0.0.1'
const HEALTH_PATH = '/api/health'
/** How much of the log's tail a start-up error quotes -- same figure as server.py's own `_LOG_TAIL`. */
const LOG_TAIL = 2000

export class ServerStartError extends Error {}

/** A port on `host` nobody is listening on right now (mirrors `free_port()` in the Linux client's server.py). The
 * port can in principle be taken by something else between this call returning and the server actually binding it
 * -- same race the Linux version accepts, not solved here either. */
export function freePort(host: string = LOOPBACK): Promise<number> {
  return new Promise((resolve, reject) => {
    const probe = createServer()
    probe.once('error', reject)
    probe.listen(0, host, () => {
      const address = probe.address()
      probe.close(() => {
        if (address && typeof address === 'object') resolve(address.port)
        else reject(new Error('could not read the probed port back from the OS'))
      })
    })
  })
}

export interface ServerCommandOptions {
  model: string
  port: number
  documents: string
  web: string
  state: string
}

/** The command line of one app's server on this computer: loopback only, serving the bundled frontend itself so
 * the page and its WebSocket share an origin and no `--allow-origin` is needed (same reasoning as
 * `composes_command` in server.py). */
export function buildServerCommand(python: string, options: ServerCommandOptions): string[] {
  return [
    python,
    '-m',
    'claudia_server',
    '--model',
    options.model,
    '--host',
    LOOPBACK,
    '--port',
    String(options.port),
    '--no-tls',
    '--dir',
    options.documents,
    '--state-dir',
    options.state,
    '--web',
    options.web,
  ]
}

type SpawnFn = (command: string[], logPath: string) => ChildProcess
type HealthFn = (url: string) => Promise<boolean>

/** Starts `command` with its stdout and stderr both appended to `logPath` (merged, like server.py's own
 * `stderr=subprocess.STDOUT`) -- the thing a start-up failure is otherwise silent about. The fd is opened and
 * handed to the child via `stdio`, then closed in this process: the child gets its own duplicated descriptor at
 * spawn time (POSIX), so closing this process's copy right after does not touch the child's. */
export function defaultSpawn(command: string[], logPath: string): ChildProcess {
  const [program, ...args] = command
  if (!program) throw new Error('empty command')
  mkdirSync(dirname(logPath), { recursive: true })
  const fd = openSync(logPath, 'a')
  try {
    return nodeSpawn(program, args, { detached: true, stdio: ['ignore', fd, fd] })
  } finally {
    closeSync(fd)
  }
}

/** A fresh path under the OS temp directory, for when no explicit `log` option is given -- the same "always have
 * somewhere to look" fallback `spawn()` in server.py uses via `tempfile.mkstemp`. */
function tempLogPath(): string {
  return join(tmpdir(), `claudia-server-${randomBytes(6).toString('hex')}.log`)
}

async function defaultHealth(url: string): Promise<boolean> {
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 500)
    try {
      const response = await fetch(url + HEALTH_PATH, { signal: controller.signal })
      return response.ok
    } finally {
      clearTimeout(timer)
    }
  } catch {
    return false
  }
}

export interface LocalServerOptions {
  url: string
  spawnFn?: SpawnFn
  healthFn?: HealthFn
  startupTimeoutMs?: number
  nowFn?: () => number
  /** The grace period checkReady() itself uses when it auto-stops a dead-on-arrival or timed-out server. Separate
   * from the `graceMs` an explicit stop() call takes, mainly so a test can keep this short without changing what
   * a deliberate stop() call elsewhere defaults to. */
  stopGraceMs?: number
  /** Where the server's stdout/stderr are appended (mirrors server.py's own `log`). Defaults to a fresh file
   * under the OS temp directory, so there is always somewhere to look even when the caller does not pick one. */
  log?: string
}

/** One server process: spawn() it, ask checkReady() until it answers, stop() it. */
export class LocalServer {
  readonly url: string
  readonly logPath: string
  private readonly command: string[]
  private readonly spawnFn: SpawnFn
  private readonly healthFn: HealthFn
  private readonly startupTimeoutMs: number
  private readonly nowFn: () => number
  private readonly stopGraceMs: number
  private process: ChildProcess | null = null
  private spawnedAt = 0
  private ready = false
  /** Set by the child's own 'error' event -- the OS refusing to start the process at all (ENOENT, EACCES, ...),
   * which Node reports this way instead of as an ordinary exit. Left unhandled, 'error' is fatal to the whole
   * process; checkReady() turns it into a plain ServerStartError like every other start-up failure here. */
  private spawnError: Error | null = null

  constructor(command: string[], options: LocalServerOptions) {
    this.command = command
    this.url = options.url
    this.logPath = options.log ?? tempLogPath()
    this.spawnFn = options.spawnFn ?? defaultSpawn
    this.healthFn = options.healthFn ?? defaultHealth
    this.startupTimeoutMs = options.startupTimeoutMs ?? 30_000
    this.nowFn = options.nowFn ?? (() => Date.now())
    this.stopGraceMs = options.stopGraceMs ?? 3000
  }

  get pid(): number | undefined {
    return this.process?.pid
  }

  get running(): boolean {
    return this.process !== null && this.process.exitCode === null && !this.process.killed
  }

  spawn(): void {
    if (this.process !== null) throw new Error('the server was started already')
    this.spawnError = null
    this.process = this.spawnFn(this.command, this.logPath)
    this.process.on('error', (error) => {
      this.spawnError = error
    })
    this.spawnedAt = this.nowFn()
    this.ready = false
  }

  /** Does the server answer yet? Never blocks for long (the caller polls this from its own event loop, same
   * discipline as server.py's own docstring asks of GTK's main loop). Throws (and stops the server) once it has
   * exited, failed to start at all, or has not answered within the timeout. */
  async checkReady(): Promise<boolean> {
    const process = this.process
    if (process === null) throw new Error('the server was not started')
    if (this.ready) return true
    if (this.spawnError !== null) {
      const message = this.spawnError.message
      await this.stop(this.stopGraceMs)
      throw new ServerStartError(`the server could not be started: ${message}${this.whatItSaid()}`)
    }
    if (process.exitCode !== null) {
      await this.stop(this.stopGraceMs)
      throw new ServerStartError(`the server stopped at start-up (exit code ${process.exitCode})${this.whatItSaid()}`)
    }
    if (await this.healthFn(this.url)) {
      this.ready = true
      return true
    }
    if (this.nowFn() - this.spawnedAt > this.startupTimeoutMs) {
      await this.stop(this.stopGraceMs)
      throw new ServerStartError(
        `the server did not answer at ${this.url} within ${this.startupTimeoutMs}ms${this.whatItSaid()}`,
      )
    }
    return false
  }

  /** The log's last `LOG_TAIL` characters, formatted for a ServerStartError message -- or '' when there is
   * nothing to show (mirrors server.py's own `_what_it_said()`). Never throws: a log read failing is not a
   * reason to hide the error that triggered this in the first place. */
  private whatItSaid(): string {
    try {
      if (!existsSync(this.logPath)) return ''
      const tail = readFileSync(this.logPath, 'utf8').slice(-LOG_TAIL).trim()
      return tail ? `\n--- what the server printed (${this.logPath}) ---\n${tail}` : ''
    } catch {
      return ''
    }
  }

  /** spawn(), then wait until the server answers. Returns its address. */
  async start(): Promise<string> {
    this.spawn()
    for (;;) {
      if (await this.checkReady()) return this.url
      await new Promise((resolve) => setTimeout(resolve, 50))
    }
  }

  /** End the server: SIGTERM, then SIGKILL after `graceMs` if it has not exited by then. Safe to call before
   * spawn(), twice, and after the server died on its own. Resolves as soon as the process is gone, not necessarily
   * after the full grace period. */
  async stop(graceMs = 3000): Promise<void> {
    const process = this.process
    if (process === null) return
    this.process = null
    if (process.exitCode !== null) return // already gone
    await new Promise<void>((resolve) => {
      let settled = false
      const finish = () => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        resolve()
      }
      process.once('exit', finish)
      process.kill('SIGTERM')
      // No PDEATHSIG-equivalent and no --lifeline (see this module's top comment): SIGKILL is the only fallback
      // if the process has not gone by the grace period. Sent, then treated as done -- SIGKILL cannot be caught
      // or ignored, so there is nothing further worth waiting for even though the OS reports exit asynchronously.
      const timer = setTimeout(() => {
        process.kill('SIGKILL')
        finish()
      }, graceMs)
    })
  }
}
