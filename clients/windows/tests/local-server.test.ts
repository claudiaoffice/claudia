// prepareServer() is tested the way clients/linux/tests/test_launch.py tests prepare_server(): a free loopback
// port, the right command, the documents folder created, missing-python/missing-frontend explained with the fix.
// (The real process start is in server.test.ts.)
import { chmodSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { SetupProblem, prepareServer } from '../src/local-server.js'

describe('prepareServer', () => {
  let repo: string
  let localAppData: string

  beforeEach(() => {
    repo = mkdtempSync(join(tmpdir(), 'claudia-repo-'))
    localAppData = mkdtempSync(join(tmpdir(), 'claudia-localappdata-'));
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
    const server = await prepareServer('creates', { repo, localAppData, env: {} })
    expect(server.url.startsWith('http://127.0.0.1:')).toBe(true)
    expect(server.running).toBe(false)
  })

  it('points the server at state/server.log, so a start-up failure is not silent', async () => {
    const server = await prepareServer('creates', { repo, localAppData, env: {} })
    expect(server.logPath).toBe(
      join(localAppData, 'Claudia', 'creates', 'state', 'server.log'),
    )
  })

  it('the documents and state folders exist once prepared', async () => {
    await prepareServer('creates', { repo, localAppData, env: {} })
    expect(() => mkdirSync(join(localAppData, 'Claudia', 'creates', 'documents'))).toThrow() // already exists
    expect(() => mkdirSync(join(localAppData, 'Claudia', 'creates', 'state'))).toThrow()
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
