// The real fix for a bug macProcessName() (launch.ts) turned out not to actually fix: the application-menu
// heading next to the Apple logo, the Cmd+Tab switcher and Activity Monitor all read a running process's *bundle*
// identity (CFBundleName, through NSBundle/NSRunningApplication) when it has one -- not argv[0], and not anything
// set through Neutralino's own NSApplication.setMainMenu: call (confirmed by reading Neutralino's own macOS
// source, api/window/window.cpp: that call only ever installs our menu items, nothing about the app's own name).
// Outside evidence of the same gap in other bare-executable Cocoa apps: a plain SDL app's menu-bar name did not
// change when argv[0] did -- "you can't do it without putting your app in an app bundle, AFAIK"
// (https://discourse.libsdl.org/t/setting-the-application-name-on-osx/31982).
//
// Full packaging (.icns, codesigning, notarization, a DMG) is still "Not done" (the README says so) -- this is
// the smallest bundle that gets CFBundleName to apply at all: Contents/MacOS/<executable>, Contents/Info.plist,
// nothing else. The dock icon the owner already has and likes comes from neutralino.config.json's own
// modes.window.icon at runtime, a completely separate mechanism from Finder's icon for the .app bundle itself
// (which this intentionally leaves generic for now, hence no CFBundleIconFile here).
//
// Confirmed against Neutralino's own settings.cpp that this is safe: --path is read as an explicit override
// (`appPath = cliArg.value`) and only falls back to the executable's own directory when --path is absent --
// launch.ts always passes --path=<appDir> explicitly, so running the binary from inside Contents/MacOS/ instead
// of apps/<app>/bin/ directly changes nothing about where neutralino.config.json or the app's resources are found.

import { chmodSync, copyFileSync, existsSync, mkdirSync, statSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import type { AppIdentity } from './identity.js'

export interface InfoPlistOptions {
  bundleId: string
  executableName: string
  /** The macOS-only, lower-case process identity the owner asked for (launch.ts's macProcessName doc comment has
   * the full story on scope) -- CFBundleName and CFBundleDisplayName both get it, since NSRunningApplication's
   * own name-resolution order checks CFBundleDisplayName first and falls back to CFBundleName. */
  displayName: string
}

/** The smallest Info.plist that gives an unbundled Neutralino binary a real bundle identity. No version/platform
 * keys beyond what CFBundleName's resolution actually needs -- this is not a packaging manifest, just the fix. */
export function infoPlist(options: InfoPlistOptions): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleExecutable</key>
	<string>${options.executableName}</string>
	<key>CFBundleIdentifier</key>
	<string>${options.bundleId}</string>
	<key>CFBundleName</key>
	<string>${options.displayName}</string>
	<key>CFBundleDisplayName</key>
	<string>${options.displayName}</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>LSMinimumSystemVersion</key>
	<string>10.13</string>
	<key>NSHighResolutionCapable</key>
	<true/>
</dict>
</plist>
`
}

export interface AppBundleOptions {
  /** apps/<app>/bin/ -- already holds the downloaded generic binary (npx @neutralinojs/neu update); the bundle
   * is created as a sibling inside it, so it is covered by the same .gitignore rule and the same "not checked
   * into the repo" status the binary itself already has. */
  binDir: string
  /** The real, downloaded Neutralino binary this bundle wraps a copy of (findNeutralinoBinary()'s own return
   * value, before this wrapping -- e.g. bin/neutralino-mac_arm64). */
  sourceBinary: string
  identity: AppIdentity
  displayName: string
}

function isUpToDate(source: string, target: string): boolean {
  if (!existsSync(target)) return false
  return statSync(target).mtimeMs >= statSync(source).mtimeMs
}

/** Builds (or re-uses) `<identity.name>`'s own minimal `.app` bundle under `binDir`, and returns the path to the
 * executable inside it -- what launch.ts should spawn instead of `sourceBinary` directly. The binary copy is
 * skipped once the bundle is already as new as `sourceBinary` (so a fresh `neu update` download is picked up,
 * but an ordinary launch does not re-copy a large file every time); Info.plist is cheap and rewritten every call,
 * so it always matches `identity`/`displayName` even if only those changed. */
export function ensureAppBundle(options: AppBundleOptions): string {
  const executableName = `claudia-${options.identity.name}`
  const contentsDir = join(options.binDir, `${executableName}.app`, 'Contents')
  const macOSDir = join(contentsDir, 'MacOS')
  const executablePath = join(macOSDir, executableName)

  mkdirSync(macOSDir, { recursive: true })
  if (!isUpToDate(options.sourceBinary, executablePath)) {
    copyFileSync(options.sourceBinary, executablePath)
    chmodSync(executablePath, 0o755)
  }
  writeFileSync(
    join(contentsDir, 'Info.plist'),
    infoPlist({ bundleId: options.identity.applicationId, executableName, displayName: options.displayName }),
  )
  return executablePath
}
