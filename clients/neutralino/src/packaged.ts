// The packaged client (D741): the windows of a client that an installer put on a computer.
//
// In a checkout the launcher finds everything relative to the repository. An installed client has a marker,
// `packaged.json`, next to `apps/` and `dist/` (the installer's build writes it), which says where the installer put the
// web frontend and the self-contained server (D740). With it the launcher
//   - hands those two to the core as CLAUDIA_WEB_DIR and CLAUDIA_SERVER_EXE (unless the person set their own), and
//   - runs the window from a copy of the app's folder in the person's own folder (`stageApp`): the launcher writes the
//     core's command into neutralino.config.json for the run, and an installation in `Program Files` is read-only for
//     a person who is not an administrator, and has a space in its name, which Neutralino cannot pass to the core.
// No Neutralino import, so this is plain Node and testable with a temp directory.

import { cpSync, mkdirSync, readFileSync, realpathSync, rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import type { Env } from './platform/host.js'

/** In the client's folder, beside `apps/`: `{"web": "../web", "server": "../server/claudia-server.exe"}`, relative to it. */
export const PACKAGED_FILE = 'packaged.json'

/** Where the installer put what the client needs besides itself, as absolute paths. */
export interface Packaged {
  web: string
  server: string
}

/** What the marker of the client that owns `appDir` (`<client>/apps/<app>`) says, or `null` in a checkout, which has no
 * marker. A marker that cannot be read is an error that says so: the person would otherwise get a window that starts
 * the wrong server, or none. */
export function readPackaged(appDir: string): Packaged | null {
  const client = dirname(dirname(appDir))
  const file = join(client, PACKAGED_FILE)
  let text: string
  try {
    text = readFileSync(file, 'utf8')
  } catch {
    return null
  }
  let found: unknown
  try {
    found = JSON.parse(text)
  } catch {
    throw new Error(`${file} is not JSON; reinstall Claudia.`)
  }
  const { web, server } = (found ?? {}) as { web?: unknown; server?: unknown }
  if (typeof found !== 'object' || typeof web !== 'string' || typeof server !== 'string') {
    throw new Error(`${file} must say where the web frontend and the server are ({"web": ..., "server": ...}); reinstall Claudia.`)
  }
  return { web: resolve(client, web), server: resolve(client, server) }
}

/** The variables the core reads to find the frontend and the server. What the person has set stays: an own server or
 * frontend wins, in whatever spelling of the name (variable names are not case-sensitive on Windows). */
export function packagedEnvironment(packaged: Packaged, base: Env): Record<string, string> {
  const has = (name: string): boolean => Object.keys(base).some((key) => key.toUpperCase() === name && base[key] !== undefined)
  const own = ['CLAUDIA_SERVER_EXE', 'CLAUDIA_SERVER_PYTHON'].some(has)
  return {
    ...(has('CLAUDIA_WEB_DIR') ? {} : { CLAUDIA_WEB_DIR: packaged.web }),
    ...(own ? {} : { CLAUDIA_SERVER_EXE: packaged.server }),
  }
}

/** A copy of the app's folder at `target`, without `bin/` (Neutralino's binary is started from where it is installed).
 * What was at `target` is removed first, so a file of an older version never stays. */
export function stageApp(appDir: string, target: string): void {
  if (resolve(appDir) === resolve(target) || realpathOrSelf(appDir) === realpathOrSelf(target)) {
    throw new Error(`cannot stage ${appDir} into the same folder`)
  }
  rmSync(target, { recursive: true, force: true })
  mkdirSync(target, { recursive: true })
  cpSync(appDir, target, { recursive: true, filter: (source) => resolve(source) !== resolve(appDir, 'bin') })
}

function realpathOrSelf(path: string): string {
  try {
    return realpathSync(path)
  } catch {
    return resolve(path)
  }
}
