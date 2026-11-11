// The launcher: which files it insists on, the environment it hands to the window (the core reads it), the command
// that starts Neutralino, and the whole program with a fake process in place of the real binary. The real Neutralino
// window can only be run on a Windows machine (see this package's README).
//
// The tests run on any host (CI is Linux): paths are built with `join` on both sides, and the Windows-only
// questions -- the 8.3 short name, the spelling of `Path` -- are handed in or checked as plain data.
import { EventEmitter } from 'node:events'
import { chmodSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { delimiter, dirname, join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { DEFAULT_COMMAND } from '../src/core-command.js'
import {
  SetupProblem,
  buildShellCommand,
  buildShellEnvironment,
  commandSafePath,
  environmentWith,
  findNeutralinoBinary,
  main,
  missingFiles,
  neutralinoBinaryName,
  run,
  shortPathOf,
  type RunDeps,
} from '../src/launch.js'
import { parseAddress } from '../src/servers.js'

describe('neutralinoBinaryName', () => {
  it('is the one Windows binary Neutralino 6.8.0 publishes', () => {
    expect(neutralinoBinaryName()).toBe('neutralino-win_x64.exe')
  })
})

describe('findNeutralinoBinary', () => {
  let appDir: string
  beforeEach(() => {
    appDir = mkdtempSync(join(tmpdir(), 'claudia-app-'))
  })
  afterEach(() => rmSync(appDir, { recursive: true, force: true }))

  it('CLAUDIA_NEUTRALINO_BIN, when set, is returned as-is', () => {
    expect(findNeutralinoBinary({ appDir, env: { CLAUDIA_NEUTRALINO_BIN: 'D:\\tools\\neutralino-win_x64.exe' } })).toBe(
      'D:\\tools\\neutralino-win_x64.exe',
    )
  })

  it('falls back to <appDir>\\bin\\neutralino-win_x64.exe, where `neu update` places it, when it is there', () => {
    mkdirSync(join(appDir, 'bin'))
    const binary = join(appDir, 'bin', 'neutralino-win_x64.exe')
    writeFileSync(binary, '')
    chmodSync(binary, 0o755) // X_OK on a Linux test host; on Windows the file merely has to exist
    expect(findNeutralinoBinary({ appDir, env: {} })).toBe(binary)
  })

  it('is null when nothing is found', () => {
    expect(findNeutralinoBinary({ appDir, env: {} })).toBeNull()
  })
})

describe('missingFiles', () => {
  const all = new Set([join('/a', 'index.html'), join('/a', 'shell', 'shell.js'), join('/a', 'ext', 'core.mjs'), join('/a', 'js', 'neutralino.js')])
  const has = (path: string) => all.has(path)

  it('is null when everything is there', () => {
    expect(missingFiles('/a', has)).toBeNull()
  })

  it('says to build when a generated file is missing, in the Windows client folder', () => {
    const message = missingFiles('/a', (p) => p !== join('/a', 'ext', 'core.mjs') && has(p))
    expect(message).toContain(join('ext', 'core.mjs'))
    expect(message).toContain('npm run build')
    expect(message).toContain('clients\\windows')
  })

  it("says to run `neu update` when Neutralino's client library is missing", () => {
    const message = missingFiles('/a', (p) => p !== join('/a', 'js', 'neutralino.js') && has(p))
    expect(message).toContain('neu update')
  })
})

describe('environmentWith', () => {
  it('replaces a variable whatever its spelling, so the child never sees two', () => {
    const environment: Record<string, string> = { Path: 'C:\\Windows', USERPROFILE: 'x' }
    environmentWith(environment, 'PATH', 'C:\\node;C:\\Windows')
    expect(Object.keys(environment).filter((k) => k.toUpperCase() === 'PATH')).toEqual(['PATH'])
    expect(environment.PATH).toBe('C:\\node;C:\\Windows')
    expect(environment.USERPROFILE).toBe('x')
  })

  it('removes a variable with null, again in any spelling', () => {
    const environment: Record<string, string> = { Claudia_Shell_Server: 'https://stale.example' }
    environmentWith(environment, 'CLAUDIA_SHELL_SERVER', null)
    expect(Object.keys(environment)).toEqual([])
  })
})

describe('buildShellEnvironment', () => {
  const own = { app: 'creates', server: null, debug: false } as const

  it('names the app, and leaves the server out when there is none (the core starts its own)', () => {
    const environment = buildShellEnvironment(own, { CLAUDIA_SHELL_SERVER: 'https://stale.example' }, 'C:\\n\\node.exe', false)
    expect(environment.CLAUDIA_SHELL_APP).toBe('creates')
    expect('CLAUDIA_SHELL_SERVER' in environment).toBe(false)
  })

  it('hands on the canonical origin of --server', () => {
    const server = parseAddress('Demo.Claudia-Office.de')
    const environment = buildShellEnvironment({ ...own, server }, {}, 'C:\\n\\node.exe', false)
    expect(environment.CLAUDIA_SHELL_SERVER).toBe('https://demo.claudia-office.de')
  })

  it("puts the folder of the running node first on PATH, and leaves no second spelling of the name (`Path`)", () => {
    const node = join('/opt/node', 'node.exe')
    const environment = buildShellEnvironment(own, { Path: 'C:\\Windows\\System32' }, node, false)
    expect(environment.PATH).toBe([dirname(node), 'C:\\Windows\\System32'].join(delimiter))
    expect(Object.keys(environment).filter((k) => k.toUpperCase() === 'PATH')).toEqual(['PATH'])
    expect(buildShellEnvironment(own, {}, node, false).PATH).toBe(dirname(node))
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
    const environment = buildShellEnvironment(own, { USERPROFILE: 'C:\\Users\\me', GONE: undefined }, '/n/node', false)
    expect(environment.USERPROFILE).toBe('C:\\Users\\me')
    expect('GONE' in environment).toBe(false)
  })
})

describe('buildShellCommand', () => {
  it('points the binary at the app folder and nothing else: the page is the one in that folder (D251)', () => {
    expect(buildShellCommand('C:\\n\\neutralino-win_x64.exe', 'C:\\repo\\clients\\windows\\apps\\creates')).toEqual([
      'C:\\n\\neutralino-win_x64.exe',
      '--path=C:\\repo\\clients\\windows\\apps\\creates',
    ])
  })
})

describe('commandSafePath', () => {
  it('leaves a path without whitespace as it is, and does not ask for a short name', () => {
    const asked: string[] = []
    expect(commandSafePath('C:\\nodejs\\node.exe', (p) => (asked.push(p), null))).toBe('C:\\nodejs\\node.exe')
    expect(asked).toEqual([])
  })

  it('uses the short name when the path has a space and the short name has none', () => {
    expect(commandSafePath('C:\\Program Files\\nodejs\\node.exe', () => 'C:\\PROGRA~1\\nodejs\\node.exe')).toBe('C:\\PROGRA~1\\nodejs\\node.exe')
  })

  it('is null when there is no short name, or when it is no better', () => {
    expect(commandSafePath('C:\\Program Files\\nodejs\\node.exe', () => null)).toBeNull()
    expect(commandSafePath('C:\\Program Files\\nodejs\\node.exe', (p) => p)).toBeNull()
  })
})

describe('shortPathOf', () => {
  it('only exists on Windows: anywhere else it is null, without running anything', () => {
    expect(shortPathOf('C:\\Program Files\\nodejs\\node.exe', 'linux')).toBeNull()
    expect(shortPathOf('/Applications/node', 'darwin')).toBeNull()
  })

  it('refuses a path that could change what `cmd` runs (a quote or a percent sign), even on Windows', () => {
    expect(shortPathOf('C:\\a" & calc & "b\\node.exe', 'win32')).toBeNull()
    expect(shortPathOf('C:\\%USERNAME%\\node.exe', 'win32')).toBeNull()
  })
})

/** A stand-in for the Neutralino process. */
class FakeChild extends EventEmitter {
  killed = 0
  kill(): boolean {
    this.killed++
    return true
  }
}

const APPS = join('/repo', 'clients', 'windows', 'apps')

function harness(overrides: Partial<RunDeps> = {}) {
  const spawned: { command: string; args: string[]; options: { env: Record<string, string> } }[] = []
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
    env: { Path: 'C:\\Windows', USERPROFILE: 'C:\\Users\\me' },
    appDir: (app) => join(APPS, app),
    nodeBinary: 'C:\\nodejs\\node.exe',
    supportsSystemCa: true,
    exists: () => true,
    findBinary: () => 'C:\\neutralino-win_x64.exe',
    setCommand: (appDir, command) => void commands.push({ appDir, command }),
    out: (line) => out.push(line),
    err: (line) => err.push(line),
    ...overrides,
  }
  return { deps, spawned, child, out, err, commands }
}

const creates = { app: 'creates', server: null, debug: false } as const

describe('run', () => {
  it('starts the binary with --path and the environment', async () => {
    const { deps, spawned } = harness()
    expect(await run(creates, deps)).toBe(0)
    expect(spawned).toHaveLength(1)
    expect(spawned[0]!.command).toBe('C:\\neutralino-win_x64.exe')
    expect(spawned[0]!.args).toEqual([`--path=${join(APPS, 'creates')}`])
    expect(spawned[0]!.options.env.CLAUDIA_SHELL_APP).toBe('creates')
    expect(spawned[0]!.options.env.NODE_OPTIONS).toBe('--use-system-ca')
  })

  it('puts the core command into the config for the run, with node, app and server in it, and the default back after', async () => {
    const { deps, commands } = harness()
    const server = parseAddress('demo.claudia-office.de')
    await run({ app: 'computes', server, debug: false }, deps)
    expect(commands).toEqual([
      {
        appDir: join(APPS, 'computes'),
        command: 'C:\\nodejs\\node.exe --use-system-ca ${NL_PATH}/ext/core.mjs --app=computes --server=https://demo.claudia-office.de',
      },
      { appDir: join(APPS, 'computes'), command: DEFAULT_COMMAND },
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
    expect(await run(creates, deps)).toBe(1)
    expect(commands.at(-1)!.command).toBe(DEFAULT_COMMAND)
    expect(err.join('\n')).toContain('EACCES')
  })

  it("uses the short name of a node in `Program Files`, which Neutralino's command line could not hold", async () => {
    const { deps, commands } = harness({
      nodeBinary: 'C:\\Program Files\\nodejs\\node.exe',
      shortName: () => 'C:\\PROGRA~1\\nodejs\\node.exe',
    })
    expect(await run(creates, deps)).toBe(0)
    expect(commands[0]!.command).toBe('C:\\PROGRA~1\\nodejs\\node.exe --use-system-ca ${NL_PATH}/ext/core.mjs --app=creates')
  })

  it("falls back to a plain `node` from PATH when node's path has a space and no short name, and says so", async () => {
    const { deps, commands, out } = harness({ nodeBinary: 'C:\\Program Files\\nodejs\\node.exe', shortName: () => null })
    expect(await run(creates, deps)).toBe(0)
    expect(commands[0]!.command).toBe('node --use-system-ca ${NL_PATH}/ext/core.mjs --app=creates')
    expect(out.join('\n')).toContain("plain 'node'")
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
    expect(child.killed).toBe(0)
  })

  it('explains what is missing and does not start anything', async () => {
    const { deps, spawned, err } = harness({ exists: () => false })
    expect(await run(creates, deps)).toBe(1)
    expect(spawned).toEqual([])
    expect(err.join('\n')).toContain('npm run build')
  })

  it('explains a missing Neutralino binary', async () => {
    const { deps, spawned, err } = harness({ findBinary: () => null })
    expect(await run(creates, deps)).toBe(1)
    expect(spawned).toEqual([])
    expect(err.join('\n')).toMatch(/neu update/)
    expect(err.join('\n')).toMatch(/CLAUDIA_NEUTRALINO_BIN/)
    expect(err.join('\n')).toContain('neutralino-win_x64.exe')
  })

  it('refuses a folder with a space in its path, and says why', async () => {
    const { deps, spawned, err } = harness({ appDir: () => 'C:\\Users\\me\\My Projects\\claudia\\apps\\creates' })
    expect(await run(creates, deps)).toBe(1)
    expect(spawned).toEqual([])
    expect(err.join('\n')).toContain('space')
  })

  it('with --debug, says where the logs are', async () => {
    const { deps, out } = harness()
    await run({ ...creates, debug: true }, deps)
    expect(out.join('\n')).toContain('shell.log')
    expect(out.join('\n')).toContain('server.log')
  })
})

describe('main', () => {
  it('starts the app named first, with the server from --server', async () => {
    const { deps, spawned } = harness()
    expect(await main(['computes', '--server', 'https://demo.claudia-office.de'], deps)).toBe(0)
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

// The entry guard made the launcher a silent no-op on Windows (third real run, 2026-11-09): the program runs only
// when `import.meta.url` equals the URL of `process.argv[1]`, and a hand-made `file://` + path is not that URL for a
// Windows path. The comparison itself, in isolation (`main()` has real side effects).
describe('the entry guard', () => {
  it('is not what a hand-made `file://` string gives, for a path with characters that a URL escapes', () => {
    const path = join(tmpdir(), 'a b', 'launch#1.js')
    expect(pathToFileURL(path).href).not.toBe(`file://${path}`)
  })

  it('is a file: URL for a Windows drive path (the scheme is not read as `c:`)', () => {
    const url = new URL(pathToFileURL('C:\\Users\\dev\\dist\\launch.js', { windows: true }).href)
    expect(url.protocol).toBe('file:')
    expect(url.pathname).toBe('/C:/Users/dev/dist/launch.js')
  })
})

describe('SetupProblem', () => {
  it('is re-exported, so that a caller needs one import for the launcher', () => {
    expect(new SetupProblem('x')).toBeInstanceOf(Error)
  })
})
