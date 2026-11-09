// The local server a window starts for itself (E0.2/D115), adapted from
// clients/linux/src/claudia_shell_gtk/server.py and clients/macos/src/server.ts for Node and Windows.
//
// Differences from both, all stemming from Windows having neither POSIX process groups nor real signals:
//  - Node's own docs are explicit that `ChildProcess.kill()` ignores the `signal` argument on Windows and always
//    terminates the process outright ("similar to SIGKILL"), whatever is passed. So unlike server.py's SIGTERM-then-
//    SIGKILL-after-a-grace-period (Linux) or server.ts's same two-step fallback (macOS, minus the PDEATHSIG belt),
//    there is no softer first signal to send here at all -- one `kill()` call already is the hard stop. `stop()`
//    keeps the same two-argument shape and `graceMs` option as the other two for interface parity (a caller that
//    does not care which OS it is on can still call `await server.stop()`), but the grace period is dead code on
//    this platform: nothing happens between the first kill and the timeout that a second, different kill would
//    change, so there is no second call. This is written down here rather than silently matched, because it is a
//    real product gap, not just an implementation detail: **a hard-killed Python `claudia_server` gets no
//    SIGTERM-driven graceful shutdown on Windows at all**, the same gap server.ts flags for "the shell itself is
//    killed outright" on macOS, just arriving a step earlier here (it is already true of this module's own normal
//    stop() path, not only of an abnormal shell death). Whether that matters depends on what claudia_server's own
//    signal handler does on shutdown today, which this client does not know and has not checked.
//  - `detached: true` on Windows makes the child "not share its console with the parent" (Node's own docs) but, per
//    the same docs, does *not* give it its own killable process group the way POSIX does -- so unlike server.ts's
//    POSIX `child.kill(signal)` reaching a negative pid (the whole group) for free, there is nothing here to reach
//    a `claudia_server` that has itself spawned children. Not solved here either: flagged in the implementation
//    notes next to the point above, both left for whoever picks up E5.11's "not done" list for Windows.
//  - No `--lifeline` on the real server (server.ts's own comment on this already applies unchanged: only the
//    spike's stand-in server had one).

import { spawn as nodeSpawn, type ChildProcess } from 'node:child_process'
import { closeSync, existsSync, mkdirSync, openSync, readFileSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { randomBytes } from 'node:crypto'

export const LOOPBACK = '127.0.0.1'
const HEALTH_PATH = '/api/health'
/** How much of the log's tail a start-up error quotes -- same figure as server.py's and server.ts's own `LOG_TAIL`. */
const LOG_TAIL = 2000

export class ServerStartError extends Error {}

/** A port on `host` nobody is listening on right now (mirrors `free_port()` in the Linux client's server.py and
 * `freePort()` in the macOS client's server.ts). The port can in principle be taken by something else between this
 * call returning and the server actually binding it -- same race both other clients accept, not solved here either. */
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
 * the page and its WebSocket share an origin and no `--allow-origin` is needed (same reasoning as `server.py`'s
 * `composes_command` and `server.ts`'s `buildServerCommand`). */
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
 * spawn time, so closing this process's copy right after does not touch the child's. */
export function defaultSpawn(command: string[], logPath: string): ChildProcess {
  const [program, ...args] = command
  if (!program) throw new Error('empty command')
  mkdirSync(dirname(logPath), { recursive: true })
  const fd = openSync(logPath, 'a')
  try {
    // `detached: true` is kept, matching server.ts, even though it buys Windows no process-group kill (this
    // module's top comment) -- it still does what Node's docs promise on every platform: the child survives this
    // process exiting unexpectedly rather than being torn down mid-flight by whatever the OS does to console
    // children, which is the one half of "detached" Windows does honour.
    //
    // `windowsHide: true` is the other half of that same trade-off, Windows-only (a no-op everywhere else, per
    // Node's own docs): without it, Windows gives a `detached` child its own new, visible console window --
    // found on a real Windows run, 2026-11-09, as "the Python server starts in a separate console [window]". The
    // server's stdout/stderr are already redirected to `logPath` via `fd`, never to that console (there was
    // nothing to see in it), so the window was never anything but a confusing, empty distraction -- this flag is
    // Node's own documented way to suppress it without touching where the output actually goes.
    return nodeSpawn(program, args, { detached: true, windowsHide: true, stdio: ['ignore', fd, fd] })
  } finally {
    closeSync(fd)
  }
}

/** A fresh path under the OS temp directory, for when no explicit `log` option is given -- the same "always have
 * somewhere to look" fallback server.py uses via `tempfile.mkstemp` and server.ts via `tmpdir()`. */
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
   * from the `graceMs` an explicit stop() call takes, mainly so a test can keep this short without changing what a
   * deliberate stop() call elsewhere defaults to. Kept for interface parity with server.ts even though, per this
   * module's top comment, nothing on Windows actually happens during the wait. */
  stopGraceMs?: number
  /** Where the server's stdout/stderr are appended (mirrors server.py's and server.ts's own `log`). Defaults to a
   * fresh file under the OS temp directory, so there is always somewhere to look even when the caller does not
   * pick one. */
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
   * discipline as server.py's and server.ts's own docstrings ask of a GUI toolkit's main loop). Throws (and stops
   * the server) once it has exited, failed to start at all, or has not answered within the timeout. */
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

  /** The log's last `LOG_TAIL` characters, formatted for a ServerStartError message -- or '' when there is nothing
   * to show (mirrors server.py's and server.ts's own `whatItSaid`/`_what_it_said`). Never throws: a log read
   * failing is not a reason to hide the error that triggered this in the first place. */
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

  /** End the server. On every other OS this is SIGTERM, then SIGKILL after `graceMs`; on Windows (this module's
   * top comment) the first `kill()` already is the hard stop, so `graceMs` only bounds how long this waits for the
   * 'exit' event to arrive, not a second, harder attempt. Safe to call before spawn(), twice, and after the
   * server died on its own. Resolves as soon as the process is gone, not necessarily after the full grace period. */
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
      process.kill() // signal argument ignored on Windows (Node's own docs); this is already the hard stop
      // Nothing a second call could do differently -- kept only so a hung 'exit' event (the process gone from the
      // OS's view but Node slow to report it) does not leave this promise unsettled forever.
      const timer = setTimeout(finish, graceMs)
    })
  }
}
