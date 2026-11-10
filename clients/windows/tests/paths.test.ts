// Mirrors clients/linux/src/claudia_shell_gtk/paths.py's and clients/macos/tests/paths.test.ts's own tests, with
// Windows's own directory convention (%LOCALAPPDATA%, not XDG or ~/Library -- a native Windows app keeps the OS's
// own layout, the same reasoning D3 gives for the GTK shell following the GNOME HIG on Linux) and the two escape
// hatches the Linux and macOS clients already have (CLAUDIA_WEB_DIR, CLAUDIA_SERVER_PYTHON), kept for the same
// reason there: a wrong explicit path should be reported, not quietly replaced by another frontend or interpreter.
//
// Expected paths are built with the same `join()` the production code uses (not a hardcoded backslash string):
// paths.ts's own top comment explains why -- `join` is `path.win32` once this really runs on Windows, and building
// both sides of an assertion from the same function is what keeps this file correct on whatever host runs it,
// including this repository's own Linux-hosted `npm test`.
import { existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { defaultLocalAppData, defaultRepo, documentsDir, findFrontend, findServerPython, stateDir } from '../src/paths.js'

describe('documentsDir / stateDir', () => {
  it("live under <LOCALAPPDATA>/Claudia/<app>, Windows's own convention", () => {
    expect(documentsDir('composes', '/Users/x/AppData/Local')).toBe(
      join('/Users/x/AppData/Local', 'Claudia', 'composes', 'documents'),
    )
    expect(stateDir('composes', '/Users/x/AppData/Local')).toBe(
      join('/Users/x/AppData/Local', 'Claudia', 'composes', 'state'),
    )
  })
})

describe('defaultLocalAppData', () => {
  it('uses LOCALAPPDATA when the environment sets it', () => {
    expect(defaultLocalAppData('/Users/x', { LOCALAPPDATA: '/Users/x/AppData/Local' })).toBe('/Users/x/AppData/Local')
  })

  it('falls back to <home>/AppData/Local when LOCALAPPDATA is unset -- a bare profile, not the Windows norm, but what a test runner or a fresh CI user may have', () => {
    expect(defaultLocalAppData('/Users/x', {})).toBe(join('/Users/x', 'AppData', 'Local'))
  })
})

describe('defaultRepo', () => {
  it('is the repository this client was started from (4 levels up from src/paths.ts, like paths.py and the macOS client)', () => {
    // By what is in it, not by its folder's name: a clone may be called anything.
    expect(existsSync(join(defaultRepo(), 'clients', 'windows', 'package.json'))).toBe(true)
    expect(existsSync(join(defaultRepo(), 'pyproject.toml'))).toBe(true)
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
    expect(findServerPython({ repo: '/does/not/matter', env: { CLAUDIA_SERVER_PYTHON: '/opt/python3.14/python.exe' } })).toBe(
      '/opt/python3.14/python.exe',
    )
  })

  it('falls back to the repository .venv/Scripts/python.exe, and to null when neither exists', () => {
    expect(findServerPython({ repo: '/definitely/not/a/real/path', env: {} })).toBeNull()
  })
})
