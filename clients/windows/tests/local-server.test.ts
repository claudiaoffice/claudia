// prepareServer() is tested the way clients/linux/tests/test_launch.py tests prepare_server(): the right folders made,
// missing-python/missing-frontend explained with the fix. Since D445 it hands over the one local server of the suite
// (desktop-server.ts), not started yet; which port, which command and what happens when two windows start at once are
// tested in desktop-server.test.ts, and the real process start in server.test.ts.
import { chmodSync, existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { DesktopServer } from '../src/desktop-server.js'
import { SetupProblem, prepareServer } from '../src/local-server.js'

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

  it('hands over the local server of the suite, not started yet', async () => {
    const server = await prepareServer('creates', { repo, localAppData, env: {} })
    expect(server).toBeInstanceOf(DesktopServer)
    expect(server.url).toBeNull()
  })

  it('points the server at state/server.log of the suite, so a start-up failure is not silent', async () => {
    const server = await prepareServer('creates', { repo, localAppData, env: {} })
    expect(server.logPath).toBe(join(localAppData, 'Claudia', 'state', 'server.log'))
  })

  it('the one folder of documents and the one of state exist once prepared, whichever app asks', async () => {
    for (const app of ['composes', 'computes', 'creates']) await prepareServer(app, { repo, localAppData, env: {} })
    expect(existsSync(join(localAppData, 'Claudia', 'documents'))).toBe(true)
    expect(existsSync(join(localAppData, 'Claudia', 'state'))).toBe(true)
    expect(existsSync(join(localAppData, 'Claudia', 'creates', 'documents'))).toBe(false) // no folder per app any more
  })

  it('uses 8765 (D504), or the port of CLAUDIA_SERVER_PORT', async () => {
    const usual = await prepareServer('creates', { repo, localAppData, env: {} })
    expect((usual as unknown as { options: { port?: number } }).options.port).toBeUndefined() // SERVER_PORT, 8765
    const other = await prepareServer('creates', { repo, localAppData, env: { CLAUDIA_SERVER_PORT: '18765' } })
    expect((other as unknown as { options: { port?: number } }).options.port).toBe(18765)
    const nonsense = await prepareServer('creates', { repo, localAppData, env: { CLAUDIA_SERVER_PORT: 'x' } })
    expect((nonsense as unknown as { options: { port?: number } }).options.port).toBeUndefined()
  })

  it('a missing server python is explained with the way to fix it', async () => {
    rmSync(join(repo, '.venv', 'Scripts', 'python.exe'))
    await expect(prepareServer('creates', { repo, localAppData, env: {} })).rejects.toThrow(SetupProblem)
    await expect(prepareServer('creates', { repo, localAppData, env: {} })).rejects.toThrow(/CLAUDIA_SERVER_PYTHON/)
  })

  it('a missing frontend is explained with the way to fix it', async () => {
    rmSync(join(repo, 'web', '.output', 'public', 'index.html'))
    await expect(prepareServer('creates', { repo, localAppData, env: {} })).rejects.toThrow(SetupProblem)
    await expect(prepareServer('creates', { repo, localAppData, env: {} })).rejects.toThrow(/CLAUDIA_WEB_DIR/)
  })

  it('a wrong explicit frontend path is reported, not silently replaced', async () => {
    await expect(
      prepareServer('creates', { repo, localAppData, env: { CLAUDIA_WEB_DIR: '/nonexistent/frontend' } }),
    ).rejects.toThrow(/\/nonexistent\/frontend/)
  })
})
