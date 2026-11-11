// Where the shell keeps documents and state, and where it finds the bundled web frontend and the server's
// interpreter (D43). Mirrors clients/linux/src/claudia_shell_gtk/paths.py and clients/macos/src/paths.ts, but with
// Windows's own directory convention (%LOCALAPPDATA%) in place of XDG/~/Library -- the same reasoning D3 gives for
// the GTK shell matching the GNOME HIG on Linux applies here for Windows. No Neutralino import, so this is plain
// Node and testable with a temp directory.
//
// Windows has no XDG_DATA_HOME/XDG_STATE_HOME split the way Linux does (D115's paths.py keeps documents and state
// apart for that reason); like macOS's single `~/Library/Application Support`, Windows apps conventionally keep
// both under one per-app folder in %LOCALAPPDATA% (not %APPDATA%, which roams across machines on a domain-joined
// PC -- documents and server state are local to this install, the same way macOS's folder is not iCloud-synced).

import { existsSync, accessSync, constants } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export interface Env {
  [key: string]: string | undefined
}

// Every join below uses the plain, host-default 'node:path' -- the same choice clients/macos/src/paths.ts makes,
// and for the same reason: `node:path`'s default export *is* `path.win32` once this genuinely runs on Windows, so
// nothing here needs to say so explicitly, and a test built the same way (join() on both sides, see
// tests/paths.test.ts) stays correct wherever it happens to run meanwhile. Forcing `path.win32` here would only
// create a second problem: `documentsDir`/`stateDir`'s result then gets handed to real `mkdir`/`accessSync` calls
// elsewhere (launch.ts's prepareServer), which must use whatever path shape the *actual* filesystem underneath
// them understands -- deliberately disagreeing with the host there would break exactly the real-filesystem
// integration this module exists to support, in exchange for a cosmetic win on a platform this package never ships
// to host testing on anyway.

/** `%LOCALAPPDATA%`, or `<home>\AppData\Local` when it is not set (the documented fallback, and what lets this
 * run under a test or CI user whose profile Windows has not fully populated). Takes `env` rather than reading
 * `process.env` itself, the same testability choice every other function in this file makes. */
export function defaultLocalAppData(home: string = homedir(), env: Env = process.env): string {
  return env.LOCALAPPDATA ?? join(home, 'AppData', 'Local')
}

function appData(localAppData: string): string {
  return join(localAppData, 'Claudia')
}

/** Where the sealed documents of `app` are kept (the server's `--dir`). */
export function documentsDir(app: string, localAppData: string = defaultLocalAppData()): string {
  return join(appData(localAppData), app, 'documents')
}

/** Where the server of `app` keeps its own state (the server's `--state-dir`). */
export function stateDir(app: string, localAppData: string = defaultLocalAppData()): string {
  return join(appData(localAppData), app, 'state')
}

/** Where the shell keeps its own settings (`shell.json`, see settings.ts): suite-wide, not one per app, so a choice
 * made in one app is found again in the other two -- the same reasoning as the Linux client's `config_dir()`. */
export function configDir(localAppData: string = defaultLocalAppData()): string {
  return appData(localAppData)
}

/** The repository root above `start`: the nearest folder that has `clients/windows/package.json` in it, or `null`. */
export function findRepo(start: string): string | null {
  let folder = start
  for (;;) {
    if (existsSync(join(folder, 'clients', 'windows', 'package.json'))) return folder
    const parent = dirname(folder)
    if (parent === folder) return null
    folder = parent
  }
}

/** The repository this client was started from (development only; a packaged client has none). Found by walking up
 * from this file, because this code runs from three places at three depths: `src/` (tests), `dist/` (the launcher)
 * and `apps/<app>/ext/` (the core, bundled by esbuild into one file). A fixed number of levels is right for the
 * first two and wrong for the third -- the macOS client's core could not find the server's Python and the web build
 * for exactly that reason (its first run on a real Mac, 2026-11-11). The fallback is the old guess. */
export function defaultRepo(from: string = dirname(fileURLToPath(import.meta.url))): string {
  return findRepo(from) ?? resolve(from, '..', '..', '..')
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
 * Same floor as the Linux and macOS clients (D116): the server needs Python 3.14 and the Claudia packages, which
 * the interpreter this shell itself runs on (Node, not Python at all, here) has neither. `Scripts\python.exe` is
 * `uv sync`'s own layout on Windows (`bin/python` on Linux and macOS -- `venv`'s standard library module documents
 * this split; `uv` follows it), so this is the one line that cannot be copied unchanged from paths.ts. */
export function findServerPython(options: { repo?: string; env?: Env } = {}): string | null {
  const env = options.env ?? process.env
  const explicit = env.CLAUDIA_SERVER_PYTHON
  if (explicit) return explicit
  const candidate = join(options.repo ?? defaultRepo(), '.venv', 'Scripts', 'python.exe')
  try {
    accessSync(candidate, constants.X_OK)
    return candidate
  } catch {
    return null
  }
}
