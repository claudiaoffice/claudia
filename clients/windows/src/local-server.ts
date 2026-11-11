// Putting a local server together for an app, or saying plainly what is missing. Port of clients/linux/src/
// claudia_shell_gtk/launch.py's `prepare_server`, the same as clients/macos/src/local-server.ts apart from the folders
// (paths.ts) and the interpreter's place. No Neutralino import.
//
// A shell needs two things from outside itself: the Python 3.14 that runs the server and the built web frontend.
// Both are looked up (paths.ts); if one is missing the person gets a message that names it and the way to fix it,
// instead of an empty window.

import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'
import { env as processEnv } from 'node:process'
import { getIdentity } from './identity.js'
import { documentsDir, findFrontend, findServerPython, stateDir, type Env } from './paths.js'
import { LOOPBACK, LocalServer, buildServerCommand, freePort } from './server.js'

/** Something the shell needs is not there. The message is written for the person who starts the app. */
export class SetupProblem extends Error {}

export interface PrepareServerOptions {
  repo?: string
  /** `%LOCALAPPDATA%`, for a test; see paths.ts. */
  localAppData?: string
  env?: Env
}

/** A `LocalServer` for `app`, not started yet. */
export async function prepareServer(app: string, options: PrepareServerOptions = {}): Promise<LocalServer> {
  const env = options.env ?? processEnv
  const identity = getIdentity(app)
  const python = findServerPython({ repo: options.repo, env })
  if (python === null) {
    throw new SetupProblem(
      "Claudia's server needs Python 3.14, and none was found.\n" +
        'Set CLAUDIA_SERVER_PYTHON to the interpreter of an environment where Claudia is installed ' +
        "(in a checkout: run 'uv sync --no-dev' and the interpreter is .venv\\Scripts\\python.exe).",
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
  const documents = documentsDir(identity.name, options.localAppData)
  const state = stateDir(identity.name, options.localAppData)
  await mkdir(documents, { recursive: true })
  await mkdir(state, { recursive: true })
  const port = await freePort()
  const command = buildServerCommand(python, { model: identity.model, port, documents, web, state })
  return new LocalServer(command, { url: `http://${LOOPBACK}:${port}`, log: join(state, 'server.log') })
}
