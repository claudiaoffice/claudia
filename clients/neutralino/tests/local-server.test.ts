// prepareServer() is tested the way clients/linux/tests/test_launch.py tests prepare_server(): the right folders made,
// missing-python/missing-frontend explained with the fix. It hands over the person's private server (private-server.ts,
// E8.5), not started yet; which port, which command and what happens when two windows start at once are tested in
// private-server.test.ts, and the real process start in server.test.ts.
import { chmodSync, existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir, userInfo } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { PrivateServer } from '../src/private-server.js'
import { privatePort } from '../src/private-port.js'
import { SetupProblem, prepareServer as prepare } from '../src/local-server.js'
import { hostPlatform } from '../src/platform/host.js'

// Each platform keeps the suite's files in its own folder and finds the server's Python where `uv sync` puts it there.
const PLATFORMS = [
  { platform: hostPlatform('macos'), folder: ['Library', 'Application Support', 'Claudia'], python: ['.venv', 'bin', 'python'] },
  { platform: hostPlatform('windows'), folder: ['AppData', 'Local', 'Claudia'], python: ['.venv', 'Scripts', 'python.exe'] },
]

describe.each(PLATFORMS)('prepareServer on $platform.id', ({ platform, folder, python: pythonParts }) => {
  let repo: string
  let home: string
  const suite = (...rest: string[]) => join(home, ...folder, ...rest)
  const prepareServer = (app: string, options: Parameters<typeof prepare>[1] = {}) => prepare(app, { platform, ...options })

  beforeEach(() => {
    repo = mkdtempSync(join(tmpdir(), 'claudia-repo-'))
    home = mkdtempSync(join(tmpdir(), 'claudia-home-'))
    const python = join(repo, ...pythonParts)
    mkdirSync(join(repo, ...pythonParts.slice(0, -1)), { recursive: true })
    writeFileSync(python, '#!/bin/sh\n')
    chmodSync(python, 0o755) // X_OK on a test host; a real Windows .venv needs no execute bit at all
    const web = join(repo, 'web', '.output', 'public')
    mkdirSync(web, { recursive: true })
    writeFileSync(join(web, 'index.html'), '<html></html>')
  })

  afterEach(() => {
    rmSync(repo, { recursive: true, force: true })
    rmSync(home, { recursive: true, force: true })
  })

  it('hands over her private server, not started yet', async () => {
    const server = await prepareServer('creates', { repo, home, env: {} })
    expect(server).toBeInstanceOf(PrivateServer)
    expect(server.url).toBeNull()
  })

  it('points the server at state/server.log of the suite, so a start-up failure is not silent', async () => {
    const server = await prepareServer('creates', { repo, home, env: {} })
    expect(server.logPath).toBe(suite('state', 'server.log'))
  })

  it('the one folder of documents and the one of state exist once prepared, whichever app asks', async () => {
    for (const app of ['composes', 'computes', 'creates']) await prepareServer(app, { repo, home, env: {} })
    expect(existsSync(suite('documents'))).toBe(true)
    expect(existsSync(suite('state'))).toBe(true)
    expect(existsSync(suite('creates', 'documents'))).toBe(false) // no folder per app any more
  })

  it('her server is on the port of her account (E8.5, D1621), or on the port of CLAUDIA_SERVER_PORT', async () => {
    const usual = await prepareServer('creates', { repo, home, env: {} })
    const { account, port } = (usual as unknown as { options: { account: Parameters<typeof privatePort>[0]; port?: number } }).options
    expect(account).toEqual(platform.id === 'windows' ? { profileFolder: home } : { uid: userInfo().uid })
    expect(port).toBeUndefined() // the port of her account
    const other = await prepareServer('creates', { repo, home, env: { CLAUDIA_SERVER_PORT: '18765' } })
    expect((other as unknown as { options: { port?: number } }).options.port).toBe(18765)
    const nonsense = await prepareServer('creates', { repo, home, env: { CLAUDIA_SERVER_PORT: 'x' } })
    expect((nonsense as unknown as { options: { port?: number } }).options.port).toBeUndefined()
  })

  it('a missing server python is explained with the way to fix it', async () => {
    rmSync(join(repo, ...pythonParts))
    await expect(prepareServer('creates', { repo, home, env: {} })).rejects.toThrow(SetupProblem)
    await expect(prepareServer('creates', { repo, home, env: {} })).rejects.toThrow(/CLAUDIA_SERVER_PYTHON/)
    // the hint names where `uv sync` puts the interpreter on this platform
    await expect(prepareServer('creates', { repo, home, env: {} })).rejects.toThrow(pythonParts.at(-1) as string)
  })

  it('the self-contained server of the installer needs no Python (D740)', async () => {
    rmSync(join(repo, ...pythonParts))
    const server = await prepareServer('creates', { repo, home, env: { CLAUDIA_SERVER_EXE: '/opt/claudia/server/claudia-server' } })
    expect((server as unknown as { options: { program: unknown } }).options.program).toEqual({ exe: '/opt/claudia/server/claudia-server' })
  })

  it('a missing frontend is explained with the way to fix it', async () => {
    rmSync(join(repo, 'web', '.output', 'public', 'index.html'))
    await expect(prepareServer('creates', { repo, home, env: {} })).rejects.toThrow(SetupProblem)
    await expect(prepareServer('creates', { repo, home, env: {} })).rejects.toThrow(/CLAUDIA_WEB_DIR/)
  })

  it('a wrong explicit frontend path is reported, not silently replaced', async () => {
    await expect(
      prepareServer('creates', { repo, home, env: { CLAUDIA_WEB_DIR: '/nonexistent/frontend' } }),
    ).rejects.toThrow(/\/nonexistent\/frontend/)
  })
})
