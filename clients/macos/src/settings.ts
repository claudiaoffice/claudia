// The shell's own small, persisted settings: the servers each app remembers (E5.8). Port of the servers part of
// clients/linux/src/claudia_shell_gtk/settings.py; the language and the trusted certificates that file also holds
// are not used here yet (self-signed certificates are deferred for every desktop client), but they are kept when
// found, because Linux and macOS write the same `shell.json` format.
//
// One JSON file, `shell.json` in `paths.configDir()`:
//   {"servers": {"computes": [{"origin": "https://demo.example.org:8420", "label": "demo", "custom": false}]}, ...}
//
// Every save reads the file, changes **its own key only** and writes the whole file back through a temporary file
// and a rename -- so one setting can never erase another, and a crash cannot leave half a file.
//
// A problem with the file is never fatal: an unreadable or unexpected file reads as "nothing saved", and a write
// that is impossible (a read-only home, a full disk) is logged and otherwise ignored.

import { mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { randomBytes } from 'node:crypto'
import { configDir } from './paths.js'
import { sanitize, type Entry } from './servers.js'

const FILENAME = 'shell.json'

export type Logger = (message: string) => void

export class Settings {
  /** `file` is the settings file (default: `shell.json` in the config directory); `log` hears about write failures. */
  constructor(
    private readonly file: string = join(configDir(), FILENAME),
    private readonly log: Logger = () => {},
  ) {}

  private read(): Record<string, unknown> {
    try {
      const data: unknown = JSON.parse(readFileSync(this.file, 'utf8'))
      return typeof data === 'object' && data !== null && !Array.isArray(data) ? (data as Record<string, unknown>) : {}
    } catch {
      return {}
    }
  }

  private update(what: string, change: (data: Record<string, unknown>) => void): void {
    const data = this.read()
    change(data)
    const directory = join(this.file, '..')
    const temporary = join(directory, `.shell-${randomBytes(4).toString('hex')}.tmp`)
    try {
      mkdirSync(directory, { recursive: true })
      writeFileSync(temporary, JSON.stringify(data), 'utf8')
      renameSync(temporary, this.file)
    } catch (problem) {
      this.log(`could not save ${what} to ${this.file}: ${(problem as Error).message}`)
      try {
        rmSync(temporary, { force: true })
      } catch {
        // nothing sensible to do
      }
    }
  }

  /** The servers that `app` remembers; only what `sanitize` accepts is returned. */
  loadServers(app: string): Entry[] {
    const servers = this.read().servers
    return sanitize(typeof servers === 'object' && servers !== null && !Array.isArray(servers) ? (servers as Record<string, unknown>)[app] : undefined)
  }

  /** Remember `entries` for `app`, replacing its list. Only what passes `sanitize` is written. */
  saveServers(app: string, entries: readonly Entry[]): void {
    const kept = sanitize([...entries])
    this.update(`the servers of ${app}`, (data) => {
      const current = data.servers
      const servers: Record<string, unknown> =
        typeof current === 'object' && current !== null && !Array.isArray(current) ? (current as Record<string, unknown>) : {}
      servers[app] = kept
      data.servers = servers
    })
  }
}
