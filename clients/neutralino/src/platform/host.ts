// What the native side of the client does differently on macOS and on Windows (D660): where it keeps its folders,
// how it finds the server's Python and Neutralino's binary, how it shows a dialog, how it ends a server and everything
// that server started, and the words a person reads for the two. Everything else in this package is the same on both.
// The page's side is src/platform/page.ts.

import type { Dialogs } from '../files.js'
import type { AppIdentity } from '../identity.js'
import type { Account } from '../private-port.js'
import { platformId, type PlatformId } from './id.js'
import { MACOS_HOST } from './macos.js'
import { WINDOWS_HOST } from './windows.js'

export interface Env {
  [key: string]: string | undefined
}

/** The binary Neutralino's window is started from, and the name its process gets. */
export interface WindowBinary {
  binary: string
  /** What the process is called (`argv0`); `undefined`: the binary's own name. */
  processName?: string
}

export interface HostPlatform {
  readonly id: PlatformId
  /** "Mac", "Windows": in "for the Mac desktop" and "for this Mac". */
  readonly desktopName: string
  /** The folder of the suite's own files for this person: documents, state, settings and logs live underneath. */
  claudiaFolder(env: Env, home: string): string
  /** Where `uv sync` puts the interpreter of a checkout's .venv, as path parts under the checkout. */
  readonly venvPython: readonly string[]
  /** The file name of Neutralino's binary for this computer's processor; a `SetupProblem` where none is published. */
  neutralinoBinaryName(architecture: string): string
  /** The key of the core's command in neutralino.config.json's extension (Neutralino reads one per operating system). */
  readonly coreCommandKey: 'commandDarwin' | 'commandWindows'
  /** Whether Neutralino takes the window's size in physical pixels, so the config's size must be asked for in logical
   * ones to show the whole page on a scaled display (Windows; macOS sizes windows in points already; D749). */
  readonly windowSizeInPhysicalPixels: boolean
  /** The binary a checkout's window is started from: on macOS a small .app bundle around the downloaded one, so the
   * app's name shows; on Windows the downloaded binary itself. (An installed app's is taken as it is: launch.ts.) */
  windowBinary(appDir: string, downloaded: string, identity: AppIdentity): WindowBinary
  /** Where a packaged client's window of `app` runs from, a fresh copy at every start (src/packaged.ts). */
  runFolder(app: string, env: Env, home: string): string
  /** What to do when that folder has a space in its path, which the core's command line cannot hold, in words. */
  readonly runFolderWithSpace: string
  /** Whether the core is started through a link to node in the run folder, because node's own path has a space and
   * there is no short name (macOS: `/Library/Application Support/…`, E8.5). */
  readonly linkNodeIntoRun: boolean
  /** The Open and Save dialogs and the viewer that prints (D501, D502). */
  dialogs(log?: (message: string) => void): Dialogs
  /** Ends the process `pid` and everything it started (`false`: it could not); absent where signals to the process
   * group do that (POSIX). */
  readonly killTree?: (pid: number) => Promise<boolean>
  /** A short name for a path with a space in it, which Neutralino can put on the core's command line; `null`: none. */
  shortPath(path: string): string | null
  /** How a person stops a server that will not go, in words. */
  readonly endTheServer: string
  /** Who she is on this computer, which her private server's port follows (private-port.ts, E8.5, D1621): her account
   * number on a Mac, her profile folder (`home`) on Windows, which has no account numbers. */
  account(home: string): Account
  /** Where the installer of the computer's service writes the service file (shared-service.ts, E8.5, D1622). */
  sharedServiceFile(env: Env): string
}

/** The host platform of this build (src/platform/id.ts). */
export function hostPlatform(id: PlatformId = platformId()): HostPlatform {
  return id === 'windows' ? WINDOWS_HOST : MACOS_HOST
}
