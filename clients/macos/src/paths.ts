// Where the shell keeps documents and state, and where it finds the bundled web frontend and the server's
// interpreter (D43). Mirrors clients/linux/src/claudia_shell_gtk/paths.py, but with macOS's own directory
// convention (~/Library/Application Support) in place of XDG -- the same reasoning D3 gives for the GTK shell
// matching the GNOME HIG on Linux applies here for macOS. No Neutralino import, so this is plain Node and testable
// with a temp directory.

import { existsSync, accessSync, constants } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export interface Env {
  [key: string]: string | undefined
}

function appSupport(home: string): string {
  return join(home, 'Library', 'Application Support', 'Claudia')
}

/** Where the sealed documents of `app` are kept (the server's `--dir`). */
export function documentsDir(app: string, home: string = homedir()): string {
  return join(appSupport(home), app, 'documents')
}

/** Where the server of `app` keeps its own state (the server's `--state-dir`). */
export function stateDir(app: string, home: string = homedir()): string {
  return join(appSupport(home), app, 'state')
}

/** The repository this client was started from (development only; a packaged client has none). Four levels up
 * from this file (src/paths.ts -> src -> macos -> clients -> repo root), the same depth paths.py counts from
 * claudia_shell_gtk/paths.py. */
export function defaultRepo(): string {
  const here = dirname(fileURLToPath(import.meta.url))
  return resolve(here, '..', '..', '..')
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
 * interpreter this shell itself runs on (Node, not Python at all, here) has neither. */
export function findServerPython(options: { repo?: string; env?: Env } = {}): string | null {
  const env = options.env ?? process.env
  const explicit = env.CLAUDIA_SERVER_PYTHON
  if (explicit) return explicit
  const candidate = join(options.repo ?? defaultRepo(), '.venv', 'bin', 'python')
  try {
    accessSync(candidate, constants.X_OK)
    return candidate
  } catch {
    return null
  }
}
