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
  let home: string

  beforeEach(() => {
    repo = mkdtempSync(join(tmpdir(), 'claudia-repo-'))
    home = mkdtempSync(join(tmpdir(), 'claudia-home-'))
    const python = join(repo, '.venv', 'bin', 'python')
    mkdirSync(join(repo, '.venv', 'bin'), { recursive: true })
    writeFileSync(python, '#!/bin/sh\n')
    chmodSync(python, 0o755)
    const web = join(repo, 'web', '.output', 'public')
    mkdirSync(web, { recursive: true })
    writeFileSync(join(web, 'index.html'), '<html></html>')
  })

  afterEach(() => {
    rmSync(repo, { recursive: true, force: true })
    rmSync(home, { recursive: true, force: true })
  })

  it('hands over the local server of the suite, not started yet', async () => {
    const server = await prepareServer('creates', { repo, home, env: {} })
    expect(server).toBeInstanceOf(DesktopServer)
    expect(server.url).toBeNull()
  })

  it('points the server at state/server.log of the suite, so a start-up failure is not silent', async () => {
    const server = await prepareServer('creates', { repo, home, env: {} })
    expect(server.logPath).toBe(join(home, 'Library', 'Application Support', 'Claudia', 'state', 'server.log'))
  })

  it('the one folder of documents and the one of state exist once prepared, whichever app asks', async () => {
    for (const app of ['composes', 'computes', 'creates']) await prepareServer(app, { repo, home, env: {} })
    expect(existsSync(join(home, 'Library', 'Application Support', 'Claudia', 'documents'))).toBe(true)
    expect(existsSync(join(home, 'Library', 'Application Support', 'Claudia', 'state'))).toBe(true)
    expect(existsSync(join(home, 'Library', 'Application Support', 'Claudia', 'creates', 'documents'))).toBe(false) // no folder per app any more
  })

  it('a missing server python is explained with the way to fix it', async () => {
    rmSync(join(repo, '.venv', 'bin', 'python'))
    await expect(prepareServer('creates', { repo, home, env: {} })).rejects.toThrow(SetupProblem)
    await expect(prepareServer('creates', { repo, home, env: {} })).rejects.toThrow(/CLAUDIA_SERVER_PYTHON/)
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
