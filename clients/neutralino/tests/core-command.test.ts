import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it } from 'vitest'
import { buildCoreCommand, DEFAULT_COMMAND, parseCoreArgs, setCoreCommand, setInspector, setLogicalPixels } from '../src/core-command.js'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const base = { nodeBinary: '/opt/homebrew/bin/node', systemCa: true, app: 'computes', server: null, debug: false } as const

describe('buildCoreCommand', () => {
  it('is the shape that spike 5 proved: the absolute node, then the core', () => {
    expect(buildCoreCommand({ ...base, systemCa: false })).toBe('/opt/homebrew/bin/node ${NL_PATH}/ext/core.mjs --app=computes')
  })

  it('carries the certificate option, the server and debug', () => {
    expect(buildCoreCommand({ ...base, server: 'https://demo.claudia-office.de', debug: true })).toBe(
      '/opt/homebrew/bin/node --use-system-ca ${NL_PATH}/ext/core.mjs --app=computes --server=https://demo.claudia-office.de --debug',
    )
  })

  it('refuses a part with a space, which Neutralino could not pass on', () => {
    expect(() => buildCoreCommand({ ...base, nodeBinary: '/Users/me/My Tools/node' })).toThrow(/space/)
    expect(() => buildCoreCommand({ ...base, nodeBinary: 'C:\\Program Files\\nodejs\\node.exe' })).toThrow(/space/)
  })
})

describe('parseCoreArgs', () => {
  it('reads back what buildCoreCommand put on the command line', () => {
    const command = buildCoreCommand({ ...base, server: 'http://127.0.0.1:8080', debug: true })
    const args = command.split(' ').slice(command.split(' ').indexOf('${NL_PATH}/ext/core.mjs') + 1)
    expect(parseCoreArgs(args)).toEqual({ app: 'computes', server: 'http://127.0.0.1:8080', debug: true })
  })

  it('knows nothing when it is given nothing, and ignores what it does not know', () => {
    expect(parseCoreArgs([])).toEqual({ app: null, server: null, debug: false })
    expect(parseCoreArgs(['--other', '--app=', '--server='])).toEqual({ app: null, server: null, debug: false })
  })
})

describe('setCoreCommand', () => {
  let dir = ''
  afterEach(() => rmSync(dir, { recursive: true, force: true }))

  it.each([
    ['composes', 'commandDarwin'],
    ['computes', 'commandDarwin'],
    ['creates', 'commandDarwin'],
    ['composes', 'commandWindows'],
    ['computes', 'commandWindows'],
    ['creates', 'commandWindows'],
  ] as const)('%s, %s: changes that command and nothing else, and the default restores the file byte for byte', (app, key) => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-config-'))
    const original = join(root, 'apps', app, 'neutralino.config.json')
    const copy = join(dir, 'neutralino.config.json')
    copyFileSync(original, copy)
    setCoreCommand(copy, buildCoreCommand({ ...base, app }), key)
    const changed = JSON.parse(readFileSync(copy, 'utf8'))
    const before = JSON.parse(readFileSync(original, 'utf8'))
    expect(changed.extensions[0][key]).toContain(`--app=${app}`)
    const other = key === 'commandDarwin' ? 'commandWindows' : 'commandDarwin'
    expect(changed.extensions[0][other]).toBe(before.extensions[0][other])
    expect({ ...changed, extensions: null }).toEqual({ ...before, extensions: null })
    setCoreCommand(copy, DEFAULT_COMMAND, key)
    expect(readFileSync(copy, 'utf8')).toBe(readFileSync(original, 'utf8'))
  })

  it.each(['\n', '\r\n'])('keeps the line ends of the file (%j), as a checkout on Windows may have CRLF', (eol) => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-config-'))
    const file = join(dir, 'neutralino.config.json')
    const config = { modes: { window: { enableInspector: false } }, extensions: [{ id: 'de.claudiaoffice.core', commandDarwin: 'x' }] }
    const original = JSON.stringify(config, null, 2).replace(/\n/g, eol) + eol
    writeFileSync(file, original)
    setCoreCommand(file, 'y', 'commandDarwin')
    expect(readFileSync(file, 'utf8')).toBe(original.replace('"x"', '"y"'))
    setInspector(file, true)
    expect(readFileSync(file, 'utf8')).toBe(original.replace('"x"', '"y"').replace('false', 'true'))
  })

  it('refuses a config without the core extension', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-config-'))
    const file = join(dir, 'neutralino.config.json')
    copyFileSync(join(root, 'package.json'), file)
    expect(() => setCoreCommand(file, 'x', 'commandWindows')).toThrow(/extension/)
  })
})

describe('setInspector', () => {
  const dirs: string[] = []
  afterEach(() => { for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true }) })
  const configCopy = (): string => {
    const dir = mkdtempSync(join(tmpdir(), 'claudia-inspector-'))
    dirs.push(dir)
    const file = join(dir, 'neutralino.config.json')
    copyFileSync(join(root, 'apps', 'computes', 'neutralino.config.json'), file)
    return file
  }

  it('turns the inspector on for a debug run and off again, and touches nothing else', () => {
    const file = configCopy()
    const before = JSON.parse(readFileSync(file, 'utf8'))
    setInspector(file, true)
    const on = JSON.parse(readFileSync(file, 'utf8'))
    expect(on.modes.window.enableInspector).toBe(true)
    setInspector(file, false)
    expect(JSON.parse(readFileSync(file, 'utf8'))).toEqual(before)
  })

  it('refuses a config without a window mode', () => {
    const file = configCopy()
    writeFileSync(file, '{}')
    expect(() => setInspector(file, true)).toThrow(/modes\.window/)
  })
})

describe('setLogicalPixels (UX-81, D749)', () => {
  const dirs: string[] = []
  afterEach(() => { for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true }) })
  const configCopy = (): string => {
    const dir = mkdtempSync(join(tmpdir(), 'claudia-pixels-'))
    dirs.push(dir)
    const file = join(dir, 'neutralino.config.json')
    copyFileSync(join(root, 'apps', 'creates', 'neutralino.config.json'), file)
    return file
  }

  it('asks for sizes in logical pixels and takes the key out again, leaving nothing else changed', () => {
    const file = configCopy()
    const before = readFileSync(file, 'utf8')
    setLogicalPixels(file, true)
    expect(JSON.parse(readFileSync(file, 'utf8')).modes.window.useLogicalPixels).toBe(true)
    setLogicalPixels(file, false)
    expect(readFileSync(file, 'utf8')).toBe(before)
  })

  it('refuses a config without a window mode', () => {
    const file = configCopy()
    writeFileSync(file, '{}')
    expect(() => setLogicalPixels(file, true)).toThrow(/modes\.window/)
  })
})
