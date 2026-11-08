// Putting a local server together for an app, finding the Neutralino binary, and the command line that starts it
// pointed at that server's own loopback page -- D159 option 2, the same choice the owner made explicitly for
// macOS, now carried over to Windows rather than asked again: the transport question was "how does a Neutralino
// shell reach the frontend", not "how does a *macOS* Neutralino shell reach it", and nothing in the spike or the
// build found a platform split in the answer. Mirrors clients/macos/src/launch.ts, itself mirroring
// clients/linux/src/claudia_shell_gtk/launch.py's prepare_server() (same two SetupProblem messages, same
// "documents/state folders exist before the server starts").
//
// Unlike macOS, there is no app-bundle.ts step here: that module exists purely to fix a CFBundleName problem (the
// macOS Dock and menu-bar heading read a bundle's Info.plist, not argv0) that has no Windows equivalent -- the
// taskbar and the window's own title bar both read `neutralino.config.json`'s `modes.window.title`, which this
// client already sets per app, same as it always did on Linux and macOS.

import { accessSync, constants } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import { spawn as nodeSpawn } from 'node:child_process'
import { join } from 'node:path'
import { env as processEnv } from 'node:process'
import { getIdentity, UnknownAppError, type App } from './identity.js'
import { defaultRepo, documentsDir, findFrontend, findServerPython, stateDir, type Env } from './paths.js'
import { LOOPBACK, LocalServer, ServerStartError, buildServerCommand, freePort } from './server.js'

export class SetupProblem extends Error {}

export interface PrepareServerOptions {
  repo?: string
  localAppData?: string
  env?: Env
}

/** A LocalServer for `app`, not started yet -- same contract as launch.py's and the macOS launch.ts's
 * prepareServer(): say plainly what is missing (and how to fix it) rather than handing back an empty window. */
export async function prepareServer(app: App, options: PrepareServerOptions = {}): Promise<LocalServer> {
  const env = options.env ?? processEnv
  const python = findServerPython({ repo: options.repo, env })
  if (python === null) {
    throw new SetupProblem(
      "Claudia's server needs Python 3.14, and none was found.\n" +
        'Set CLAUDIA_SERVER_PYTHON to the interpreter of an environment where Claudia is installed ' +
        "(in a checkout: run 'uv sync' and the interpreter is .venv\\Scripts\\python.exe).",
    )
  }
  const web = findFrontend({ repo: options.repo, env })
  if (web === null) {
    const wrong = env.CLAUDIA_WEB_DIR
    throw new SetupProblem(
      wrong
        ? `CLAUDIA_WEB_DIR is set to ${wrong}, but there is no built frontend (index.html) in it.`
        : "The web frontend has not been built.\nBuild it ('npm run build' in the web folder) or set CLAUDIA_WEB_DIR to a folder that holds it.",
    )
  }
  const identity = getIdentity(app)
  const documents = documentsDir(identity.name, options.localAppData)
  const state = stateDir(identity.name, options.localAppData)
  await mkdir(documents, { recursive: true })
  await mkdir(state, { recursive: true })
  const port = await freePort()
  const command = buildServerCommand(python, { model: identity.model, port, documents, web, state })
  return new LocalServer(command, { url: `http://${LOOPBACK}:${port}`, log: join(state, 'server.log') })
}

/** The one binary name Neutralino 6.8.0 publishes for Windows (notes/e0-3-neutralino-windows-macos.md §5: "and the
 * Linux ones, not used" lists no separate win_arm64 either) -- unlike macOS's `neutralinoBinaryName`, there is no
 * architecture branch here, because there is nothing to branch on yet. If Neutralino ever publishes a Windows ARM64
 * binary this becomes wrong silently rather than loudly, same trade-off the macOS function's own doc comment
 * accepts for an unpublished macOS architecture. */
export function neutralinoBinaryName(): string {
  return 'neutralino-win_x64.exe'
}

export interface FindNeutralinoBinaryOptions {
  /** apps/<app>/, the project `neu update` (or `neu run`) is pointed at -- it writes the binary into `bin/`
   * underneath this, not into this folder directly (confirmed against the E0.3 spike's own `run_windows.cmd`,
   * which downloads with `npx @neutralinojs/neu update` and then runs `bin\neutralino-win_x64.exe`). Not checked
   * into the repo -- D157 pins the binary and client-library versions together, re-checked on every upgrade. */
  appDir: string
  env?: Env
}

/** `$CLAUDIA_NEUTRALINO_BIN`, else `<appDir>\bin\neutralino-win_x64.exe` if it exists, else `null` -- same shape as
 * paths.ts's findServerPython and the macOS client's findNeutralinoBinary: an explicit override is trusted as-is,
 * a wrong default is reported by main() rather than silently skipped. `constants.X_OK` is accepted on Windows (the
 * file just needs to exist and be readable; Windows has no execute bit), the same assumption findServerPython
 * already makes for python.exe. */
export function findNeutralinoBinary(options: FindNeutralinoBinaryOptions): string | null {
  const env = options.env ?? processEnv
  const explicit = env.CLAUDIA_NEUTRALINO_BIN
  if (explicit) return explicit
  const candidate = join(options.appDir, 'bin', neutralinoBinaryName())
  try {
    accessSync(candidate, constants.X_OK)
    return candidate
  } catch {
    return null
  }
}

export interface ShellCommandOptions {
  /** Where the document server's own loopback page already is (LocalServer.url after start()). */
  url: string
  /** apps/<app>/ -- `--path` so the binary still reads this app's neutralino.config.json, icon and injected
   * script, even though the *page* it shows comes from `url`, not from anything under this folder. */
  appDir: string
}

/** The Neutralino binary's own command line for D159 option 2: load the document server's loopback page instead
 * of anything Neutralino ships, while `--path` keeps this app's own config (and the injection settings inside it)
 * in effect. Identical to macOS's buildShellCommand -- these flags are Neutralino's own, not OS-specific. */
export function buildShellCommand(binary: string, options: ShellCommandOptions): string[] {
  return [binary, `--path=${options.appDir}`, `--url=${options.url}`, '--enable-server=true']
}

/** Starts `app` end to end: the local server, then the Neutralino binary pointed at it, then waits for the window
 * to close and stops the server. The untested half of this module -- the real binary spawn and exit wait -- is
 * this launcher's equivalent of the GTK main loop launch.py leaves to Application.run(): wiring that needs a real
 * window, not a unit test. Returns the process exit code. */
export async function main(argv: readonly string[]): Promise<number> {
  const appName = (argv[0] ?? 'composes') as App
  let identity
  try {
    identity = getIdentity(appName)
  } catch (error) {
    if (error instanceof UnknownAppError) {
      console.error(error.message)
      return 1
    }
    throw error
  }
  if (!identity.packaged) {
    console.error(`'${appName}' has no Windows client yet -- this first version only covers composes.`)
    return 1
  }

  let server: LocalServer
  try {
    server = await prepareServer(appName)
  } catch (error) {
    if (error instanceof SetupProblem) {
      console.error(error.message)
      return 1
    }
    throw error
  }

  const appDir = join(defaultRepo(), 'clients', 'windows', 'apps', appName)
  const binary = findNeutralinoBinary({ appDir })
  if (binary === null) {
    console.error(
      `No Neutralino binary found for Windows (expected ${join(appDir, 'bin', neutralinoBinaryName())}).\n` +
        `Fetch it with: cd ${appDir} && npx @neutralinojs/neu update\n` +
        '(reads neutralino.config.json\'s pinned cli.binaryVersion, 6.8.0 today -- D157).\n' +
        'Or set CLAUDIA_NEUTRALINO_BIN to an existing binary\'s path.',
    )
    return 1
  }

  let url: string
  try {
    url = await server.start()
  } catch (error) {
    if (error instanceof ServerStartError) {
      console.error(error.message)
      return 1
    }
    throw error
  }
  const [shellBinary, ...shellArgs] = buildShellCommand(binary, { url, appDir })
  if (!shellBinary) throw new Error('empty shell command') // unreachable: buildShellCommand always returns at least the binary
  const shell = nodeSpawn(shellBinary, shellArgs, { stdio: 'inherit' })

  const exitCode = await new Promise<number>((resolve) => {
    shell.once('exit', (code) => resolve(code ?? 0))
    shell.once('error', () => resolve(1))
  })
  await server.stop()
  return exitCode
}

// Run directly (`node dist/launch.js composes`) rather than only imported, matching launch.py's and the macOS
// launch.ts's own `if __name__ == "__main__"`/import.meta.url guard.
if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).then((code) => {
    process.exitCode = code
  })
}
