// The real fix for the owner's second real-run bug that macProcessName() (launch.ts) turned out NOT to be: the
// application-menu heading next to the Apple logo, the Cmd+Tab switcher and Activity Monitor all read a running
// process's *bundle* identity (CFBundleName, via NSBundle/NSRunningApplication) for an app that has one, not
// argv[0] -- confirmed by re-reading Neutralino's own macOS source (api/window/window.cpp's setMainMenu() only
// ever calls NSApplication.setMainMenu: with our own menu items, never anything that touches CFBundleName or
// NSApplication's own name) and by outside evidence of the same gap in other bare-executable Cocoa apps
// (https://discourse.libsdl.org/t/setting-the-application-name-on-osx/31982: "You can't do it without putting
// your app in an app bundle, AFAIK" -- confirmed there too, that changing argv[0] has no effect). There is no way
// around a real `.app` bundle short of full packaging (D157/README "Not done"), so this builds the smallest one
// that works: Contents/MacOS/<executable>, Contents/Info.plist, nothing else (no .icns -- the running dock icon
// the owner already praised comes from neutralino.config.json's own modes.window.icon, a completely separate
// thing from Finder's icon for the .app itself, which this intentionally leaves generic for now).
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, utimesSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { ensureAppBundle, infoPlist } from '../src/app-bundle.js'
import { getIdentity } from '../src/identity.js'

describe('infoPlist', () => {
  it('names the executable, the bundle id, and the display name -- the three keys CFBundleName/Info.plist need', () => {
    const plist = infoPlist({ bundleId: 'de.claudiaoffice.creates', executableName: 'claudia-creates', displayName: 'claudia creates' })
    expect(plist).toContain('<key>CFBundleExecutable</key>\n\t<string>claudia-creates</string>')
    expect(plist).toContain('<key>CFBundleIdentifier</key>\n\t<string>de.claudiaoffice.creates</string>')
    expect(plist).toContain('<key>CFBundleName</key>\n\t<string>claudia creates</string>')
    expect(plist).toContain('<key>CFBundleDisplayName</key>\n\t<string>claudia creates</string>')
  })

  it('is well-formed-enough XML: one root <plist>, one <dict>, balanced tags', () => {
    const plist = infoPlist({ bundleId: 'de.claudiaoffice.creates', executableName: 'claudia-creates', displayName: 'claudia creates' })
    expect(plist).toMatch(/^<\?xml/)
    expect(plist.match(/<plist/g)).toHaveLength(1)
    expect(plist.match(/<\/plist>/g)).toHaveLength(1)
    expect(plist.match(/<dict>/g)).toHaveLength(1)
    expect(plist.match(/<\/dict>/g)).toHaveLength(1)
  })
})

describe('ensureAppBundle', () => {
  let dir: string
  let binDir: string
  let sourceBinary: string

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-app-bundle-'))
    binDir = join(dir, 'bin')
    mkdirSync(binDir, { recursive: true })
    sourceBinary = join(binDir, 'neutralino-mac_arm64')
    writeFileSync(sourceBinary, 'pretend-binary-bytes-v1')
    chmodSync(sourceBinary, 0o755)
  })

  afterEach(() => {
    rmSync(dir, { recursive: true, force: true })
  })

  it('creates Contents/MacOS/<executable> and Contents/Info.plist, and returns the executable path', () => {
    const executablePath = ensureAppBundle({
      binDir,
      sourceBinary,
      identity: getIdentity('creates'),
      displayName: 'claudia creates',
    })
    expect(executablePath).toBe(join(binDir, 'claudia-creates.app', 'Contents', 'MacOS', 'claudia-creates'))
    expect(readFileSync(executablePath, 'utf8')).toBe('pretend-binary-bytes-v1')
    expect(statSync(executablePath).mode & 0o111).toBeTruthy() // still executable
    const plist = readFileSync(join(binDir, 'claudia-creates.app', 'Contents', 'Info.plist'), 'utf8')
    expect(plist).toContain('claudia creates')
    expect(plist).toContain('de.claudiaoffice.creates')
  })

  it('does not re-copy the binary when the bundle is already as new as the source (an unnecessary copy of a large file on every launch)', () => {
    const first = ensureAppBundle({ binDir, sourceBinary, identity: getIdentity('creates'), displayName: 'claudia creates' })
    const firstCopyTime = statSync(first).mtimeMs
    const second = ensureAppBundle({ binDir, sourceBinary, identity: getIdentity('creates'), displayName: 'claudia creates' })
    expect(statSync(second).mtimeMs).toBe(firstCopyTime) // untouched, not rewritten
  })

  it('re-copies when the source binary is newer than the bundled copy (a fresh `neu update` download)', () => {
    const executablePath = ensureAppBundle({ binDir, sourceBinary, identity: getIdentity('creates'), displayName: 'claudia creates' })
    const past = new Date(Date.now() - 10_000)
    utimesSync(executablePath, past, past) // the existing bundled copy looks old
    writeFileSync(sourceBinary, 'pretend-binary-bytes-v2') // a newer download replaced the source
    ensureAppBundle({ binDir, sourceBinary, identity: getIdentity('creates'), displayName: 'claudia creates' })
    expect(readFileSync(executablePath, 'utf8')).toBe('pretend-binary-bytes-v2')
  })

  it('(re)writes Info.plist every time, even when the binary copy is skipped -- cheap, and keeps it in step with identity.ts', () => {
    ensureAppBundle({ binDir, sourceBinary, identity: getIdentity('creates'), displayName: 'claudia creates' })
    ensureAppBundle({ binDir, sourceBinary, identity: getIdentity('creates'), displayName: 'a different display name' })
    const plist = readFileSync(join(binDir, 'claudia-creates.app', 'Contents', 'Info.plist'), 'utf8')
    expect(plist).toContain('a different display name')
  })
})
