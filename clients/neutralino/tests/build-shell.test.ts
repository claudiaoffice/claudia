import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { DEFAULT_COMMAND } from '../src/core-command.js'
import { beforeAll, describe, expect, it } from 'vitest'
// @ts-expect-error the build tool is plain JavaScript
import { TARGETS, appsOf, buildApp, platformOf, renderPage } from '../tools/build-shell.mjs'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const template = readFileSync(join(root, 'tools', 'shell-page.template.html'), 'utf8')

describe('renderPage', () => {
  it('puts the title in every place and nothing else changes', () => {
    const page = renderPage(template, 'Claudia Creates')
    expect(page).not.toContain('__TITLE__')
    expect(page).toContain('<title>Claudia Creates</title>')
  })

  it('takes a title with special replacement patterns literally', () => {
    expect(renderPage('<title>__TITLE__</title>', "A$&B$'")).toBe("<title>A$&B$'</title>")
  })

  it('refuses a template without the placeholder', () => {
    expect(() => renderPage('<html></html>', 'x')).toThrow(/__TITLE__/)
  })
})

describe('the page template (what Neutralino serves)', () => {
  it("loads Neutralino's client library and never its globals script (D157), library first", () => {
    expect(template).toContain('<script src="js/neutralino.js"></script>')
    expect(template).not.toMatch(/<script[^>]*__neutralino_globals/)
    expect(template.indexOf('js/neutralino.js')).toBeLessThan(template.indexOf('shell/shell.js'))
  })

  it('has the frame and the status overlay that shell-page-entry.ts looks for', () => {
    for (const id of ['frame', 'status', 'status-title', 'status-details']) expect(template).toContain(`id="${id}"`)
  })

  it('names its icon, so the web view does not ask the server for /favicon.ico, which is not there (CODE-96, D752)', () => {
    expect(template).toContain('<link rel="icon" href="/icon.png">')
    for (const app of ['composes', 'computes', 'creates']) expect(existsSync(join(root, 'apps', app, 'icon.png')), app).toBe(true)
  })

  it('has no inline script (nothing but the two files)', () => {
    expect(template.match(/<script(?![^>]*\bsrc=)[^>]*>/g)).toBeNull()
  })
})

describe('buildApp', () => {
  beforeAll(async () => {
    for (const app of ['composes', 'computes', 'creates']) await buildApp(app, { quiet: true })
  }, 60000)

  it.each(['composes', 'computes', 'creates'])('makes the page, its script and the core of %s', (app) => {
    const dir = join(root, 'apps', app)
    for (const file of ['index.html', 'shell/shell.js', 'ext/core.mjs']) expect(existsSync(join(dir, file)), file).toBe(true)
    expect(readFileSync(join(dir, 'index.html'), 'utf8')).toContain(`Claudia ${app[0]!.toUpperCase()}${app.slice(1)}`)
  })

  it('bundles the menu and the identity of its own app into the page script', () => {
    const creates = readFileSync(join(root, 'apps', 'creates', 'shell', 'shell.js'), 'utf8')
    expect(creates).toContain('run("creates"')
    expect(creates).toContain('Claudia Creates')
    const computes = readFileSync(join(root, 'apps', 'computes', 'shell', 'shell.js'), 'utf8')
    expect(computes).toContain('run("computes"')
  })

  it('keeps Node out of the page script and the browser out of the core', () => {
    expect(readFileSync(join(root, 'apps', 'creates', 'shell', 'shell.js'), 'utf8')).not.toMatch(/node:(fs|http|https|net|child_process)/)
    expect(readFileSync(join(root, 'apps', 'creates', 'ext', 'core.mjs'), 'utf8')).not.toContain('document.getElementById')
  })

  it('refuses an app that does not exist', async () => {
    await expect(buildApp('spreadsheets', { quiet: true })).rejects.toThrow(/unknown app/)
  })

  it.each(['composes', 'computes', 'creates'])('%s: the Neutralino config matches the design (D251, D157)', (app) => {
    const config = JSON.parse(readFileSync(join(root, 'apps', app, 'neutralino.config.json'), 'utf8'))
    expect(config.applicationId).toBe(`de.claudiaoffice.${app}`)
    expect(config.cli.binaryName).toBe(`claudia-${app}`)
    expect(config.tokenSecurity).toBe('one-time') // never 'none' (D157)
    expect(config.url).toBe('/')
    expect(config.modes.window.injectScript).toBeUndefined() // injection into a page Neutralino did not serve never worked
    expect(config.modes.window.injectGlobals).toBeUndefined()
    // the page ends the app when the window is closed: Neutralino 6.8.0 crashes on macOS when it does that itself (D506),
    // and Windows closes the same way, so that one config serves both (D660)
    expect(config.modes.window.exitProcessOnClose).toBe(false)
    expect(config.modes.window.enableInspector).toBe(false) // on, Neutralino opens the DevTools by itself; only --debug turns it on
    expect(config.enableExtensions).toBe(true)
    expect(config.extensions).toEqual([{ id: 'de.claudiaoffice.core', commandDarwin: DEFAULT_COMMAND, commandWindows: DEFAULT_COMMAND }])
    // the page may only do what the shell needs: no files, no processes
    expect(config.nativeAllowList.filter((m: string) => /^(filesystem|os|computer)\./.test(m))).toEqual([])
    expect(config.nativeAllowList).toEqual(expect.arrayContaining(['app.exit', 'window.setMainMenu', 'events.on', 'extensions.dispatch', 'app.broadcast']))
    expect(config.cli.binaryVersion).toBe(config.cli.clientVersion)
    expect(existsSync(join(root, 'apps', app, 'icon.png'))).toBe(true)
  })
})

describe('the platform of a build (D660)', () => {
  it('is the one named with --platform, else the one this runs on', () => {
    expect(platformOf(['--platform', 'windows', 'creates'], 'darwin')).toBe('windows')
    expect(platformOf(['creates'], 'win32')).toBe('windows')
    expect(platformOf([], 'darwin')).toBe('macos')
    expect(platformOf([], 'linux')).toBe('macos')
    expect(() => platformOf(['--platform', 'linux'])).toThrow(/unknown platform/)
  })

  it('leaves the option out of the apps, and builds all three when none is named', () => {
    expect(appsOf(['--platform', 'windows', 'creates'])).toEqual(['creates'])
    expect(appsOf(['--platform', 'macos'])).toEqual(['composes', 'computes', 'creates'])
  })

  it("writes each platform's bundles for its own web view and tells them which platform they are", async () => {
    expect(TARGETS).toEqual({ macos: 'safari15', windows: 'chrome109' })
    const into = mkdtempSync(join(tmpdir(), 'claudia-build-windows-'))
    try {
      await buildApp('creates', { quiet: true, platform: 'windows', into })
      // the bundle carries its platform as a constant (src/platform/id.ts), so a Windows build is Windows anywhere
      for (const file of [join('ext', 'core.mjs'), join('shell', 'shell.js')]) {
        expect(readFileSync(join(into, file), 'utf8'), file).toContain('if (true) return "windows"')
      }
    } finally {
      rmSync(into, { recursive: true, force: true })
    }
  }, 60000)
})
