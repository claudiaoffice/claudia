// Putting the local server together for an app's window, or saying plainly what is missing. Since D445 it is one
// server for the three apps, found or started by desktop-server.ts; this module checks what it needs (the Python 3.14
// that runs it, the built web frontend), makes its folders and hands over a `DesktopServer` that is not started yet.
// The twin of clients/windows/src/local-server.ts. No Neutralino import.
//
// A shell needs two things from outside itself: the Python 3.14 that runs the server and the built web frontend.
// Both are looked up (paths.ts); if one is missing the person gets a message that names it and the way to fix it,
// instead of an empty window.

import { mkdir } from 'node:fs/promises'
import { env as processEnv } from 'node:process'
import { DesktopServer, type DesktopServerOptions } from './desktop-server.js'
import { getIdentity } from './identity.js'
import { findFrontend, findServerPython, serverDocumentsDir, serverStateDir, type Env } from './paths.js'

/** Something the shell needs is not there. The message is written for the person who starts the app. */
export class SetupProblem extends Error {}

export interface PrepareServerOptions {
  repo?: string
  /** The home folder, for a test; see paths.ts. */
  home?: string
  env?: Env
  log?: (message: string) => void
  /** What the tests replace in the server (health check, start, ports, presence). */
  seams?: Partial<DesktopServerOptions>
}

/** The shared local server for `app`'s window, not started yet. */
export async function prepareServer(app: string, options: PrepareServerOptions = {}): Promise<DesktopServer> {
  const env = options.env ?? processEnv
  const identity = getIdentity(app)
  const python = findServerPython({ repo: options.repo, env })
  if (python === null) {
    throw new SetupProblem(
      "Claudia's server needs Python 3.14, and none was found.\n" +
        'Set CLAUDIA_SERVER_PYTHON to the interpreter of an environment where Claudia is installed ' +
        "(in a checkout: run 'uv sync --no-dev' and the interpreter is .venv/bin/python).",
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
  const documents = serverDocumentsDir(options.home)
  const state = serverStateDir(options.home)
  await mkdir(documents, { recursive: true })
  await mkdir(state, { recursive: true })
  // CLAUDIA_SERVER_PORT: another port than 8765 (D504), for a person who needs 8765 for something else, and for tests.
  const port = Number.parseInt(env.CLAUDIA_SERVER_PORT ?? '', 10)
  return new DesktopServer({
    app: identity.name,
    python,
    web,
    documents,
    state,
    log: options.log,
    ...(port > 0 && port < 65536 ? { port } : {}),
    ...options.seams,
  })
}
