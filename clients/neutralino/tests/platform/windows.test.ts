// What is Windows' own on the native side (src/platform/windows.ts, D660): taskkill for a server's process tree, and the
// spawn options of a server that must not open a console window. `spawn` is wrapped so a test can see the options it
// was given (`windowsHide` leaves no trace on the ChildProcess itself) and so taskkill is never really run.
import { EventEmitter } from 'node:events'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defaultSpawn } from '../../src/server.js'
import { WINDOWS_HOST, killProcessTree, localAppData } from '../../src/platform/windows.js'

// `vi.hoisted` so `spawnSpy` exists by the time `vi.mock`'s own factory (hoisted above every import) first runs.
const { spawnSpy } = vi.hoisted(() => ({ spawnSpy: vi.fn() }))
vi.mock('node:child_process', async (importOriginal) => {
  const actual = await importOriginal<typeof import('node:child_process')>()
  spawnSpy.mockImplementation(actual.spawn)
  return { ...actual, spawn: spawnSpy }
})

describe('killProcessTree', () => {
  it('is not available off Windows, and then runs nothing', async () => {
    spawnSpy.mockClear()
    expect(await killProcessTree(4242, 'linux')).toBe(false)
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
    expect(await killProcessTree(4242, 'win32')).toBe(true)
    expect(spawnSpy).toHaveBeenCalledWith('taskkill', ['/pid', '4242', '/T', '/F'], expect.objectContaining({ windowsHide: true }))
    spawnSpy.mockImplementationOnce(fake(128)) // "process not found": already gone, the caller falls back to kill()
    expect(await killProcessTree(4242, 'win32')).toBe(false)
  })

  it('reports false when taskkill cannot be started', async () => {
    spawnSpy.mockImplementationOnce(() => {
      const killer = new EventEmitter()
      queueMicrotask(() => killer.emit('error', new Error('ENOENT')))
      return killer as never
    })
    expect(await killProcessTree(4242, 'win32')).toBe(false)
  })
})

describe('the server process', () => {
  let dir = ''
  afterEach(() => rmSync(dir, { recursive: true, force: true }))

  it('is started without a console window of its own ("the Python server starts in a separate console", a real Windows run)', async () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-server-log-'))
    spawnSpy.mockClear()
    const child = defaultSpawn(['node', '-e', 'process.exit(0)'], join(dir, 'server.log'))
    await new Promise<void>((resolve) => child.once('exit', () => resolve()))
    const options = spawnSpy.mock.calls[0]?.[2] as Record<string, unknown> | undefined
    expect(options?.windowsHide).toBe(true) // a no-op on a Mac, where it is passed all the same
    expect(options?.detached).toBe(true)
  })
})

describe('WINDOWS_HOST', () => {
  it('keeps the suite in %LOCALAPPDATA%\\Claudia, and finds the venv interpreter in Scripts', () => {
    expect(WINDOWS_HOST.claudiaFolder({ LOCALAPPDATA: 'L' }, 'H')).toBe(join('L', 'Claudia'))
    expect(localAppData({}, 'H')).toBe(join('H', 'AppData', 'Local'))
    expect(WINDOWS_HOST.venvPython).toEqual(['.venv', 'Scripts', 'python.exe'])
  })

  it('starts the downloaded binary as it is: no bundle, no process name of its own', () => {
    expect(WINDOWS_HOST.windowBinary('apps/creates', 'C:\\neutralino-win_x64.exe', undefined as never)).toEqual({ binary: 'C:\\neutralino-win_x64.exe' })
  })
})
