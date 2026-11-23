// Where the shell keeps documents and state, and where it finds the bundled web frontend and the server's
// interpreter (D43). Mirrors clients/linux/src/claudia_shell_gtk/paths.py, but with the operating system's own folder
// in place of XDG (~/Library/Application Support on a Mac, %LOCALAPPDATA% on Windows; src/platform/), the same
// reasoning D3 gives for the GTK shell matching the GNOME HIG on Linux. No Neutralino import, so this is plain Node
// and testable with a temp directory.

import { existsSync, accessSync, constants } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { hostPlatform, type Env, type HostPlatform } from './platform/host.js'
import type { ServerProgram } from './server.js'

export type { Env }

/** The folder of the suite's own files for this person (`~/Library/Application Support/Claudia`,
 * `%LOCALAPPDATA%\Claudia`): everything below lives underneath. */
export function claudiaFolder(platform: HostPlatform = hostPlatform(), env: Env = process.env, home: string = homedir()): string {
  return platform.claudiaFolder(env, home)
}

/** Where the sealed documents of all three apps are kept (the server's `--dir`; the server puts each app's into a
 * folder of its own, D431). One folder for the suite, because the three desktop apps share one local server (D445). */
export function serverDocumentsDir(folder: string = claudiaFolder()): string {
  return join(folder, 'documents')
}

/** Where the local server keeps its own state (the server's `--state-dir`), together with `desktop-server.json`, which
 * remembers its port, and its `server.log`. One folder for the suite (D445). */
export function serverStateDir(folder: string = claudiaFolder()): string {
  return join(folder, 'state')
}

/** Where the shell of `app` keeps its own log (`shell.log`): not the server's, which the three apps share. */
export function stateDir(app: string, folder: string = claudiaFolder()): string {
  return join(folder, app, 'state')
}

/** Where the shell keeps its own settings (`shell.json`, see settings.ts): suite-wide, not one per app, so a choice
 * made in one app is found again in the other two -- the same reasoning as the Linux client's `config_dir()`. */
export function configDir(folder: string = claudiaFolder()): string {
  return folder
}

/** The repository root above `start`: the nearest folder that has `clients/neutralino/package.json` in it, or `null`. */
export function findRepo(start: string): string | null {
  let folder = start
  for (;;) {
    if (existsSync(join(folder, 'clients', 'neutralino', 'package.json'))) return folder
    const parent = dirname(folder)
    if (parent === folder) return null
    folder = parent
  }
}

/** The repository this client was started from (development only; a packaged client has none). Found by walking up
 * from this file, because this code runs from three places at three depths: `src/` (tests), `dist/` (the launcher)
 * and `apps/<app>/ext/` (the core, bundled by esbuild into one file). A fixed number of levels was right for the
 * first two and wrong for the third, which made the core look for the server's Python and the web build in
 * `clients/macos` (found by the first run of a local server on a real Mac, 2026-11-11). The fallback is the old guess. */
export function defaultRepo(from: string = dirname(fileURLToPath(import.meta.url))): string {
  return findRepo(from) ?? resolve(from, '..', '..', '..')
}

/** The folder of the window of `app`: `apps/<app>` beside the folder this code runs from (`dist/`, or `src/` in the tests),
 * in a checkout (`clients/neutralino`) and in an installation (`<install>\client`) alike (D746). */
export function appFolder(app: string, from: string = dirname(fileURLToPath(import.meta.url))): string {
  return join(dirname(from), 'apps', app)
}

function isFrontend(folder: string | null): folder is string {
  return folder !== null && existsSync(join(folder, 'index.html'))
}

/**
 * The folder with the built web frontend the local server will serve, or `null`. In this order:
 * `CLAUDIA_WEB_DIR` (the only candidate when set -- a wrong path is reported, never quietly replaced), the
 * frontend shipped inside the packaged app, and the build of a development checkout (`web/.output/public`).
 */
export function findFrontend(
  options: { repo?: string; packaged?: string | null; env?: Env } = {},
): string | null {
  const env = options.env ?? process.env
  const explicit = env.CLAUDIA_WEB_DIR
  if (explicit) return isFrontend(explicit) ? explicit : null
  const shipped = options.packaged ?? null // set once this client is actually packaged; nothing ships it yet
  if (isFrontend(shipped)) return shipped
  const checkout = join(options.repo ?? defaultRepo(), 'web', '.output', 'public')
  return isFrontend(checkout) ? checkout : null
}

/** The interpreter that runs the server: `$CLAUDIA_SERVER_PYTHON`, else the repository's `.venv`, else `null`.
 * Same floor as the Linux client (D116): the server needs Python 3.14 and the Claudia packages, which the
 * interpreter this shell itself runs on (Node, not Python at all, here) has neither. Where `uv sync` puts the
 * interpreter is the platform's: `bin/python`, or `Scripts\python.exe` on Windows. */
export function findServerPython(options: { repo?: string; env?: Env; platform?: HostPlatform } = {}): string | null {
  const env = options.env ?? process.env
  const explicit = env.CLAUDIA_SERVER_PYTHON
  if (explicit) return explicit
  const candidate = join(options.repo ?? defaultRepo(), ...(options.platform ?? hostPlatform()).venvPython)
  try {
    accessSync(candidate, constants.X_OK)
    return candidate
  } catch {
    return null
  }
}

/** What starts the server: `$CLAUDIA_SERVER_EXE` (the self-contained server of the Windows installer, D740; as-is, like
 * `CLAUDIA_SERVER_PYTHON`, so a wrong path fails where it is spawned and says so), else the interpreter of
 * `findServerPython`, else `null`. */
export function findServerProgram(options: { repo?: string; env?: Env; platform?: HostPlatform } = {}): ServerProgram | null {
  const exe = (options.env ?? process.env).CLAUDIA_SERVER_EXE
  if (exe) return { exe }
  return findServerPython(options)
}
