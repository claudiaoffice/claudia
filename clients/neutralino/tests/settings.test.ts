import { mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { Settings } from '../src/settings.js'

describe('Settings', () => {
  let directory: string
  let file: string
  beforeEach(() => {
    directory = mkdtempSync(join(tmpdir(), 'claudia-settings-'))
    file = join(directory, 'Claudia', 'shell.json')
  })
  afterEach(() => rmSync(directory, { recursive: true, force: true }))

  it('has no servers before anything was saved, and no file', () => {
    expect(new Settings(file).loadServers('creates')).toEqual([])
  })

  it('saves the servers of one app and reads them back, creating the folder', () => {
    const settings = new Settings(file)
    settings.saveServers('creates', [{ origin: 'https://a.example', label: 'A', custom: true }])
    expect(new Settings(file).loadServers('creates')).toEqual([{ origin: 'https://a.example', label: 'A', custom: true }])
    expect(new Settings(file).loadServers('computes')).toEqual([])
  })

  it('keeps what else is in the file (the language, trusted certificates, other apps)', () => {
    mkdirSync(join(directory, 'Claudia'), { recursive: true })
    writeFileSync(file, JSON.stringify({ locale: 'de', trusted: { 'a.example': 'abc' }, servers: { composes: [{ origin: 'https://c.example', label: 'C', custom: false }] } }))
    new Settings(file).saveServers('creates', [{ origin: 'https://a.example', label: 'A', custom: false }])
    const data = JSON.parse(readFileSync(file, 'utf8'))
    expect(data.locale).toBe('de')
    expect(data.trusted).toEqual({ 'a.example': 'abc' })
    expect(data.servers.composes).toHaveLength(1)
    expect(data.servers.creates).toHaveLength(1)
  })

  it('writes only what is valid', () => {
    new Settings(file).saveServers('creates', [
      { origin: 'https://ok.example', label: 'ok', custom: false },
      { origin: 'javascript:alert(1)', label: 'bad', custom: false },
    ])
    expect(new Settings(file).loadServers('creates').map((e) => e.origin)).toEqual(['https://ok.example'])
  })

  it('reads a broken or unexpected file as nothing saved', () => {
    mkdirSync(join(directory, 'Claudia'), { recursive: true })
    writeFileSync(file, '{not json')
    expect(new Settings(file).loadServers('creates')).toEqual([])
    writeFileSync(file, '[1,2]')
    expect(new Settings(file).loadServers('creates')).toEqual([])
    writeFileSync(file, JSON.stringify({ servers: 'x' }))
    expect(new Settings(file).loadServers('creates')).toEqual([])
  })

  it('leaves no temporary file behind', () => {
    new Settings(file).saveServers('creates', [])
    expect(readdirSync(join(directory, 'Claudia'))).toEqual(['shell.json'])
  })

  it('logs a write that is impossible and goes on', () => {
    const logged: string[] = []
    writeFileSync(join(directory, 'blocker'), 'a file where a folder should be')
    const settings = new Settings(join(directory, 'blocker', 'shell.json'), (m) => logged.push(m))
    expect(() => settings.saveServers('creates', [])).not.toThrow()
    expect(logged.join('')).toContain('could not save')
  })
})
