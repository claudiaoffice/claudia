// The launcher: which files it insists on, the environment it hands to the window (the core reads it), the command
// that starts Neutralino, and the whole program with a fake process in place of the real binary. The real Neutralino
// window can only be run on a Mac (see this package's README).
import { EventEmitter } from 'node:events'
import { chmodSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { delimiter, join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { DEFAULT_COMMAND } from '../src/core-command.js'
import { getIdentity } from '../src/identity.js'
import {
  SetupProblem,
  buildShellCommand,
  buildShellEnvironment,
  findNeutralinoBinary,
  macProcessName,
  main,
  missingFiles,
  neutralinoBinaryName,
  run,
  type RunDeps,
} from '../src/launch.js'
import { parseAddress } from '../src/servers.js'

describe('neutralinoBinaryName', () => {
  it('names the binary for each known mac architecture', () => {
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
  afterEach(() => rmSync(appDir, { recursive: true, force: true }))

  it('CLAUDIA_NEUTRALINO_BIN, when set, is returned as-is', () => {
    expect(findNeutralinoBinary({ appDir, env: { CLAUDIA_NEUTRALINO_BIN: '/opt/neutralino-mac_arm64' } })).toBe('/opt/neutralino-mac_arm64')
  })

  it('falls back to <appDir>/bin/neutralino-mac_<arch>, where `neu update` places it, when it is executable', () => {
    mkdirSync(join(appDir, 'bin'))
    const binary = join(appDir, 'bin', 'neutralino-mac_arm64')
    writeFileSync(binary, '#!/bin/sh\n')
    chmodSync(binary, 0o755)
    expect(findNeutralinoBinary({ appDir, env: {}, arch: 'arm64' })).toBe(binary)
  })

  it('is null when nothing is found', () => {
    expect(findNeutralinoBinary({ appDir, env: {}, arch: 'arm64' })).toBeNull()
  })
})

describe('macProcessName', () => {
  it("is 'claudia <app>', lower case: macOS shows it as the application's name", () => {
    expect(macProcessName(getIdentity('creates'))).toBe('claudia creates')
    expect(macProcessName(getIdentity('computes'))).toBe('claudia computes')
  })

  it('is scoped to this one process-identity string; the title stays Title Case (shared with Linux and the web app)', () => {
    const identity = getIdentity('creates')
    expect(macProcessName(identity)).not.toBe(identity.title)
  })
})

describe('missingFiles', () => {
  const all = new Set(['/a/index.html', '/a/shell/shell.js', '/a/ext/core.mjs', '/a/js/neutralino.js'])
  const has = (path: string) => all.has(path)

  it('is null when everything is there', () => {
    expect(missingFiles('/a', has)).toBeNull()
  })

  it('says to build when a generated file is missing', () => {
    const message = missingFiles('/a', (p) => p !== '/a/ext/core.mjs' && has(p))
    expect(message).toContain('ext/core.mjs')
    expect(message).toContain('npm run build')
  })

  it("says to run `neu update` when Neutralino's client library is missing", () => {
    const message = missingFiles('/a', (p) => p !== '/a/js/neutralino.js' && has(p))
    expect(message).toContain('neu update')
  })
})

describe('buildShellEnvironment', () => {
  const own = { app: 'creates', server: null, debug: false } as const

  it('names the app, and leaves the server out when there is none (the core starts its own)', () => {
    const environment = buildShellEnvironment(own, { CLAUDIA_SHELL_SERVER: 'https://stale.example' }, '/n/bin/node', false)
    expect(environment.CLAUDIA_SHELL_APP).toBe('creates')
    expect('CLAUDIA_SHELL_SERVER' in environment).toBe(false)
  })

  it('hands on the canonical origin of --server', () => {
    const server = parseAddress('Demo.Claudia-Office.de')
    const environment = buildShellEnvironment({ ...own, server }, {}, '/n/bin/node', false)
    expect(environment.CLAUDIA_SHELL_SERVER).toBe('https://demo.claudia-office.de')
  })

  it('puts the folder of the running node first on PATH, so the extension finds it', () => {
    const environment = buildShellEnvironment(own, { PATH: '/usr/bin' }, '/opt/node/bin/node', false)
    expect(environment.PATH).toBe(['/opt/node/bin', '/usr/bin'].join(delimiter))
    expect(buildShellEnvironment(own, {}, '/opt/node/bin/node', false).PATH).toBe('/opt/node/bin')
  })

  it('asks Node to use the system certificates only when this Node knows the flag, and only once', () => {
    expect(buildShellEnvironment(own, {}, '/n/node', true).NODE_OPTIONS).toBe('--use-system-ca')
    expect(buildShellEnvironment(own, {}, '/n/node', false).NODE_OPTIONS).toBeUndefined()
    expect(buildShellEnvironment(own, { NODE_OPTIONS: '--max-old-space-size=512' }, '/n/node', true).NODE_OPTIONS).toBe(
      '--max-old-space-size=512 --use-system-ca',
    )
    expect(buildShellEnvironment(own, { NODE_OPTIONS: '--use-system-ca' }, '/n/node', true).NODE_OPTIONS).toBe('--use-system-ca')
  })

  it('marks debug', () => {
    expect(buildShellEnvironment({ ...own, debug: true }, {}, '/n/node', false).CLAUDIA_SHELL_DEBUG).toBe('1')
    expect(buildShellEnvironment(own, {}, '/n/node', false).CLAUDIA_SHELL_DEBUG).toBeUndefined()
  })

  it('leaves the rest of the environment alone, and drops undefined values', () => {
    const environment = buildShellEnvironment(own, { HOME: '/Users/me', GONE: undefined }, '/n/node', false)
    expect(environment.HOME).toBe('/Users/me')
    expect('GONE' in environment).toBe(false)
  })
})

describe('buildShellCommand', () => {
  it('points the binary at the app folder and nothing else: the page is the one in that folder (D251)', () => {
    expect(buildShellCommand('/opt/neutralino-mac_arm64', '/repo/clients/macos/apps/creates')).toEqual([
      '/opt/neutralino-mac_arm64',
      '--path=/repo/clients/macos/apps/creates',
    ])
  })
})

/** A stand-in for the Neutralino process. */
class FakeChild extends EventEmitter {
  killed: string[] = []
  kill(signal: string): boolean {
    this.killed.push(signal)
    return true
  }
}

function harness(overrides: Partial<RunDeps> = {}) {
  const spawned: { command: string; args: string[]; options: { env: Record<string, string>; argv0: string } }[] = []
  const child = new FakeChild()
  const out: string[] = []
  const err: string[] = []
  const commands: { appDir: string; command: string }[] = []
  const deps: RunDeps = {
    spawn: ((command: string, args: string[], options: never) => {
      spawned.push({ command, args, options })
      queueMicrotask(() => child.emit('exit', 0))
      return child
    }) as never,
    env: { PATH: '/usr/bin', HOME: '/Users/me' },
    appDir: (app) => `/repo/clients/macos/apps/${app}`,
    nodeBinary: '/opt/node/bin/node',
    supportsSystemCa: true,
    exists: () => true,
    findBinary: () => '/repo/clients/macos/apps/creates/bin/neutralino-mac_arm64',
    makeBundle: () => '/bundle/Contents/MacOS/claudia-creates',
    setCommand: (appDir, command) => void commands.push({ appDir, command }),
    out: (line) => out.push(line),
    err: (line) => err.push(line),
    ...overrides,
  }
  return { deps, spawned, child, out, err, commands }
}

describe('run', () => {
  it('starts the bundled binary with --path and the environment, named like the app', async () => {
    const { deps, spawned } = harness()
    const code = await run({ app: 'creates', server: null, debug: false }, deps)
    expect(code).toBe(0)
    expect(spawned).toHaveLength(1)
    expect(spawned[0]!.command).toBe('/bundle/Contents/MacOS/claudia-creates')
    expect(spawned[0]!.args).toEqual(['--path=/repo/clients/macos/apps/creates'])
    expect(spawned[0]!.options.argv0).toBe('claudia creates')
    expect(spawned[0]!.options.env.CLAUDIA_SHELL_APP).toBe('creates')
    expect(spawned[0]!.options.env.NODE_OPTIONS).toBe('--use-system-ca')
  })

  it('puts the core command into the config for the run, with node, app and server in it, and the default back after', async () => {
    const { deps, commands } = harness()
    const server = parseAddress('demo.claudia-office.de')
    await run({ app: 'computes', server, debug: false }, deps)
    expect(commands).toEqual([
      {
        appDir: '/repo/clients/macos/apps/computes',
        command: '/opt/node/bin/node --use-system-ca ${NL_PATH}/ext/core.mjs --app=computes --server=https://demo.claudia-office.de',
      },
      { appDir: '/repo/clients/macos/apps/computes', command: DEFAULT_COMMAND },
    ])
  })

  it('puts the default back also when the window cannot be started', async () => {
    const { deps, commands, err } = harness({
      spawn: (() => {
        const c = new FakeChild()
        queueMicrotask(() => c.emit('error', new Error('EACCES')))
        return c
      }) as never,
    })
    expect(await run({ app: 'creates', server: null, debug: false }, deps)).toBe(1)
    expect(commands.at(-1)!.command).toBe(DEFAULT_COMMAND)
    expect(err.join('\n')).toContain('EACCES')
  })

  it('reports a command that cannot be made (node in a path with a space), and starts nothing', async () => {
    const { deps, spawned, err } = harness({ nodeBinary: '/Users/me/My Tools/node' })
    expect(await run({ app: 'creates', server: null, debug: false }, deps)).toBe(1)
    expect(spawned).toEqual([])
    expect(err.join('\n')).toContain('space')
  })

  it('passes the exit code of the window on', async () => {
    const { deps, child } = harness({
      spawn: (() => {
        const c = new FakeChild()
        queueMicrotask(() => c.emit('exit', 3))
        return c
      }) as never,
    })
    expect(await run({ app: 'computes', server: null, debug: false }, deps)).toBe(3)
    expect(child.killed).toEqual([])
  })

  it('explains what is missing and does not start anything', async () => {
    const { deps, spawned, err } = harness({ exists: () => false })
    expect(await run({ app: 'creates', server: null, debug: false }, deps)).toBe(1)
    expect(spawned).toEqual([])
    expect(err.join('\n')).toContain('npm run build')
  })

  it('explains a missing Neutralino binary', async () => {
    const { deps, spawned, err } = harness({ findBinary: () => null })
    expect(await run({ app: 'creates', server: null, debug: false }, deps)).toBe(1)
    expect(spawned).toEqual([])
    expect(err.join('\n')).toMatch(/neu update/)
    expect(err.join('\n')).toMatch(/CLAUDIA_NEUTRALINO_BIN/)
  })

  it('refuses a folder with a space in its path, and says why', async () => {
    const { deps, spawned, err } = harness({ appDir: () => '/Users/me/My Projects/claudia/apps/creates' })
    expect(await run({ app: 'creates', server: null, debug: false }, deps)).toBe(1)
    expect(spawned).toEqual([])
    expect(err.join('\n')).toContain('space')
  })

  it('reports a bundle that cannot be made', async () => {
    const { deps, err } = harness({
      makeBundle: () => {
        throw new Error('disk full')
      },
    })
    expect(await run({ app: 'creates', server: null, debug: false }, deps)).toBe(1)
    expect(err.join('\n')).toContain('disk full')
  })

  it('reports a binary that cannot be started', async () => {
    const { deps, err } = harness({
      spawn: (() => {
        const c = new FakeChild()
        queueMicrotask(() => c.emit('error', new Error('EACCES')))
        return c
      }) as never,
    })
    expect(await run({ app: 'creates', server: null, debug: false }, deps)).toBe(1)
    expect(err.join('\n')).toContain('EACCES')
  })

  it('with --debug, says where the logs are', async () => {
    const { deps, out } = harness()
    await run({ app: 'creates', server: null, debug: true }, deps)
    expect(out.join('\n')).toContain('shell.log')
    expect(out.join('\n')).toContain('server.log')
  })
})

describe('main', () => {
  it('starts the app named first, with the server from --server', async () => {
    const { deps, spawned } = harness()
    const code = await main(['computes', '--server', 'https://demo.claudia-office.de'], deps)
    expect(code).toBe(0)
    expect(spawned[0]!.options.env.CLAUDIA_SHELL_APP).toBe('computes')
    expect(spawned[0]!.options.env.CLAUDIA_SHELL_SERVER).toBe('https://demo.claudia-office.de')
  })

  it('starts the same way without --server', async () => {
    const { deps, spawned } = harness()
    expect(await main(['composes'], deps)).toBe(0)
    expect('CLAUDIA_SHELL_SERVER' in spawned[0]!.options.env).toBe(false)
  })

  it('exits 2 with a message for no app, an unknown app, an unknown option, and a bad address', async () => {
    for (const argv of [[], ['--debug'], ['spreadsheets'], ['creates', '--nope'], ['creates', '--server', 'http://example.com']]) {
      const { deps, spawned, err } = harness()
      expect(await main(argv, deps)).toBe(2)
      expect(spawned).toEqual([])
      expect(err.join('\n')).toContain('error')
    }
  })

  it('prints help and version and exits 0 without starting anything', async () => {
    const { deps, spawned, out } = harness()
    expect(await main(['creates', '--help'], deps)).toBe(0)
    expect(await main(['creates', '--version'], deps)).toBe(0)
    expect(spawned).toEqual([])
    expect(out[0]).toContain('usage: claudia-creates')
    expect(out[1]).toMatch(/^claudia-creates \d/)
  })
})
