// Mirrors clients/linux/tests/test_launch.py's own scope: prepare_server() is tested (a free loopback port, the
// right command, the documents folder created, missing-python/missing-frontend explained with the fix), the real
// main loop is not -- there the GTK Application.run() loop is the untested wiring, here it is the part of main()
// that actually spawns the compiled Neutralino binary and waits on it (needs a real binary on a real Mac, not a
// sandbox; see this package's README). findNeutralinoBinary/neutralinoBinaryName/buildShellCommand are the
// macOS-only pieces Linux has no equivalent of (GTK *is* the shell process; macOS's shell is a separate compiled
// binary this launcher must find and start), so they get their own coverage here.
import { chmodSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
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

describe('neutralinoBinaryName', () => {
  it('names the binary the spike settled on for each known mac architecture', () => {
    expect(neutralinoBinaryName('arm64')).toBe('neutralino-mac_arm64')
    expect(neutralinoBinaryName('x64')).toBe('neutralino-mac_x64')
  })

  it('refuses an architecture Neutralino does not publish a mac binary for', () => {
    expect(() => neutralinoBinaryName('ia32')).toThrow(SetupProblem)
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
    expect(findNeutralinoBinary({ appDir, env: { CLAUDIA_NEUTRALINO_BIN: '/opt/neutralino-mac_arm64' } })).toBe(
      '/opt/neutralino-mac_arm64',
    )
  })

  it('falls back to <appDir>/neutralino-mac_<arch> when it exists and is executable', () => {
    const binary = join(appDir, 'neutralino-mac_arm64')
    writeFileSync(binary, '#!/bin/sh\n')
    chmodSync(binary, 0o755)
    expect(findNeutralinoBinary({ appDir, env: {}, arch: 'arm64' })).toBe(binary)
  })

  it('is null when nothing is found (no env override, no binary placed yet)', () => {
    expect(findNeutralinoBinary({ appDir, env: {}, arch: 'arm64' })).toBeNull()
  })
})

describe('buildShellCommand', () => {
  it('points the binary at the loopback page and this app\'s own resources (D159 option 2)', () => {
    const command = buildShellCommand('/opt/neutralino-mac_arm64', {
      url: 'http://127.0.0.1:54321',
      appDir: '/repo/clients/macos/apps/creates',
    })
    expect(command).toEqual([
      '/opt/neutralino-mac_arm64',
      '--path=/repo/clients/macos/apps/creates',
      '--url=http://127.0.0.1:54321',
      '--enable-server=true',
    ])
  })
})
