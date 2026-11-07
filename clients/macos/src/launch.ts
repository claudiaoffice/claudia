// Putting a local server together for an app, finding the Neutralino binary, and the command line that starts it
// pointed at that server's own loopback page -- D159 option 2, the user's explicit choice over serving Neutralino's
// own bundle cross-origin. Mirrors clients/linux/src/claudia_shell_gtk/launch.py's prepare_server() (same two
// SetupProblem messages, same "documents/state folders exist before the server starts"), plus two pieces Linux has
// no equivalent of: GTK *is* the Linux shell process, but Neutralino is a separate compiled binary this launcher
// has to locate (findNeutralinoBinary) and start with the right flags (buildShellCommand). Those flags --
// `--url`, `--path`, `--enable-server` -- are confirmed against Neutralino's own "internal CLI arguments" docs;
// whether `injectGlobals`/`injectClientLibrary`/`injectScript` (set in apps/<app>/neutralino.config.json, not
// here -- `--path` just points the binary at that file) actually take effect on a page loaded from an *external*
// URL is D159's one open question, not something this module can settle. See this package's README.

import { accessSync, constants } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import { spawn as nodeSpawn } from 'node:child_process'
import { join } from 'node:path'
import { arch as hostArch, env as processEnv } from 'node:process'
import { getIdentity, UnknownAppError, type App } from './identity.js'
import { defaultRepo, documentsDir, findFrontend, findServerPython, stateDir, type Env } from './paths.js'
import { LOOPBACK, LocalServer, buildServerCommand, freePort } from './server.js'

export class SetupProblem extends Error {}

export interface PrepareServerOptions {
  repo?: string
  home?: string
  env?: Env
}

/** A LocalServer for `app`, not started yet -- same contract as launch.py's prepare_server(): say plainly what is
 * missing (and how to fix it) rather than handing back an empty window. */
export async function prepareServer(app: App, options: PrepareServerOptions = {}): Promise<LocalServer> {
  const env = options.env ?? processEnv
  const python = findServerPython({ repo: options.repo, env })
  if (python === null) {
    throw new SetupProblem(
      "Claudia's server needs Python 3.14, and none was found.\n" +
        'Set CLAUDIA_SERVER_PYTHON to the interpreter of an environment where Claudia is installed ' +
        "(in a checkout: run 'uv sync' and the interpreter is .venv/bin/python).",
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
  const documents = documentsDir(identity.name, options.home)
  const state = stateDir(identity.name, options.home)
  await mkdir(documents, { recursive: true })
  await mkdir(state, { recursive: true })
  const port = await freePort()
  const command = buildServerCommand(python, { model: identity.model, port, documents, web, state })
  return new LocalServer(command, { url: `http://${LOOPBACK}:${port}` })
}

/** The binary name the spike settled on for each Mac architecture (notes/e0-3-neutralino-windows-macos.md §5). */
export function neutralinoBinaryName(architecture: string = hostArch): string {
  if (architecture === 'arm64') return 'neutralino-mac_arm64'
  if (architecture === 'x64') return 'neutralino-mac_x64'
  throw new SetupProblem(`no Neutralino binary is published for macOS on '${architecture}'`)
}

export interface FindNeutralinoBinaryOptions {
  /** apps/<app>/, where the binary is conventionally placed next to neutralino.config.json (not checked into the
   * repo -- D157 pins the binary and client-library versions together, re-checked on every upgrade). */
  appDir: string
  env?: Env
  arch?: string
}

/** `$CLAUDIA_NEUTRALINO_BIN`, else `<appDir>/neutralino-mac_<arch>` if it exists and is executable, else `null` --
 * same shape as paths.ts's findServerPython: an explicit override is trusted as-is, a wrong default is reported by
 * main() rather than silently skipped. */
export function findNeutralinoBinary(options: FindNeutralinoBinaryOptions): string | null {
  const env = options.env ?? processEnv
  const explicit = env.CLAUDIA_NEUTRALINO_BIN
  if (explicit) return explicit
  const candidate = join(options.appDir, neutralinoBinaryName(options.arch))
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
 * in effect. `--enable-server=true` is Neutralino's own documented requirement for loading a remote/external URL
 * at all (the native-API/WebSocket channel the injected script depends on). */
export function buildShellCommand(binary: string, options: ShellCommandOptions): string[] {
  return [binary, `--path=${options.appDir}`, `--url=${options.url}`, '--enable-server=true']
}

/** Starts `app` end to end: the local server, then the Neutralino binary pointed at it, then waits for the window
 * to close and stops the server. The untested half of this module -- the real binary spawn and exit wait -- is
 * this launcher's equivalent of the GTK main loop launch.py leaves to Application.run(): wiring that needs a real
 * window, not a unit test. Returns the process exit code. */
export async function main(argv: readonly string[]): Promise<number> {
  const appName = (argv[0] ?? 'creates') as App
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
    console.error(`'${appName}' has no macOS client yet -- this first version only covers creates (E5.11).`)
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

  const appDir = join(defaultRepo(), 'clients', 'macos', 'apps', appName)
  const binary = findNeutralinoBinary({ appDir })
  if (binary === null) {
    console.error(
      `No Neutralino binary found for this Mac.\n` +
        `Set CLAUDIA_NEUTRALINO_BIN to its path, or place ${neutralinoBinaryName()} in ${appDir}\n` +
        '(D157: pin it to the same version as the client library in neutralino.config.json, 6.8.0 today).',
    )
    return 1
  }

  const url = await server.start()
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

// Run directly (`node dist/launch.js creates`) rather than only imported, matching launch.py's own
// `if __name__ == "__main__"` guard.
if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).then((code) => {
    process.exitCode = code
  })
}
