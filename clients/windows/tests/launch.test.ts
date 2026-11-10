// Mirrors clients/linux/tests/test_launch.py's and clients/macos/tests/launch.test.ts's own scope: prepareServer()
// is tested (a free loopback port, the right command, the documents folder created, missing-python/missing-frontend
// explained with the fix), the real main loop is not -- there the GTK Application.run() loop is the untested
// wiring, here it is the part of main() that actually spawns the compiled Neutralino binary and waits on it (needs
// a real binary on a real Windows machine, not a sandbox; see this package's README). findNeutralinoBinary/
// neutralinoBinaryName/buildShellCommand are the pieces Linux has no equivalent of (GTK *is* the shell process;
// this shell's is a separate compiled binary this launcher must find and start).
import { chmodSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  SetupProblem,
  buildShellCommand,
  findNeutralinoBinary,
  neutralinoBinaryName,
  prepareServer,
} from '../src/launch.js'

describe('prepareServer', () => {
  let repo: string
  let localAppData: string

  beforeEach(() => {
    repo = mkdtempSync(join(tmpdir(), 'claudia-repo-'))
    localAppData = mkdtempSync(join(tmpdir(), 'claudia-localappdata-'))
    const python = join(repo, '.venv', 'Scripts', 'python.exe')
    mkdirSync(join(repo, '.venv', 'Scripts'), { recursive: true })
    writeFileSync(python, '')
    chmodSync(python, 0o755) // X_OK on a Linux test host; a real Windows .venv needs no execute bit at all
    const web = join(repo, 'web', '.output', 'public')
    mkdirSync(web, { recursive: true })
    writeFileSync(join(web, 'index.html'), '<html></html>')
  })

  afterEach(() => {
    rmSync(repo, { recursive: true, force: true })
    rmSync(localAppData, { recursive: true, force: true })
  })

  it('builds a server for the app on a free loopback port, not started yet', async () => {
    const server = await prepareServer('composes', { repo, localAppData, env: {} })
    expect(server.url.startsWith('http://127.0.0.1:')).toBe(true)
    expect(server.running).toBe(false)
  })

  it('points the server at state/server.log, so a start-up failure is not silent', async () => {
    const server = await prepareServer('composes', { repo, localAppData, env: {} })
    expect(server.logPath).toBe(join(localAppData, 'Claudia', 'composes', 'state', 'server.log'))
  })

  it('the documents and state folders exist once prepared', async () => {
    await prepareServer('composes', { repo, localAppData, env: {} })
    expect(() => mkdirSync(join(localAppData, 'Claudia', 'composes', 'documents'))).toThrow() // already exists
    expect(() => mkdirSync(join(localAppData, 'Claudia', 'composes', 'state'))).toThrow()
  })

  it('a missing server python is explained with the way to fix it', async () => {
    rmSync(join(repo, '.venv', 'Scripts', 'python.exe'))
    await expect(prepareServer('composes', { repo, localAppData, env: {} })).rejects.toThrow(SetupProblem)
    await expect(prepareServer('composes', { repo, localAppData, env: {} })).rejects.toThrow(/CLAUDIA_SERVER_PYTHON/)
  })

  it('a missing frontend is explained with the way to fix it', async () => {
    rmSync(join(repo, 'web', '.output', 'public', 'index.html'))
    await expect(prepareServer('composes', { repo, localAppData, env: {} })).rejects.toThrow(SetupProblem)
    await expect(prepareServer('composes', { repo, localAppData, env: {} })).rejects.toThrow(/CLAUDIA_WEB_DIR/)
  })

  it('a wrong explicit frontend path is reported, not silently replaced', async () => {
    await expect(
      prepareServer('composes', { repo, localAppData, env: { CLAUDIA_WEB_DIR: '/nonexistent/frontend' } }),
    ).rejects.toThrow(/nonexistent.frontend/)
  })
})

describe('neutralinoBinaryName', () => {
  it('is the one binary Neutralino 6.8.0 publishes for Windows -- no architecture branch (unlike macOS), see this module\'s own doc comment', () => {
    expect(neutralinoBinaryName()).toBe('neutralino-win_x64.exe')
  })
})

describe('findNeutralinoBinary', () => {
  let appDir: string

  beforeEach(() => {
    appDir = mkdtempSync(join(tmpdir(), 'claudia-app-'))
  })

  afterEach(() => {
    rmSync(appDir, { recursive: true, force: true })
  })

  it('CLAUDIA_NEUTRALINO_BIN, when set, is returned as-is', () => {
    expect(findNeutralinoBinary({ appDir, env: { CLAUDIA_NEUTRALINO_BIN: 'C:\\opt\\neutralino-win_x64.exe' } })).toBe(
      'C:\\opt\\neutralino-win_x64.exe',
    )
  })

  it("falls back to <appDir>/bin/neutralino-win_x64.exe -- where `neu update` itself places it -- when it exists", () => {
    mkdirSync(join(appDir, 'bin'))
    const binary = join(appDir, 'bin', 'neutralino-win_x64.exe')
    writeFileSync(binary, '')
    chmodSync(binary, 0o755)
    expect(findNeutralinoBinary({ appDir, env: {} })).toBe(binary)
  })

  it('is null when nothing is found (no env override, no binary placed yet)', () => {
    expect(findNeutralinoBinary({ appDir, env: {} })).toBeNull()
  })
})

describe('buildShellCommand', () => {
  it("points the binary at the loopback page and this app's own resources (D159 option 2)", () => {
    const command = buildShellCommand('C:\\opt\\neutralino-win_x64.exe', {
      url: 'http://127.0.0.1:54321',
      appDir: 'C:\\repo\\clients\\windows\\apps\\composes',
    })
    expect(command).toEqual([
      'C:\\opt\\neutralino-win_x64.exe',
      '--path=C:\\repo\\clients\\windows\\apps\\composes',
      '--url=http://127.0.0.1:54321',
      '--enable-server=true',
    ])
  })
})

describe('the entry-point guard\'s URL comparison (why `main()` was never reached on Windows)', () => {
  it('a naive `file://${path}` template on a Windows-shaped argv[1] can never equal the well-formed URL import.meta.url actually is', () => {
    const windowsArgv1 = 'C:\\Users\\dev\\claudia\\clients\\windows\\dist\\launch.js'
    const naiveTemplate = `file://${windowsArgv1}`
    expect(naiveTemplate).not.toBe(pathToFileURL(windowsArgv1).href)
    expect(new URL(pathToFileURL(windowsArgv1).href).protocol).toBe('file:')
  })

  it('pathToFileURL(argv[1]).href is stable under its own round trip, on a POSIX-shaped path too', () => {
    const posixArgv1 = '/home/dev/claudia/clients/windows/dist/launch.js'
    const url = pathToFileURL(posixArgv1)
    expect(url.href).toBe(pathToFileURL(posixArgv1).href)
    expect(url.protocol).toBe('file:')
  })
})
