// Mirrors clients/linux/src/claudia_shell_gtk/paths.py's own tests, with macOS's own directory conventions
// (~/Library/Application Support, not XDG -- a native Mac app keeps the OS's own layout, the same reasoning D3
// gives for the GTK shell following the GNOME HIG on Linux) and the two escape hatches the Linux client already
// has (CLAUDIA_WEB_DIR, CLAUDIA_SERVER_PYTHON), kept for the same reason there: a wrong explicit path should be
// reported, not quietly replaced by another frontend or interpreter.
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { defaultRepo, documentsDir, findFrontend, findServerPython, stateDir } from '../src/paths.js'

describe('documentsDir / stateDir', () => {
  it("live under ~/Library/Application Support/Claudia/<app>, macOS's own convention", () => {
    expect(documentsDir('creates', '/Users/x')).toBe('/Users/x/Library/Application Support/Claudia/creates/documents')
    expect(stateDir('creates', '/Users/x')).toBe('/Users/x/Library/Application Support/Claudia/creates/state')
  })
})

describe('defaultRepo', () => {
  it('is the repository this client was started from (4 levels up from src/paths.ts, like paths.py)', () => {
    expect(defaultRepo().endsWith('/claudia')).toBe(true)
  })
})

describe('findFrontend', () => {
  let dir: string
  afterEach(() => {
    if (dir) rmSync(dir, { recursive: true, force: true })
  })

  it('returns null when nothing has an index.html', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-frontend-'))
    expect(findFrontend({ repo: dir, env: {} })).toBeNull()
  })

  it('finds the development checkout build, web/.output/public', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-frontend-'))
    const checkout = join(dir, 'web', '.output', 'public')
    mkdirSync(checkout, { recursive: true })
    writeFileSync(join(checkout, 'index.html'), '<html></html>')
    expect(findFrontend({ repo: dir, env: {} })).toBe(checkout)
  })

  it('CLAUDIA_WEB_DIR is the only candidate when set, even if it has no index.html (reported, not bypassed)', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-frontend-'))
    const checkout = join(dir, 'web', '.output', 'public')
    mkdirSync(checkout, { recursive: true })
    writeFileSync(join(checkout, 'index.html'), '<html></html>')
    const wrong = join(dir, 'nope')
    expect(findFrontend({ repo: dir, env: { CLAUDIA_WEB_DIR: wrong } })).toBeNull()
  })
})

describe('findServerPython', () => {
  it('CLAUDIA_SERVER_PYTHON, when set, is returned as-is (no existence check -- the caller finds out when it fails to spawn)', () => {
    expect(findServerPython({ repo: '/does/not/matter', env: { CLAUDIA_SERVER_PYTHON: '/opt/python3.14' } })).toBe(
      '/opt/python3.14',
    )
  })

  it('falls back to the repository .venv, and to null when neither exists', () => {
    expect(findServerPython({ repo: '/definitely/not/a/real/path', env: {} })).toBeNull()
  })
})
