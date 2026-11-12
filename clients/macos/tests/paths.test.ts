// Mirrors clients/linux/src/claudia_shell_gtk/paths.py's own tests, with macOS's own directory conventions
// (~/Library/Application Support, not XDG -- a native Mac app keeps the OS's own layout, the same reasoning D3
// gives for the GTK shell following the GNOME HIG on Linux) and the two escape hatches the Linux client already
// has (CLAUDIA_WEB_DIR, CLAUDIA_SERVER_PYTHON), kept for the same reason there: a wrong explicit path should be
// reported, not quietly replaced by another frontend or interpreter.
import { existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it } from 'vitest'
import { configDir, defaultRepo, documentsDir, findFrontend, findRepo, findServerPython, stateDir } from '../src/paths.js'

describe('documentsDir / stateDir', () => {
  it("live under ~/Library/Application Support/Claudia/<app>, macOS's own convention", () => {
    expect(documentsDir('creates', '/Users/x')).toBe('/Users/x/Library/Application Support/Claudia/creates/documents')
    expect(stateDir('creates', '/Users/x')).toBe('/Users/x/Library/Application Support/Claudia/creates/state')
  })
})

describe('configDir', () => {
  it("is the folder of the whole suite, not of one app: the server lists of every app share one shell.json", () => {
    expect(configDir('/Users/x')).toBe('/Users/x/Library/Application Support/Claudia')
  })
})

describe('defaultRepo', () => {
  it('is the repository this client was started from (4 levels up from src/paths.ts, like paths.py), whatever the checkout is called', () => {
    expect(existsSync(join(defaultRepo(), 'clients', 'macos', 'package.json'))).toBe(true)
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

describe('findRepo / defaultRepo', () => {
  let dir = ''
  afterEach(() => rmSync(dir, { recursive: true, force: true }))

  it('finds the repository from every place the code runs from: src, dist and the bundled core in apps/<app>/ext', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-repo-'))
    mkdirSync(join(dir, 'clients', 'macos', 'apps', 'computes', 'ext'), { recursive: true })
    mkdirSync(join(dir, 'clients', 'macos', 'dist'), { recursive: true })
    mkdirSync(join(dir, 'clients', 'macos', 'src'), { recursive: true })
    writeFileSync(join(dir, 'clients', 'macos', 'package.json'), '{}')
    for (const place of ['src', 'dist', join('apps', 'computes', 'ext')]) {
      expect(findRepo(join(dir, 'clients', 'macos', place))).toBe(dir)
      expect(defaultRepo(join(dir, 'clients', 'macos', place))).toBe(dir)
    }
  })

  it('knows nothing outside a checkout, and defaultRepo then falls back to the old three-levels-up guess', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-norepo-'))
    mkdirSync(join(dir, 'a', 'b', 'c'), { recursive: true })
    expect(findRepo(join(dir, 'a', 'b', 'c'))).toBeNull()
    expect(defaultRepo(join(dir, 'a', 'b', 'c'))).toBe(dir)
  })

  it('is this very checkout for this very file (the real layout, not only a model of it)', () => {
    const here = dirname(fileURLToPath(import.meta.url))
    const repo = defaultRepo(join(here, '..', 'apps', 'creates', 'ext'))
    expect(existsSync(join(repo, 'clients', 'macos', 'package.json'))).toBe(true)
    expect(defaultRepo()).toBe(repo)
  })
})
