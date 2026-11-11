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
  let home: string

  beforeEach(() => {
    repo = mkdtempSync(join(tmpdir(), 'claudia-repo-'));
    home = mkdtempSync(join(tmpdir(), 'claudia-home-'));
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

  it('builds a server for the app on a free loopback port, not started yet', async () => {
    const server = await prepareServer('creates', { repo, home, env: {} })
    expect(server.url.startsWith('http://127.0.0.1:')).toBe(true)
    expect(server.running).toBe(false)
  })

  it('points the server at state/server.log, so a start-up failure is not silent', async () => {
    const server = await prepareServer('creates', { repo, home, env: {} })
    expect(server.logPath).toBe(
      join(home, 'Library', 'Application Support', 'Claudia', 'creates', 'state', 'server.log'),
    )
  })

  it('the documents and state folders exist once prepared', async () => {
    await prepareServer('creates', { repo, home, env: {} })
    expect(() => mkdirSync(join(home, 'Library', 'Application Support', 'Claudia', 'creates', 'documents'))).toThrow() // already exists
    expect(() => mkdirSync(join(home, 'Library', 'Application Support', 'Claudia', 'creates', 'state'))).toThrow()
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
