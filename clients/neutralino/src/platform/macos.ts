// macOS, for the native side (src/platform/host.ts): ~/Library/Application Support, a .app bundle around Neutralino's
// binary so the app's name shows, AppKit's panels through osascript, and process groups and signals for stopping.

import { userInfo } from 'node:os'
import { join } from 'node:path'
import type { HostPlatform } from './host.js'
import { ensureAppBundle } from './macos-app-bundle.js'
import { macDialogs } from './macos-dialogs.js'
import { SetupProblem } from './setup-problem.js'
import type { AppIdentity } from '../identity.js'

/** The process name macOS shows for the window (the application menu's heading, Cmd+Tab, Activity Monitor): lower
 * case, as the owner asked on 2026-11-07. `macos-app-bundle.ts` explains why this needs a bundle. */
export function macProcessName(identity: AppIdentity): string {
  return `claudia ${identity.name}`
}

/** The binary name for each Mac architecture (notes/e0-3-neutralino-windows-macos.md §5). */
export function macNeutralinoBinaryName(architecture: string): string {
  if (architecture === 'arm64') return 'neutralino-mac_arm64'
  if (architecture === 'x64') return 'neutralino-mac_x64'
  throw new SetupProblem(`no Neutralino binary is published for macOS on '${architecture}'`)
}

export const MACOS_HOST: HostPlatform = {
  id: 'macos',
  desktopName: 'Mac',
  claudiaFolder: (_env, home) => join(home, 'Library', 'Application Support', 'Claudia'),
  venvPython: ['.venv', 'bin', 'python'],
  neutralinoBinaryName: macNeutralinoBinaryName,
  coreCommandKey: 'commandDarwin',
  windowSizeInPhysicalPixels: false,
  windowBinary: (appDir, downloaded, identity, packaged) => {
    // Installed, the binary is inside the app (claudia <app>.app/Contents/MacOS/neutralino), which names it (D1626).
    if (packaged) return { binary: downloaded }
    const displayName = macProcessName(identity)
    // Running the downloaded binary as it is never gets the application's name applied (macos-app-bundle.ts has the
    // story): the smallest .app bundle around a copy of it does.
    const binary = ensureAppBundle({ binDir: join(appDir, 'bin'), sourceBinary: downloaded, identity, displayName })
    return { binary, processName: displayName }
  },
  runFolder: (app, _env, home) => join(home, 'Library', 'Caches', 'Claudia', 'run', app),
  runFolderWithSpace: 'Your home folder has a space in its path, which the window cannot be started from.',
  linkNodeIntoRun: true,
  dialogs: (log) => macDialogs(log),
  // No killTree: a detached server is the leader of its own process group, and signals reach it (server.ts sends them).
  // A Mac has no short names; a path with a space in it cannot go on the core's command line.
  shortPath: () => null,
  endTheServer: 'Or quit its Python process in Activity Monitor.',
  account: () => ({ uid: userInfo().uid }),
  sharedServiceFile: () => '/Library/Application Support/Claudia/service.json',
}
