// Mirrors clients/linux/src/claudia_shell_gtk/server.py's own tests (command construction, spawn/check_ready/stop),
// adapted for Node + macOS: no PR_SET_PDEATHSIG (Linux-only), so this relies on `detached: true`'s POSIX process
// group plus an explicit SIGTERM/SIGKILL from stop() -- there is no equivalent of Linux's "the kernel kills the
// server if the shell is kill -9'd" guarantee here yet (see server.ts's own top comment and the implementation
// notes: an open item, not silently assumed solved).
import { EventEmitter } from 'node:events'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LocalServer, ServerStartError, buildServerCommand, defaultSpawn, freePort } from '../src/server.js'

describe('freePort', () => {
  it('returns a port nobody is listening on yet, and two calls do not collide', async () => {
    const a = await freePort()
    const b = await freePort()
    expect(a).toBeGreaterThan(0)
    expect(b).toBeGreaterThan(0)
    expect(a).not.toBe(b) // the OS does not hand out the same ephemeral port twice back to back
  })
})

describe('buildServerCommand', () => {
  it('matches the Linux client\'s composes_command shape, for the given model', () => {
    const command = buildServerCommand('/usr/bin/python3.14', {
      model: 'claudia_creates:SlideModel',
      port: 41233,
      documents: '/docs',
      web: '/frontend',
      state: '/state',
    })
    expect(command).toEqual([
      '/usr/bin/python3.14',
      '-m',
      'claudia_server',
      '--model',
      'claudia_creates:SlideModel',
      '--host',
      '127.0.0.1',
      '--port',
      '41233',
      '--no-tls',
      '--dir',
      '/docs',
      '--state-dir',
      '/state',
      '--web',
      '/frontend',
    ])
  })
})

/** A fake child process good enough for LocalServer: an EventEmitter with pid/kill, controlled entirely by the
 * test (no real process spawned, matching how server_test.py in the Linux client uses a fake command rather than
 * a real server in most of its tests -- here there is no equivalent fixture server at all, so the fake stands in
 * for one everywhere). */
class FakeChildProcess extends EventEmitter {
  pid = 4242
  killed = false
  exitCode: number | null = null // matches Node's own ChildProcess: null until the process has actually exited
  kill = vi.fn((_signal?: string) => {
    this.killed = true
    return true
  })
  /** What Node itself does right before emitting 'exit': set exitCode, then emit. Tests call this instead of a
   * raw .emit('exit', ...) so checkReady()/stop() see the same exitCode a real ChildProcess would have. */
  exit(code: number | null): void {
    this.exitCode = code
    this.emit('exit', code, null)
  }
}

describe("LocalServer and a spawn that never starts (ENOENT and friends)", () => {
  // The bug this guards against: Node's ChildProcess emits 'error' (not 'exit') when the OS itself refuses to
  // start the process at all (a bad interpreter path, no execute permission, ...). Nothing in checkReady() used to
  // listen for that, so it became an *unhandled* 'error' event -- which Node treats as fatal and crashes the whole
  // process, uncaught, instead of becoming a plain ServerStartError like every other start-up failure here.
  it("checkReady() raises ServerStartError instead of leaving 'error' unhandled", async () => {
    const child = new FakeChildProcess()
    const server = new LocalServer(['/does/not/exist'], {
      url: 'http://127.0.0.1:1',
      spawnFn: () => child as never,
      healthFn: async () => false,
      stopGraceMs: 1, // the auto-stop this triggers isn't what this test is about; keep it fast
    })
    server.spawn()
    child.emit('error', new Error('spawn /does/not/exist ENOENT'))
    let caught: unknown
    try {
      await server.checkReady()
    } catch (error) {
      caught = error
    }
    expect(caught).toBeInstanceOf(ServerStartError)
    expect((caught as Error).message).toMatch(/ENOENT/)
  })
})

describe('LocalServer log capture', () => {
  // The bug this guards against: a server that exits at start-up with no indication *why*, which is exactly what
  // a person sees from the shell if stdout/stderr are piped and nobody ever reads the pipe (server.py's own
  // _what_it_said() is the thing being ported here -- it was missing from the first round of this port).
  let dir: string
  afterEach(() => {
    if (dir) rmSync(dir, { recursive: true, force: true })
  })

  it("ServerStartError quotes the log's tail when the process exits before answering", async () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-server-log-'))
    const log = join(dir, 'server.log')
    writeFileSync(log, 'ModuleNotFoundError: no module named claudia_server\n')
    const child = new FakeChildProcess()
    const server = new LocalServer(['python3'], {
      url: 'http://127.0.0.1:1',
      spawnFn: () => child as never,
      healthFn: async () => false,
      log,
    })
    server.spawn()
    child.exit(1)
    await expect(server.checkReady()).rejects.toThrow(/ModuleNotFoundError/)
  })

  it('says nothing extra when the log is empty or does not exist yet', async () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-server-log-'))
    const log = join(dir, 'never-written.log')
    const child = new FakeChildProcess()
    const server = new LocalServer(['python3'], {
      url: 'http://127.0.0.1:1',
      spawnFn: () => child as never,
      healthFn: async () => false,
      log,
    })
    server.spawn()
    child.exit(1)
    await expect(server.checkReady()).rejects.toThrow('the server stopped at start-up (exit code 1)')
  })

  it('logPath defaults to a temp file when none is given, and is exposed before and after spawn()', () => {
    const server = new LocalServer(['python3'], { url: 'http://127.0.0.1:1' })
    const before = server.logPath
    expect(before.length).toBeGreaterThan(0)
    server.spawn()
    expect(server.logPath).toBe(before) // stable across spawn(), not re-rolled
  })

  it('an explicit log path is used as-is, and its parent directory is created', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-server-log-'))
    const log = join(dir, 'nested', 'server.log')
    const server = new LocalServer(['python3'], { url: 'http://127.0.0.1:1', log, spawnFn: () => new FakeChildProcess() as never })
    expect(server.logPath).toBe(log)
    server.spawn() // must not throw NOENT for the not-yet-existing 'nested' directory
  })
})

describe('defaultSpawn', () => {
  let dir: string
  afterEach(() => {
    if (dir) rmSync(dir, { recursive: true, force: true })
  })

  it("writes the real child's stdout and stderr to the given log file (merged, like server.py's stderr=STDOUT)", async () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-server-log-'))
    const log = join(dir, 'server.log')
    const child = defaultSpawn(
      ['node', '-e', "console.log('from stdout'); console.error('from stderr'); process.exit(3)"],
      log,
    )
    const [code] = await new Promise<[number | null]>((resolve) => child.once('exit', (c) => resolve([c])))
    expect(code).toBe(3)
    const { readFileSync } = await import('node:fs')
    const written = readFileSync(log, 'utf8')
    expect(written).toContain('from stdout')
    expect(written).toContain('from stderr')
  })
})

describe('LocalServer', () => {
  it('is not ready until health() says so, and check_ready never blocks', async () => {
    const child = new FakeChildProcess()
    const spawn = vi.fn(() => child as never)
    let healthy = false
    const health = vi.fn(async () => healthy)
    const server = new LocalServer(['python3', '-m', 'claudia_server'], {
      url: 'http://127.0.0.1:1',
      spawnFn: spawn,
      healthFn: health,
    })
    server.spawn()
    expect(spawn).toHaveBeenCalledOnce()
    expect(await server.checkReady()).toBe(false)
    healthy = true
    expect(await server.checkReady()).toBe(true)
  })

  it('raises ServerStartError and stops the process if it exits before answering', async () => {
    const child = new FakeChildProcess()
    const server = new LocalServer(['python3'], {
      url: 'http://127.0.0.1:1',
      spawnFn: () => child as never,
      healthFn: async () => false,
    })
    server.spawn()
    child.exit(7)
    await expect(server.checkReady()).rejects.toThrow(ServerStartError)
  })

  it('raises ServerStartError after the startup timeout elapses with no answer', async () => {
    const child = new FakeChildProcess()
    let now = 0
    const server = new LocalServer(['python3'], {
      url: 'http://127.0.0.1:1',
      spawnFn: () => child as never,
      healthFn: async () => false,
      startupTimeoutMs: 1000,
      nowFn: () => now,
      stopGraceMs: 1, // the auto-stop this triggers isn't what this test is about; keep it fast
    })
    server.spawn()
    expect(await server.checkReady()).toBe(false)
    now = 1001
    await expect(server.checkReady()).rejects.toThrow(ServerStartError)
  })

  it('stop() sends SIGTERM to the process group, then SIGKILL if it has not exited within the grace period', async () => {
    const child = new FakeChildProcess()
    const server = new LocalServer(['python3'], { url: 'http://127.0.0.1:1', spawnFn: () => child as never })
    server.spawn()
    const stopping = server.stop(10)
    expect(child.kill).toHaveBeenCalledWith('SIGTERM')
    // simulate the grace period elapsing without the (fake) process ever exiting
    await stopping
    expect(child.kill).toHaveBeenCalledWith('SIGKILL')
  })

  it('stop() is a no-op before spawn(), and safe to call twice', async () => {
    const server = new LocalServer(['python3'], { url: 'http://127.0.0.1:1' })
    await server.stop(1)
    const child = new FakeChildProcess()
    const spawned = new LocalServer(['python3'], { url: 'http://127.0.0.1:1', spawnFn: () => child as never })
    spawned.spawn()
    await spawned.stop(1)
    await spawned.stop(1) // second call: process is already gone, must not throw
  })

  it('stop() resolves as soon as the real process reports exit, without waiting out the grace period', async () => {
    const child = new FakeChildProcess()
    const server = new LocalServer(['python3'], { url: 'http://127.0.0.1:1', spawnFn: () => child as never })
    server.spawn()
    const stopping = server.stop(5000)
    queueMicrotask(() => child.exit(0))
    await stopping
    expect(child.kill).toHaveBeenCalledTimes(1) // SIGTERM only -- SIGKILL never needed
  })
})
