// Putting the local server together for an app's window, or saying plainly what is missing. It is her private server,
// one for her three apps (D445, E8.5), found or started by private-server.ts; this module checks what it needs (the
// Python 3.14 that runs it, the built web frontend), makes its folders and hands over a `PrivateServer` not started yet.
// No Neutralino import.
//
// A shell needs two things from outside itself: the Python 3.14 that runs the server and the built web frontend.
// Both are looked up (paths.ts); if one is missing the person gets a message that names it and the way to fix it,
// instead of an empty window.

import { mkdir } from 'node:fs/promises'
import { homedir } from 'node:os'
import { env as processEnv } from 'node:process'
import { PrivateServer, type PrivateServerOptions } from './private-server.js'
import { getIdentity } from './identity.js'
import { claudiaFolder, findFrontend, findServerProgram, serverDocumentsDir, serverStateDir, type Env } from './paths.js'
import { hostPlatform, type HostPlatform } from './platform/host.js'
import { SetupProblem } from './platform/setup-problem.js'

export { SetupProblem }

export interface PrepareServerOptions {
  repo?: string
  /** The home folder, for a test (the suite's own files are underneath, paths.ts's `claudiaFolder`). */
  home?: string
  env?: Env
  /** The operating system's ways (src/platform/host.ts); this build's by default. */
  platform?: HostPlatform
  log?: (message: string) => void
  /** What the tests replace in the server (health check, start, ports, presence). */
  seams?: Partial<PrivateServerOptions>
}

/** Her private server for `app`'s window, not started yet. */
export async function prepareServer(app: string, options: PrepareServerOptions = {}): Promise<PrivateServer> {
  const env = options.env ?? processEnv
  const identity = getIdentity(app)
  const platform = options.platform ?? hostPlatform()
  const program = findServerProgram({ repo: options.repo, env, platform })
  if (program === null) {
    const venv = platform.venvPython.join(platform.id === 'windows' ? '\\' : '/')
    throw new SetupProblem(
      "Claudia's server needs Python 3.14, and none was found.\n" +
        'Set CLAUDIA_SERVER_PYTHON to the interpreter of an environment where Claudia is installed, or CLAUDIA_SERVER_EXE to the installer\'s claudia-server.exe ' +
        `(in a checkout: run 'uv sync --no-dev' and the interpreter is ${venv}).`,
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
  const home = options.home ?? homedir()
  const folder = claudiaFolder(platform, env, home)
  const documents = serverDocumentsDir(folder)
  const state = serverStateDir(folder)
  await mkdir(documents, { recursive: true })
  await mkdir(state, { recursive: true })
  // CLAUDIA_SERVER_PORT: another port than the one of her account (D1621), for a person who needs it for something
  // else, and for tests.
  const port = Number.parseInt(env.CLAUDIA_SERVER_PORT ?? '', 10)
  return new PrivateServer({
    app: identity.name,
    program,
    web,
    documents,
    state,
    log: options.log,
    endTheServer: platform.endTheServer,
    account: platform.account(home),
    ...(port > 0 && port < 65536 ? { port } : {}),
    ...options.seams,
  })
}
