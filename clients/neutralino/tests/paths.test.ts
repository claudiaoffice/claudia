// Mirrors clients/linux/src/claudia_shell_gtk/paths.py's own tests, with macOS's and Windows's own directory conventions
// (~/Library/Application Support and %LOCALAPPDATA%, not XDG -- a native app keeps the OS's own layout, the same reasoning D3
// gives for the GTK shell following the GNOME HIG on Linux) and the two escape hatches the Linux client already
// has (CLAUDIA_WEB_DIR, CLAUDIA_SERVER_PYTHON), kept for the same reason there: a wrong explicit path should be
// reported, not quietly replaced by another frontend or interpreter.
import { chmodSync, existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it } from 'vitest'
import { appFolder, claudiaFolder, configDir, defaultRepo, findFrontend, findRepo, findServerProgram, findServerPython, serverDocumentsDir, serverStateDir, stateDir } from '../src/paths.js'
import { hostPlatform } from '../src/platform/host.js'
import { localAppData } from '../src/platform/windows.js'

describe('claudiaFolder', () => {
  it("is ~/Library/Application Support/Claudia on a Mac", () => {
    expect(claudiaFolder(hostPlatform('macos'), {}, '/Users/x')).toBe(join('/Users/x', 'Library', 'Application Support', 'Claudia'))
  })

  it('is <LOCALAPPDATA>/Claudia on Windows', () => {
    expect(claudiaFolder(hostPlatform('windows'), { LOCALAPPDATA: 'C:\\Users\\x\\AppData\\Local' }, 'C:\\Users\\x')).toBe(
      join('C:\\Users\\x\\AppData\\Local', 'Claudia'),
    )
  })

  it('falls back to <home>/AppData/Local on Windows when LOCALAPPDATA is unset -- a bare profile, not the Windows norm, but what a test runner or a fresh CI user may have', () => {
    expect(claudiaFolder(hostPlatform('windows'), {}, '/Users/x')).toBe(join('/Users/x', 'AppData', 'Local', 'Claudia'))
    expect(localAppData({}, '/Users/x')).toBe(join('/Users/x', 'AppData', 'Local'))
  })
})

describe('serverDocumentsDir / serverStateDir / stateDir', () => {
  const suite = join('/Users/x', 'Library', 'Application Support', 'Claudia')

  it("the local server's folders are the suite's: the three apps share one server (D445)", () => {
    expect(serverDocumentsDir(suite)).toBe(join(suite, 'documents'))
    expect(serverStateDir(suite)).toBe(join(suite, 'state'))
  })

  it("a shell's own log is its app's: <suite>/<app>/state", () => {
    expect(stateDir('creates', suite)).toBe(join(suite, 'creates', 'state'))
  })
})

describe('configDir', () => {
  it("is the folder of the whole suite, not of one app: the server lists of every app share one shell.json", () => {
    expect(configDir('/Users/x/Library/Application Support/Claudia')).toBe('/Users/x/Library/Application Support/Claudia')
    expect(serverDocumentsDir('L')).toBe(join(configDir('L'), 'documents'))
  })
})

describe('defaultRepo', () => {
  it('is the repository this client was started from (4 levels up from src/paths.ts, like paths.py), whatever the checkout is called', () => {
    expect(existsSync(join(defaultRepo(), 'clients', 'neutralino', 'package.json'))).toBe(true)
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

  it.each([
    ['macos', ['.venv', 'bin', 'python']],
    ['windows', ['.venv', 'Scripts', 'python.exe']],
  ] as const)('on %s looks where `uv sync` puts the interpreter there', (id, parts) => {
    const repo = mkdtempSync(join(tmpdir(), 'claudia-venv-'))
    try {
      mkdirSync(join(repo, ...parts.slice(0, -1)), { recursive: true })
      writeFileSync(join(repo, ...parts), '')
      chmodSync(join(repo, ...parts), 0o755)
      expect(findServerPython({ repo, env: {}, platform: hostPlatform(id) })).toBe(join(repo, ...parts))
      const other = hostPlatform(id === 'macos' ? 'windows' : 'macos')
      expect(findServerPython({ repo, env: {}, platform: other })).toBeNull()
    } finally {
      rmSync(repo, { recursive: true, force: true })
    }
  })
})

describe('findRepo / defaultRepo', () => {
  let dir = ''
  afterEach(() => rmSync(dir, { recursive: true, force: true }))

  it('finds the repository from every place the code runs from: src, dist and the bundled core in apps/<app>/ext', () => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-repo-'))
    mkdirSync(join(dir, 'clients', 'neutralino', 'apps', 'computes', 'ext'), { recursive: true })
    mkdirSync(join(dir, 'clients', 'neutralino', 'dist'), { recursive: true })
    mkdirSync(join(dir, 'clients', 'neutralino', 'src'), { recursive: true })
    writeFileSync(join(dir, 'clients', 'neutralino', 'package.json'), '{}')
    for (const place of ['src', 'dist', join('apps', 'computes', 'ext')]) {
      expect(findRepo(join(dir, 'clients', 'neutralino', place))).toBe(dir)
      expect(defaultRepo(join(dir, 'clients', 'neutralino', place))).toBe(dir)
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
    expect(existsSync(join(repo, 'clients', 'neutralino', 'package.json'))).toBe(true)
    expect(defaultRepo()).toBe(repo)
  })
})

describe('findServerProgram (D740)', () => {
  it('CLAUDIA_SERVER_EXE, when set, is the program: the installer ships the server with its interpreter inside', () => {
    expect(findServerProgram({ repo: '/does/not/matter', env: { CLAUDIA_SERVER_EXE: 'C:\\Claudia\\server\\claudia-server.exe' } })).toEqual({
      exe: 'C:\\Claudia\\server\\claudia-server.exe',
    })
  })

  it('wins over CLAUDIA_SERVER_PYTHON, because it is what an installed client sets', () => {
    expect(findServerProgram({ env: { CLAUDIA_SERVER_EXE: '/opt/s', CLAUDIA_SERVER_PYTHON: '/opt/python' } })).toEqual({ exe: '/opt/s' })
  })

  it('is the interpreter, as before, when no exe is named', () => {
    expect(findServerProgram({ repo: '/x', env: { CLAUDIA_SERVER_PYTHON: '/opt/python3.14' } })).toBe('/opt/python3.14')
    expect(findServerProgram({ repo: '/definitely/not/a/real/path', env: {} })).toBeNull()
  })
})

describe('appFolder', () => {
  // CODE-81 (D746): the launcher of an installation looked for its apps in a repository that is not there.
  it.each([
    ['an installation (Windows: <install>\\client\\dist)', join('Programs', 'Claudia Office', 'client')],
    ['a checkout', join('repo', 'clients', 'neutralino')],
  ])('is apps/<app> beside the launcher\'s own folder in %s, with or without a repository around it', (_place, client) => {
    for (const folder of ['dist', 'src']) {
      expect(appFolder('computes', join(client, folder))).toBe(join(client, 'apps', 'computes'))
    }
  })

  it('is, for this very checkout, a folder that has the app\'s window configuration', () => {
    expect(existsSync(join(appFolder('composes'), 'neutralino.config.json'))).toBe(true)
  })
})
