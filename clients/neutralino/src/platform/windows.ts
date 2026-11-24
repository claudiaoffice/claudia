// Windows, for the native side (src/platform/host.ts): %LOCALAPPDATA%, the one x64 binary of Neutralino, the common
// file dialogs through PowerShell, taskkill for a server's whole process tree, and 8.3 short names for the path of
// node, which usually has a space in it (`C:\Program Files\nodejs\node.exe`).
//
// Two things here ask the operating system the code runs on rather than the platform it was built for: taskkill and
// the short names exist only on Windows itself, and a Windows build is also run on Linux (the e2e job in CI).

import { spawn as nodeSpawn, spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { env as processEnv, platform as osPlatform } from 'node:process'
import type { HostPlatform } from './host.js'
import { windowsDialogs } from './windows-dialogs.js'

/** `taskkill /pid <pid> /T /F`: the tree, forcibly -- there is no gentler signal on Windows (server.ts's top comment).
 * `windowsHide`, because a console tool started from a GUI process gets its own window otherwise. `false` where this is
 * not Windows, taskkill is missing, or it did not know the pid: the caller then falls back to `kill()`. */
export function killProcessTree(pid: number, os: string = osPlatform): Promise<boolean> {
  if (os !== 'win32') return Promise.resolve(false)
  return new Promise((resolve) => {
    try {
      const killer = nodeSpawn('taskkill', ['/pid', String(pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true })
      killer.once('error', () => resolve(false))
      killer.once('exit', (code) => resolve(code === 0))
    } catch {
      resolve(false)
    }
  })
}

/** The 8.3 short name of a path (`C:\PROGRA~1\nodejs\node.exe`), or `null` when there is none (short names can be
 * switched off per volume) or this is not Windows. Asked of `cmd`, whose `%~sI` is the documented way. */
export function shortPathOf(path: string, os: string = osPlatform): string | null {
  if (os !== 'win32' || /["%]/.test(path)) return null
  try {
    const done = spawnSync(processEnv.ComSpec ?? 'cmd.exe', ['/d', '/c', `for %I in ("${path}") do @echo %~sI`], {
      encoding: 'utf8',
      windowsHide: true,
      windowsVerbatimArguments: true,
      timeout: 5000,
    })
    if (done.status !== 0) return null
    const short = done.stdout.trim().split(/\r?\n/).pop()?.trim() ?? ''
    return short === '' ? null : short
  } catch {
    return null
  }
}

/** `%LOCALAPPDATA%`, or `<home>\AppData\Local` when it is not set (the documented fallback, and what lets this run
 * under a test or CI user whose profile Windows has not fully populated). Not `%APPDATA%`, which roams across machines
 * on a domain-joined PC: documents and server state are local to this install, as macOS's folder is not iCloud-synced. */
export function localAppData(env: { [key: string]: string | undefined }, home: string): string {
  return env.LOCALAPPDATA ?? join(home, 'AppData', 'Local')
}

export const WINDOWS_HOST: HostPlatform = {
  id: 'windows',
  desktopName: 'Windows',
  claudiaFolder: (env, home) => join(localAppData(env, home), 'Claudia'),
  venvPython: ['.venv', 'Scripts', 'python.exe'],
  // Neutralino 6.8.0 publishes exactly one Windows binary (notes/e0-3-neutralino-windows-macos.md §5): the x64 one,
  // which also runs on Windows on ARM.
  neutralinoBinaryName: () => 'neutralino-win_x64.exe',
  coreCommandKey: 'commandWindows',
  windowSizeInPhysicalPixels: true,
  // No .app bundle: the taskbar and the title bar read the title from the config (notes/e5-11-windows-client.md).
  windowBinary: (_appDir, downloaded) => ({ binary: downloaded }),
  dialogs: () => windowsDialogs(),
  killTree: (pid) => killProcessTree(pid),
  shortPath: (path) => shortPathOf(path),
  endTheServer: 'Or end its python.exe in the Task Manager.',
}
