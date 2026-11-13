// Mirrors clients/linux/src/claudia_shell_gtk/server.py's and clients/macos/tests/server.test.ts's own tests
// (command construction, spawn/checkReady/stop). The one real behavioural difference from both -- no SIGTERM-then-
// SIGKILL two-step, because Node ignores the signal argument on Windows and `kill()` is already the hard stop --
// is covered by its own describe block below; everything else here is the same contract macOS already tests the
// same way, because LocalServer's logic (ready/not-ready, log capture, idempotent stop) does not change per OS.
import { EventEmitter } from 'node:events'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LocalServer, ServerStartError, buildServerCommand, defaultKillTree, defaultSpawn, freePort } from '../src/server.js'

// Wraps the real `spawn` so defaultSpawn's own tests below still get a genuine child process (and the log-capture
// test still sees genuine output), while letting one test inspect exactly what options defaultSpawn passed it --
// the only way to check `windowsHide`, which (unlike `detached`) leaves no trace on the ChildProcess object itself
// afterwards for a test to read back. `vi.hoisted` so `spawnSpy` exists by the time `vi.mock`'s own factory
// (hoisted above every import, including the `const` below it) first runs.
const { spawnSpy } = vi.hoisted(() => ({ spawnSpy: vi.fn() }))
vi.mock('node:child_process', async (importOriginal) => {
  const actual = await importOriginal<typeof import('node:child_process')>()
  spawnSpy.mockImplementation(actual.spawn)
  return { ...actual, spawn: spawnSpy }
})

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
  it("matches the Linux and macOS clients' command shape, for the given model", () => {
    const command = buildServerCommand('C:\\repo\\.venv\\Scripts\\python.exe', {
      model: 'claudia_composes:TextModel',
      port: 41233,
      documents: 'C:\\docs',
      web: 'C:\\frontend',
      state: 'C:\\state',
    })
    expect(command).toEqual([
      'C:\\repo\\.venv\\Scripts\\python.exe',
      '-m',
      'claudia_server',
      '--model',
      'claudia_composes:TextModel',
      '--host',
      '127.0.0.1',
      '--port',
      '41233',
      '--no-tls',
      '--dir',
      'C:\\docs',
      '--state-dir',
      'C:\\state',
      '--web',
      'C:\\frontend',
    ])
  })
})

/** A fake child process good enough for LocalServer: an EventEmitter with pid/kill, controlled entirely by the
 * test -- same fixture as the Linux and macOS test suites use, for the same reason (no real server to spawn here). */
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
    const server = new LocalServer(['C:\\does\\not\\exist.exe'], {
      url: 'http://127.0.0.1:1',
      spawnFn: () => child as never,
      healthFn: async () => false,
      stopGraceMs: 1, // the auto-stop this triggers isn't what this test is about; keep it fast
    })
    server.spawn()
    child.emit('error', new Error('spawn C:\\does\\not\\exist.exe ENOENT'))
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
  // _what_it_said(), already ported once for macOS, ported again here).
  let dir: string
  afterEach(() => {
    if (dir) rmSync(dir, { recursive: true, force: true })
  })

  it("ServerStartError quotes the log's tail when the process exits before answering", async () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-server-log-'))
    const log = join(dir, 'server.log')
    writeFileSync(log, 'ModuleNotFoundError: no module named claudia_server\n')
    const child = new FakeChildProcess()
    const server = new LocalServer(['python'], {
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
    const server = new LocalServer(['python'], {
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
    const server = new LocalServer(['python'], { url: 'http://127.0.0.1:1' })
    const before = server.logPath
    expect(before.length).toBeGreaterThan(0)
    server.spawn()
    expect(server.logPath).toBe(before) // stable across spawn(), not re-rolled
  })

  it('an explicit log path is used as-is, and its parent directory is created', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-server-log-'))
    const log = join(dir, 'nested', 'server.log')
    const server = new LocalServer(['python'], { url: 'http://127.0.0.1:1', log, spawnFn: () => new FakeChildProcess() as never })
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

  it('passes windowsHide: true -- Windows-only, a no-op elsewhere per Node\'s own docs, suppressing the new, ' +
    'empty console window `detached: true` otherwise pops up on a real Windows run (found 2026-11-09: "the ' +
    'Python server starts in a separate console")', async () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-server-log-'))
    const log = join(dir, 'server.log')
    spawnSpy.mockClear()
    const child = defaultSpawn(['node', '-e', 'process.exit(0)'], log)
    await new Promise<void>((resolve) => child.once('exit', () => resolve()))
    expect(spawnSpy).toHaveBeenCalledOnce()
    const options = spawnSpy.mock.calls[0]?.[2] as Record<string, unknown> | undefined
    expect(options?.windowsHide).toBe(true)
    expect(options?.detached).toBe(true) // unchanged by this fix -- still needed for the other half of this trade-off
  })
})

describe('LocalServer', () => {
  it('is not ready until health() says so, and checkReady() never blocks', async () => {
    const child = new FakeChildProcess()
    const spawn = vi.fn(() => child as never)
    let healthy = false
    const health = vi.fn(async () => healthy)
    const server = new LocalServer(['python', '-m', 'claudia_server'], {
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
    const server = new LocalServer(['python'], {
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
    const server = new LocalServer(['python'], {
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

  it('stop() is a no-op before spawn(), and safe to call twice', async () => {
    const server = new LocalServer(['python'], { url: 'http://127.0.0.1:1' })
    await server.stop(1)
    const child = new FakeChildProcess()
    const spawned = new LocalServer(['python'], { url: 'http://127.0.0.1:1', spawnFn: () => child as never })
    spawned.spawn()
    await spawned.stop(1)
    await spawned.stop(1) // second call: process is already gone, must not throw
  })

  it('stop() resolves as soon as the real process reports exit, without waiting out the grace period', async () => {
    const child = new FakeChildProcess()
    const server = new LocalServer(['python'], { url: 'http://127.0.0.1:1', spawnFn: () => child as never })
    server.spawn()
    const stopping = server.stop(5000)
    queueMicrotask(() => child.exit(0))
    await stopping
    expect(child.kill).toHaveBeenCalledTimes(1) // one call is already the hard stop on Windows (this module's top comment)
  })
})

describe('stop() on Windows: one kill() call, no softer SIGTERM step', () => {
  // What this guards against regressing to: copying the Linux/macOS SIGTERM-then-SIGKILL shape unchanged here
  // would be harmless in a test with a fake child (it would just call kill() twice), but wrong about what actually
  // happens on a real Windows process -- server.ts's own top comment is explicit that Node ignores the signal
  // argument there, so a second, "harder" kill() is not a fallback, it is the same call again.
  it('calls kill() exactly once even when the process never reports exit before the grace period elapses', async () => {
    const child = new FakeChildProcess()
    const server = new LocalServer(['python'], { url: 'http://127.0.0.1:1', spawnFn: () => child as never })
    server.spawn()
    await server.stop(5) // the fake never emits 'exit'; this waits out the grace period and resolves anyway
    expect(child.kill).toHaveBeenCalledTimes(1)
    expect(child.kill).toHaveBeenCalledWith()
  })
})

describe('stop() ends the whole tree (the venv launcher of `.venv\\Scripts\\python.exe` has the real server as its child)', () => {
  it('uses the tree kill when it has the pid, and does not kill() the launcher alone', async () => {
    const child = new FakeChildProcess()
    ;(child as unknown as { pid: number }).pid = 4242
    const killed: number[] = []
    const server = new LocalServer(['python'], {
      url: 'http://127.0.0.1:1',
      spawnFn: () => child as never,
      killTree: async (pid) => {
        killed.push(pid)
        queueMicrotask(() => child.exit(1))
        return true
      },
    })
    server.spawn()
    await server.stop(1000)
    expect(killed).toEqual([4242])
    expect(child.kill).not.toHaveBeenCalled()
  })

  it('falls back to kill() when the tree kill could not be done', async () => {
    const child = new FakeChildProcess()
    ;(child as unknown as { pid: number }).pid = 4242
    const server = new LocalServer(['python'], { url: 'http://127.0.0.1:1', spawnFn: () => child as never, killTree: async () => false })
    server.spawn()
    await server.stop(20)
    expect(child.kill).toHaveBeenCalledTimes(1)
  })
})

describe('defaultKillTree', () => {
  it('is not available off Windows, and then runs nothing', async () => {
    spawnSpy.mockClear()
    expect(await defaultKillTree(4242, 'linux')).toBe(false)
    expect(spawnSpy).not.toHaveBeenCalled()
  })

  it('asks taskkill for the tree, forcibly and without a console window, and reports whether it worked', async () => {
    // A stand-in for taskkill: never run the real one in a test (on a Windows host it would end process 4242).
    const fake = (code: number) => () => {
      const killer = new EventEmitter()
      queueMicrotask(() => killer.emit('exit', code))
      return killer as never
    }
    spawnSpy.mockClear()
    spawnSpy.mockImplementationOnce(fake(0))
    expect(await defaultKillTree(4242, 'win32')).toBe(true)
    expect(spawnSpy).toHaveBeenCalledWith('taskkill', ['/pid', '4242', '/T', '/F'], expect.objectContaining({ windowsHide: true }))
    spawnSpy.mockImplementationOnce(fake(128)) // "process not found": already gone, the caller falls back to kill()
    expect(await defaultKillTree(4242, 'win32')).toBe(false)
  })

  it('reports false when taskkill cannot be started', async () => {
    spawnSpy.mockImplementationOnce(() => {
      const killer = new EventEmitter()
      queueMicrotask(() => killer.emit('error', new Error('ENOENT')))
      return killer as never
    })
    expect(await defaultKillTree(4242, 'win32')).toBe(false)
  })
})
