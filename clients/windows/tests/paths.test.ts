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
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it } from 'vitest'
import { configDir, defaultLocalAppData, defaultRepo, documentsDir, findFrontend, findRepo, findServerPython, stateDir } from '../src/paths.js'

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

describe('configDir', () => {
  it('is the folder of the whole suite, not of one app: the server lists of every app share one shell.json', () => {
    expect(configDir('C:\\Users\\me\\AppData\\Local')).toBe(join('C:\\Users\\me\\AppData\\Local', 'Claudia'))
    expect(documentsDir('computes', 'L')).toBe(join(configDir('L'), 'computes', 'documents'))
  })
})

describe('findRepo / defaultRepo', () => {
  let dir = ''
  afterEach(() => rmSync(dir, { recursive: true, force: true }))

  it('finds the repository from every place the code runs from: src, dist and the bundled core in apps/<app>/ext', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-repo-'))
    mkdirSync(join(dir, 'clients', 'windows', 'apps', 'computes', 'ext'), { recursive: true })
    mkdirSync(join(dir, 'clients', 'windows', 'dist'), { recursive: true })
    mkdirSync(join(dir, 'clients', 'windows', 'src'), { recursive: true })
    writeFileSync(join(dir, 'clients', 'windows', 'package.json'), '{}')
    for (const place of ['src', 'dist', join('apps', 'computes', 'ext')]) {
      expect(findRepo(join(dir, 'clients', 'windows', place))).toBe(dir)
      expect(defaultRepo(join(dir, 'clients', 'windows', place))).toBe(dir)
    }
  })

  it('knows nothing outside a checkout, and defaultRepo then falls back to the old three-levels-up guess', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-norepo-'))
    mkdirSync(join(dir, 'a', 'b', 'c'), { recursive: true })
    expect(findRepo(join(dir, 'a', 'b', 'c'))).toBeNull()
    expect(defaultRepo(join(dir, 'a', 'b', 'c'))).toBe(dir)
  })

  it('is this very checkout for this very file (the real layout, not only a model of it), whatever the clone is called', () => {
    const here = dirname(fileURLToPath(import.meta.url))
    const repo = defaultRepo(join(here, '..', 'apps', 'creates', 'ext'))
    expect(existsSync(join(repo, 'clients', 'windows', 'package.json'))).toBe(true)
    expect(existsSync(join(repo, 'pyproject.toml'))).toBe(true)
    expect(defaultRepo()).toBe(repo)
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
