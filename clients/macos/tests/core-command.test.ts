import { copyFileSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it } from 'vitest'
import { buildCoreCommand, DEFAULT_COMMAND, parseCoreArgs, setCoreCommand } from '../src/core-command.js'

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

  it.each(['composes', 'computes', 'creates'])('%s: changes the command and nothing else, and the default restores the file byte for byte', (app) => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-config-'))
    const original = join(root, 'apps', app, 'neutralino.config.json')
    const copy = join(dir, 'neutralino.config.json')
    copyFileSync(original, copy)
    setCoreCommand(copy, buildCoreCommand({ ...base, app }))
    const changed = JSON.parse(readFileSync(copy, 'utf8'))
    expect(changed.extensions[0].commandDarwin).toContain(`--app=${app}`)
    expect({ ...changed, extensions: null }).toEqual({ ...JSON.parse(readFileSync(original, 'utf8')), extensions: null })
    setCoreCommand(copy, DEFAULT_COMMAND)
    expect(readFileSync(copy, 'utf8')).toBe(readFileSync(original, 'utf8'))
  })

  it('refuses a config without the core extension', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-config-'))
    const file = join(dir, 'neutralino.config.json')
    copyFileSync(join(root, 'package.json'), file)
    expect(() => setCoreCommand(file, 'x')).toThrow(/extension/)
  })
})
