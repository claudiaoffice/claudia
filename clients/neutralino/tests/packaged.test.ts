// The packaged client (D731): what makes a client that an installer put on a computer different from a checkout.
// The files of an app are read from where the installer put them, but the window runs from a copy in the person's
// own folder: the launcher writes the core's command into neutralino.config.json, and `Program Files` is read-only
// and has a space in its name (Neutralino cannot pass a path with a space to the core).
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { PACKAGED_FILE, packagedEnvironment, readPackaged, stageApp } from '../src/packaged.js'

let root: string
beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'claudia-packaged-'))
})
afterEach(() => rmSync(root, { recursive: true, force: true }))

/** `<root>/client/apps/<app>` with what `npm run build` and `neu update` leave there, and the marker beside `apps`. */
function installed(marker: unknown = { web: '../web', server: '../server/claudia-server.exe' }): string {
  const appDir = join(root, 'client', 'apps', 'composes')
  for (const dir of ['bin', 'js', 'shell', 'ext']) mkdirSync(join(appDir, dir), { recursive: true })
  writeFileSync(join(appDir, 'index.html'), '<html>')
  writeFileSync(join(appDir, 'shell', 'shell.js'), 'shell')
  writeFileSync(join(appDir, 'ext', 'core.mjs'), 'core')
  writeFileSync(join(appDir, 'js', 'neutralino.js'), 'lib')
  writeFileSync(join(appDir, 'bin', 'neutralino-win_x64.exe'), 'MZ')
  writeFileSync(join(appDir, 'neutralino.config.json'), '{}')
  writeFileSync(join(appDir, 'icon.png'), 'png')
  if (marker !== null) writeFileSync(join(root, 'client', PACKAGED_FILE), JSON.stringify(marker))
  return appDir
}

describe('readPackaged', () => {
  it('is null in a checkout, which has no marker', () => {
    expect(readPackaged(installed(null))).toBeNull()
  })

  it('reads the frontend and the server, which the marker gives relative to the client folder', () => {
    expect(readPackaged(installed())).toEqual({
      web: join(root, 'web'),
      server: join(root, 'server', 'claudia-server.exe'),
    })
  })

  it('refuses a marker that is not what the installer writes, instead of guessing', () => {
    expect(() => readPackaged(installed({ web: 3 }))).toThrow(/packaged\.json/)
    expect(() => readPackaged(installed('nonsense'))).toThrow(/packaged\.json/)
  })

  it('refuses a marker that is not JSON', () => {
    const appDir = installed(null)
    writeFileSync(join(root, 'client', PACKAGED_FILE), '{')
    expect(() => readPackaged(appDir)).toThrow(/packaged\.json/)
  })
})

describe('packagedEnvironment', () => {
  const packaged = { web: '/c/web', server: '/c/server/claudia-server.exe' }

  it('names the frontend and the server the installer shipped', () => {
    expect(packagedEnvironment(packaged, {})).toEqual({ CLAUDIA_WEB_DIR: '/c/web', CLAUDIA_SERVER_EXE: '/c/server/claudia-server.exe' })
  })

  it('leaves what the person set alone: an own server or frontend wins, in any spelling of the name', () => {
    expect(packagedEnvironment(packaged, { claudia_web_dir: '/mine' })).toEqual({ CLAUDIA_SERVER_EXE: '/c/server/claudia-server.exe' })
    expect(packagedEnvironment(packaged, { CLAUDIA_SERVER_PYTHON: '/py' })).toEqual({ CLAUDIA_WEB_DIR: '/c/web' })
    expect(packagedEnvironment(packaged, { CLAUDIA_SERVER_EXE: '/mine.exe' })).toEqual({ CLAUDIA_WEB_DIR: '/c/web' })
  })
})

describe('stageApp', () => {
  it('copies what the window needs and leaves the big binary where it is', () => {
    const appDir = installed()
    const run = join(root, 'run', 'composes')
    stageApp(appDir, run)
    for (const file of ['index.html', 'neutralino.config.json', 'icon.png', join('shell', 'shell.js'), join('ext', 'core.mjs'), join('js', 'neutralino.js')]) {
      expect(readFileSync(join(run, file), 'utf8')).toBe(readFileSync(join(appDir, file), 'utf8'))
    }
    expect(existsSync(join(run, 'bin'))).toBe(false)
  })

  it('starts from a clean folder every time, so a file of an older version never stays', () => {
    const appDir = installed()
    const run = join(root, 'run', 'composes')
    mkdirSync(run, { recursive: true })
    writeFileSync(join(run, 'old.txt'), 'x')
    stageApp(appDir, run)
    expect(existsSync(join(run, 'old.txt'))).toBe(false)
    expect(existsSync(join(run, 'index.html'))).toBe(true)
  })

  it('never changes the installed files: the config the launcher writes is the copy', () => {
    const appDir = installed()
    const run = join(root, 'run', 'composes')
    stageApp(appDir, run)
    writeFileSync(join(run, 'neutralino.config.json'), '{"changed":true}')
    expect(readFileSync(join(appDir, 'neutralino.config.json'), 'utf8')).toBe('{}')
  })

  it('refuses to put the copy into the folder it copies from', () => {
    const appDir = installed()
    expect(() => stageApp(appDir, appDir)).toThrow(/same folder/)
  })
})
