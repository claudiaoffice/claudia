import { describe, expect, it } from 'vitest'
import { parseCommand, splitAppArgument, usage } from '../src/cli.js'

const run = (app: string, ...args: string[]) => parseCommand(app, args, '1.2.3')

describe('parseCommand', () => {
  it('starts the app\'s own server when no option is given', () => {
    expect(run('creates')).toEqual({ kind: 'run', options: { app: 'creates', server: null, debug: false } })
  })

  it('connects to the server named by --server, in either spelling', () => {
    for (const args of [['--server', 'demo.claudia-office.de'], ['--server=demo.claudia-office.de']]) {
      const command = run('computes', ...args)
      expect(command.kind).toBe('run')
      if (command.kind === 'run') {
        expect(command.options.app).toBe('computes')
        expect(command.options.server?.origin).toBe('https://demo.claudia-office.de')
      }
    }
  })

  it('takes plain http for this computer only', () => {
    const ok = run('creates', '--server', 'http://127.0.0.1:8123')
    expect(ok.kind).toBe('run')
    const refused = run('creates', '--server', 'http://example.com')
    expect(refused).toMatchObject({ kind: 'usage_error', code: 2 })
    if (refused.kind === 'usage_error') expect(refused.text).toContain('--server')
  })

  it('reads --debug', () => {
    expect(run('creates', '--debug')).toMatchObject({ kind: 'run', options: { debug: true } })
  })

  it('prints the help for --help and -h, and the version for --version, with exit code 0', () => {
    expect(run('composes', '--help')).toEqual({ kind: 'print', text: usage('composes'), code: 0 })
    expect(run('composes', '-h')).toMatchObject({ kind: 'print', code: 0 })
    expect(run('composes', '--version')).toEqual({ kind: 'print', text: 'claudia-composes 1.2.3', code: 0 })
  })

  it('exits 2 for an unknown option, a stray word, a missing value, and an app that does not exist', () => {
    for (const args of [['--nope'], ['stray'], ['--server']]) {
      expect(run('creates', ...args)).toMatchObject({ kind: 'usage_error', code: 2 })
    }
    expect(run('spreadsheets')).toMatchObject({ kind: 'usage_error', code: 2 })
  })

  it('the help is for the app, and says what --server does', () => {
    expect(usage('computes')).toContain('usage: claudia-computes')
    expect(usage('computes')).toContain('Claudia Computes')
    expect(usage('computes')).toContain('--server URL')
  })
})

describe('splitAppArgument', () => {
  it('takes the app first and leaves the rest', () => {
    expect(splitAppArgument(['creates', '--debug'])).toEqual({ app: 'creates', rest: ['--debug'] })
  })

  it('has no picker: no app is an error that names the apps', () => {
    for (const argv of [[], ['--debug']]) {
      const split = splitAppArgument(argv)
      expect('error' in split && split.error).toContain('composes, computes, creates')
    }
  })
})
